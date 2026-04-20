import os
import json
import uuid
import hashlib
from datetime import datetime
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()
NEWS_API_KEY   = os.getenv("NewsAPI_KEY", "")
NEWS_API_BASE  = "https://newsapi.org/v2"
BOOKMARKS_FILE = os.path.join(os.path.dirname(__file__), "bookmarks.json")

# ── App Setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_bookmarks() -> list:
    if not os.path.exists(BOOKMARKS_FILE):
        return []
    try:
        with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_bookmarks(bookmarks: list) -> None:
    with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, indent=2, ensure_ascii=False)


def _article_id(article: dict) -> str:
    source = article.get("url") or article.get("title") or str(uuid.uuid4())
    return hashlib.md5(source.encode()).hexdigest()


def _clean_article(article: dict, article_id: str = None) -> dict:
    if article_id is None:
        article_id = _article_id(article)
    return {
        "id":          article_id,
        "title":       article.get("title") or "Untitled",
        "description": article.get("description") or "",
        "content":     article.get("content") or "",
        "url":         article.get("url") or "#",
        "urlToImage":  article.get("urlToImage") or "",
        "publishedAt": article.get("publishedAt") or "",
        "source":      (article.get("source") or {}).get("name") or "Unknown",
        "author":      article.get("author") or "",
    }


def _newsapi_get(endpoint: str, params: dict):
    if not NEWS_API_KEY:
        return None
    params["apiKey"] = NEWS_API_KEY
    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/{endpoint}",
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "HEAD"])
def index():
    if request.method == "HEAD":
        return "", 200
    return render_template("index.html")


@app.route("/api/news")
def get_news():
    category  = request.args.get("category", "general").lower()
    country   = request.args.get("country", "us")
    page_size = min(int(request.args.get("page_size", 20)), 100)

    valid_categories = {
        "business", "entertainment", "general",
        "health", "science", "sports", "technology"
    }
    if category not in valid_categories:
        category = "general"

    data = _newsapi_get("top-headlines", {
        "category": category,
        "country":  country,
        "pageSize": page_size,
    })

    if data is None:
        return jsonify({
            "status":   "ok",
            "articles": _mock_articles(category),
            "mock":     True,
        })

    articles = [
        _clean_article(a)
        for a in data.get("articles", [])
        if a.get("title") and a["title"] != "[Removed]"
    ]

    return jsonify({
        "status":       "ok",
        "totalResults": data.get("totalResults", len(articles)),
        "articles":     articles,
        "mock":         False,
    })


@app.route("/api/search")
def search_news():
    query     = request.args.get("q", "").strip()
    page_size = min(int(request.args.get("page_size", 20)), 100)
    sort_by   = request.args.get("sort_by", "publishedAt")

    if not query:
        return jsonify({"status": "error", "message": "Query param 'q' is required"}), 400

    data = _newsapi_get("everything", {
        "q":        query,
        "pageSize": page_size,
        "sortBy":   sort_by,
        "language": "en",
    })

    if data is None:
        return jsonify({
            "status":   "ok",
            "articles": [],
            "mock":     True,
            "message":  "Search unavailable — add a valid NewsAPI_KEY to .env",
        })

    articles = [
        _clean_article(a)
        for a in data.get("articles", [])
        if a.get("title") and a["title"] != "[Removed]"
    ]

    return jsonify({
        "status":       "ok",
        "totalResults": data.get("totalResults", len(articles)),
        "articles":     articles,
        "mock":         False,
    })


@app.route("/api/bookmarks", methods=["GET"])
def get_bookmarks():
    return jsonify({"status": "ok", "bookmarks": _load_bookmarks()})


@app.route("/api/bookmarks", methods=["POST"])
def add_bookmark():
    payload = request.get_json(silent=True)
    if not payload or not payload.get("url"):
        return jsonify({"status": "error", "message": "Invalid article payload"}), 400

    bookmarks  = _load_bookmarks()
    article_id = _article_id(payload)

    if any(b["id"] == article_id for b in bookmarks):
        return jsonify({"status": "exists", "id": article_id}), 200

    clean = _clean_article(payload, article_id)
    clean["savedAt"] = datetime.utcnow().isoformat() + "Z"
    bookmarks.append(clean)
    _save_bookmarks(bookmarks)

    return jsonify({"status": "ok", "id": article_id}), 201


@app.route("/api/bookmarks/<article_id>", methods=["DELETE"])
def remove_bookmark(article_id: str):
    bookmarks = _load_bookmarks()
    updated   = [b for b in bookmarks if b["id"] != article_id]

    if len(updated) == len(bookmarks):
        return jsonify({"status": "error", "message": "Bookmark not found"}), 404

    _save_bookmarks(updated)
    return jsonify({"status": "ok"})


# ── Mock Data ──────────────────────────────────────────────────────────────────

def _mock_articles(category: str = "general") -> list:
    return [{
        "id": str(uuid.uuid4()),
        "title": f"Demo article for {category}",
        "description": "Add your NewsAPI_KEY to fetch live headlines.",
        "content": "",
        "url": "https://newsapi.org",
        "urlToImage": "",
        "publishedAt": "2025-01-01T00:00:00Z",
        "source": "Demo",
        "author": "System",
    }]


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(BOOKMARKS_FILE):
        _save_bookmarks([])
    app.run(debug=True, port=5000)

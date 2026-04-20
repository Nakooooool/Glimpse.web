# ─────────────────────────────────────────
#  Glimpse-web  |  Flask Backend  |  app.py
# ─────────────────────────────────────────
import os, json, uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

NEWS_API_KEY   = os.getenv("NEWS_API_KEY", "YOUR_API_KEY_HERE")
NEWS_API_BASE  = "https://newsapi.org/v2"
BOOKMARKS_FILE = "bookmarks.json"

# Map frontend tab slugs → NewsAPI category values
CATEGORY_MAP = {
    "tech":          "technology",
    "sports":        "sports",
    "business":      "business",
    "health":        "health",
    "entertainment": "entertainment",
    "general":       "general",
}

# ── Bookmark file helpers ─────────────────
def load_bookmarks():
    if not os.path.exists(BOOKMARKS_FILE):
        return []
    with open(BOOKMARKS_FILE, "r") as f:
        try:    return json.load(f)
        except: return []

def save_bookmarks(data):
    with open(BOOKMARKS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Normalise article shape ───────────────
def fmt(article, idx=0):
    return {
        "id":          article.get("url", str(idx)),
        "title":       article.get("title", "No title"),
        "description": article.get("description", ""),
        "content":     article.get("content", ""),
        "url":         article.get("url", "#"),
        "image":       article.get("urlToImage", ""),
        "source":      article.get("source", {}).get("name", "Unknown"),
        "publishedAt": article.get("publishedAt", ""),
        "author":      article.get("author", ""),
    }

# ── Routes ───────────────────────────────

@app.route("/")
def index():
    """Serve the Glimpse-web single-page app."""
    return render_template("index.html")

# GET /api/news?category=tech&page=1
@app.route("/api/news")
def get_news():
    category = request.args.get("category", "general").lower()
    page     = request.args.get("page", 1, type=int)
    api_cat  = CATEGORY_MAP.get(category, "general")
    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/top-headlines",
            params={"apiKey": NEWS_API_KEY, "category": api_cat,
                    "language": "en", "pageSize": 12, "page": page},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "ok":
            return jsonify({"error": data.get("message", "API error"), "articles": []}), 400
        articles = [fmt(a, i) for i, a in enumerate(data.get("articles", []))
                    if a.get("title") and a["title"] != "[Removed]"]
        return jsonify({"articles": articles, "totalResults": data.get("totalResults", 0)})
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out", "articles": []}), 504
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500

# GET /api/search?q=keyword
@app.route("/api/search")
def search_news():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"articles": [], "totalResults": 0})
    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/everything",
            params={"apiKey": NEWS_API_KEY, "q": q, "language": "en",
                    "sortBy": "publishedAt", "pageSize": 12},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "ok":
            return jsonify({"error": data.get("message", "API error"), "articles": []}), 400
        articles = [fmt(a, i) for i, a in enumerate(data.get("articles", []))
                    if a.get("title") and a["title"] != "[Removed]"]
        return jsonify({"articles": articles, "totalResults": data.get("totalResults", 0)})
    except Exception as e:
        return jsonify({"error": str(e), "articles": []}), 500

# GET /api/bookmarks
@app.route("/api/bookmarks", methods=["GET"])
def get_bookmarks():
    return jsonify({"articles": load_bookmarks()})

# POST /api/bookmarks  — body: article JSON
@app.route("/api/bookmarks", methods=["POST"])
def add_bookmark():
    article = request.get_json()
    if not article:
        return jsonify({"error": "No data provided"}), 400
    bookmarks = load_bookmarks()
    if article.get("id") in {b.get("id") for b in bookmarks}:
        return jsonify({"message": "Already saved", "articles": bookmarks})
    article.setdefault("bookmark_id", str(uuid.uuid4()))
    bookmarks.append(article)
    save_bookmarks(bookmarks)
    return jsonify({"message": "Saved to Glimpse!", "articles": bookmarks})

# DELETE /api/bookmarks/<article_id>
@app.route("/api/bookmarks/<path:article_id>", methods=["DELETE"])
def remove_bookmark(article_id):
    bookmarks = load_bookmarks()
    updated = [b for b in bookmarks if b.get("id") != article_id]
    save_bookmarks(updated)
    return jsonify({"message": "Removed from Glimpse", "articles": updated})

# ── Entry point ───────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)

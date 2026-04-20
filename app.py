import os
import json
import uuid
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

app = Flask(__name__)

# Config
NEWS_API_KEY   = os.getenv("NEWS_API_KEY")
NEWS_API_BASE  = "https://newsapi.org/v2"
BOOKMARKS_FILE = "bookmarks.json"

# Map frontend tabs to NewsAPI categories
CATEGORY_MAP = {
    "tech":          "technology",
    "sports":        "sports",
    "business":      "business",
    "health":        "health",
    "entertainment": "entertainment",
    "general":       "general",
}

# --- Database (JSON) Helpers ---
def init_bookmarks():
    """Ensures the bookmarks file exists and is a valid list."""
    if not os.path.exists(BOOKMARKS_FILE):
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump([], f)

def load_bookmarks():
    init_bookmarks()
    try:
        with open(BOOKMARKS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []

def save_bookmarks(data):
    with open(BOOKMARKS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- Utility: Format News Data ---
def fmt(article, idx=0):
    """Normalizes NewsAPI data into a clean format for the frontend."""
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

# --- API Routes ---

@app.route("/", methods=["GET", "HEAD"])
def index():
    """Serve the main frontend. HEAD method prevents Render health-check errors."""
    return render_template("index.html")

@app.route("/api/news")
def get_news():
    if not NEWS_API_KEY:
        return jsonify({"error": "API Key missing on server", "articles": []}), 500
        
    category = request.args.get("category", "general").lower()
    page     = request.args.get("page", 1, type=int)
    api_cat  = CATEGORY_MAP.get(category, "general")
    
    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/top-headlines",
            params={
                "apiKey": NEWS_API_KEY, 
                "category": api_cat,
                "language": "en", 
                "pageSize": 12, 
                "page": page
            },
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

@app.route("/api/search")
def search_news():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"articles": [], "totalResults": 0})
        
    try:
        resp = requests.get(
            f"{NEWS_API_BASE}/everything",
            params={
                "apiKey": NEWS_API_KEY, 
                "q": q, 
                "language": "en",
                "sortBy": "publishedAt", 
                "pageSize": 12
            },
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

@app.route("/api/bookmarks", methods=["GET", "POST"])
def manage_bookmarks():
    if request.method == "POST":
        article = request.get_json()
        if not article:
            return jsonify({"error": "No data provided"}), 400
            
        bookmarks = load_bookmarks()
        # Check for duplicates
        if any(b.get("id") == article.get("id") for b in bookmarks):
            return jsonify({"message": "Already saved", "articles": bookmarks})
            
        article.setdefault("bookmark_id", str(uuid.uuid4()))
        bookmarks.append(article)
        save_bookmarks(bookmarks)
        return jsonify({"message": "Saved to Glimpse!", "articles": bookmarks})
        
    return jsonify({"articles": load_bookmarks()})

@app.route("/api/bookmarks/<path:article_id>", methods=["DELETE"])
def remove_bookmark(article_id):
    bookmarks = load_bookmarks()
    updated = [b for b in bookmarks if b.get("id") != article_id]
    save_bookmarks(updated)
    return jsonify({"message": "Removed from Glimpse", "articles": updated})

if __name__ == "__main__":
    init_bookmarks()
    app.run(debug=True, port=5000)

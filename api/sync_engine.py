import os
import requests
import time
import logging
from supabase import create_client, Client
from fastembed import TextEmbedding

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize FastEmbed & Supabase
logger.info("Initializing FastEmbed for Data Sync...")
model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_embedding(text: str):
    """Generate embedding using FastEmbed local inference"""
    try:
        # FastEmbed is optimized for batching
        embeddings = list(model.embed([text[:2000]])) # Truncate for efficiency
        return embeddings[0].tolist()
    except Exception as e:
        logger.error(f"Embedding Error: {e}")
        return None

def get_indian_movies(total_target=2100):
    """Massive crawl of Indian regional movies across languages"""
    logger.info(f"Targeting {total_target} Indian movies...")
    all_movies = []
    # Major regional languages
    languages = ['hi', 'te', 'ta', 'kn', 'ml', 'bn', 'mr', 'pa']
    pages_per_lang = (total_target // len(languages) // 20) + 2

    for lang in languages:
        logger.info(f"Crawling language: {lang}")
        for page in range(1, pages_per_lang + 1):
            try:
                url = (
                    f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}"
                    f"&region=IN&with_original_language={lang}&page={page}"
                    f"&sort_by=primary_release_date.desc&include_adult=false"
                )
                res = requests.get(url, timeout=10)
                if res.status_code == 429: # Rate Limit
                    time.sleep(2)
                    continue
                res.raise_for_status()
                data = res.json()
                results = data.get('results', [])
                if not results: break
                all_movies.extend(results)
            except Exception as e:
                logger.error(f"TMDB Fetch Error: {e}")
                continue
    return all_movies

def get_global_books(items_per_query=80):
    """Crawl global books across various categories"""
    categories = [
        "fiction", "mystery", "history", "science", "biography", "thriller",
        "philosophy", "technology", "romance", "fantasy", "business", "self-help"
    ]
    all_books = []
    
    for cat in categories:
        logger.info(f"Crawling category: {cat}")
        for start in range(0, items_per_query, 40):
            try:
                url = f"https://www.googleapis.com/books/v1/volumes?q=subject:{cat}&orderBy=newest&maxResults=40&startIndex={start}"
                res = requests.get(url, timeout=10)
                res.raise_for_status()
                data = res.json()
                items = data.get('items', [])
                if not items: break
                all_books.extend(items)
                time.sleep(0.5) # Anti-throttle
            except Exception as e:
                logger.error(f"Google Books Fetch Error: {e}")
                continue
    return all_books

def run_sync():
    # --- Sync Movies ---
    movie_candidates = get_indian_movies()
    logger.info(f"Processing {len(movie_candidates)} movies...")
    synced_movies = 0
    for m in movie_candidates:
        if not m.get('overview') or not m.get('title'): continue
        
        text = f"{m['title']}. {m['overview']}"
        vector = get_embedding(text)
        if not vector: continue

        try:
            payload = {
                "tmdb_id": m['id'],
                "title": m['title'],
                "overview": m['overview'],
                "release_date": m.get('release_date'),
                "poster_url": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else None,
                "embedding": vector
            }
            supabase.table("movies").upsert(payload, on_conflict="tmdb_id").execute()
            synced_movies += 1
            if synced_movies % 50 == 0: logger.info(f"Synced {synced_movies} movies...")
        except Exception as e:
            logger.error(f"DB Insert Error (Movie): {e}")

    # --- Sync Books ---
    book_candidates = get_global_books()
    logger.info(f"Processing {len(book_candidates)} books...")
    synced_books = 0
    for b in book_candidates:
        vol = b.get('volumeInfo', {})
        desc = vol.get('description', '')
        if not desc or not vol.get('title'): continue

        text = f"{vol['title']}. {desc}"
        vector = get_embedding(text)
        if not vector: continue

        try:
            payload = {
                "google_id": b['id'],
                "title": vol.get('title'),
                "description": desc,
                "thumbnail_url": vol.get('imageLinks', {}).get('thumbnail'),
                "embedding": vector
            }
            supabase.table("books").upsert(payload, on_conflict="google_id").execute()
            synced_books += 1
            if synced_books % 50 == 0: logger.info(f"Synced {synced_books} books...")
        except Exception as e:
            logger.error(f"DB Insert Error (Book): {e}")

    logger.info(f"Sync complete. Movies: {synced_movies}, Books: {synced_books}")

if __name__ == "__main__":
    if not all([TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
        logger.error("Missing Environment Variables!")
    else:
        run_sync()
import os
import requests
import time
import logging
from supabase import create_client, Client

# Set up logging for GitHub Actions output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

# 2. Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_embedding(text: str):
    """
    Calls Hugging Face Inference API for embeddings.
    Replaces local ML libraries to stay under memory/storage limits.
    """
    if not HF_TOKEN:
        logger.error("HF_TOKEN is missing! Cannot generate embeddings.")
        return None

    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    for i in range(5):
        try:
            response = requests.post(
                api_url, 
                headers=headers, 
                json={"inputs": text, "options": {"wait_for_model": True}}, 
                timeout=30
            )
            
            if response.status_code == 200:
                vector = response.json()
                # FLATTENING LOGIC: Ensure we have a flat list of 384 floats
                if isinstance(vector, list):
                    while len(vector) > 0 and isinstance(vector[0], list):
                        vector = vector[0]
                    return vector
                return vector
            elif response.status_code == 503:
                wait_time = (i + 1) * 5
                logger.info(f"AI Engine warming up... waiting {wait_time}s")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"HF Error: {response.status_code} - {response.text}")
                break
        except Exception as e:
            logger.error(f"Request Error: {e}")
            time.sleep(2)
    return None

def get_indian_movies(total_target=2100):
    """Fetch a massive collection of Indian movies across regions to reach 2000+ rows"""
    logger.info(f"Targeting at least {total_target} Indian movies...")
    all_movies = []
    
    # Expanded language list to cover more regional markets
    languages = ['hi', 'te', 'ta', 'kn', 'ml', 'pa', 'bn', 'mr']
    
    # Calculate pages needed per language (approx 20 movies per page)
    pages_per_lang = (total_target // len(languages) // 20) + 5 

    for lang in languages:
        logger.info(f"Deep crawling movies for language: {lang}...")
        for page in range(1, pages_per_lang + 1):
            try:
                url = (
                    f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}"
                    f"&region=IN&with_origin_country=IN&with_original_language={lang}"
                    f"&sort_by=primary_release_date.desc&include_adult=false&page={page}"
                    f"&primary_release_year.gte=2000" 
                )
                response = requests.get(url)
                if response.status_code == 429: # Rate limit handling
                    time.sleep(2)
                    continue
                
                response.raise_for_status()
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    break 
                    
                all_movies.extend(results)
                
                if len(all_movies) > total_target + 500:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching {lang} movies page {page}: {e}")
                continue
    
    return all_movies

def get_global_books(items_per_query=120):
    """Fetch a massive collection of books across 30+ categories with pagination"""
    queries = [
        "fiction", "mystery", "history", "science", "biography", "thriller",
        "philosophy", "technology", "romance", "fantasy", "business", "travel",
        "self-help", "poetry", "art", "psychology", "economics", "cooking",
        "health", "religion", "politics", "sociology", "education", "law",
        "adventure", "classics", "comics", "drama", "horror"
    ]
    all_books = []
    
    for query in queries:
        logger.info(f"Deep crawling books for category: {query}...")
        for start_index in range(0, items_per_query, 40):
            try:
                url = f"https://www.googleapis.com/books/v1/volumes?q={query}&orderBy=newest&maxResults=40&startIndex={start_index}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                    
                all_books.extend(items)
                time.sleep(0.5) # Respect Google Books API
            except Exception as e:
                logger.error(f"Error fetching books for {query} at index {start_index}: {e}")
                continue
    
    return all_books

def run_sync():
    if not supabase:
        logger.error("Supabase not initialized. Check your credentials.")
        return

    # --- Process Movies ---
    movie_candidates = get_indian_movies(total_target=2200) 
    synced_movies = 0
    logger.info(f"Total movie candidates fetched: {len(movie_candidates)}. Starting vector processing...")
    
    for m in movie_candidates:
        try:
            if not m.get('overview') or not m.get('title'):
                continue
            
            # Limit text to roughly 2000 chars for the embedding model
            text_content = f"{m['title']}. {m.get('overview', '')}"[:2000]
            embedding = get_embedding(text_content)
            
            if not embedding:
                continue

            movie_payload = {
                "tmdb_id": m['id'],
                "title": m['title'],
                "overview": m['overview'],
                "release_date": m.get('release_date') if m.get('release_date') else None,
                "poster_url": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else None,
                "language": m.get('original_language'),
                "origin_country": [m.get('origin_country')] if isinstance(m.get('origin_country'), str) else m.get('origin_country'),
                "embedding": embedding
            }
            supabase.table("movies").upsert(movie_payload, on_conflict="tmdb_id").execute()
            synced_movies += 1
            
            if synced_movies % 100 == 0:
                logger.info(f"Progress: {synced_movies} movies synced to database...")
                
        except Exception as e:
            logger.error(f"Database error saving movie {m.get('title')}: {e}")

    logger.info(f"Successfully finished movie sync. Total unique movies processed: {synced_movies}")

    # --- Process Books ---
    book_items = get_global_books(items_per_query=120)
    synced_books = 0
    logger.info(f"Total book candidates fetched: {len(book_items)}. Starting vector processing...")
    
    for b in book_items:
        try:
            vol = b.get('volumeInfo', {})
            description = vol.get('description', '')
            if not description or not vol.get('title'):
                continue

            text_content = f"{vol.get('title')}. {description}"[:2000]
            embedding = get_embedding(text_content)
            
            if not embedding:
                continue

            book_payload = {
                "google_id": b['id'],
                "title": vol.get('title'),
                "authors": vol.get('authors', []),
                "description": description,
                "thumbnail_url": vol.get('imageLinks', {}).get('thumbnail'),
                "categories": vol.get('categories', []),
                "embedding": embedding
            }
            supabase.table("books").upsert(book_payload, on_conflict="google_id").execute()
            synced_books += 1
            if synced_books % 100 == 0:
                logger.info(f"Progress: {synced_books} books synced...")
        except Exception as e:
            logger.error(f"Database error saving book: {e}")

    logger.info(f"Successfully finished book sync. Total unique books processed: {synced_books}")
    logger.info("Full database update completed. Ready for hybrid recommendation serving.")

if __name__ == "__main__":
    missing = []
    if not TMDB_API_KEY: missing.append("TMDB_API_KEY")
    if not SUPABASE_URL: missing.append("SUPABASE_URL")
    if not SUPABASE_KEY: missing.append("SUPABASE_KEY")
    if not HF_TOKEN: missing.append("HF_TOKEN")

    if missing:
        logger.error(f"FAILED TO START: Missing secrets in environment: {', '.join(missing)}")
    else:
        run_sync()
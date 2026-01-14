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

def get_indian_movies(total_target=10000):
    """Massive crawl of Indian regional movies across languages and genres"""
    logger.info(f"Targeting {total_target} Indian movies...")
    all_movies = []
    seen_ids = set()
    
    # Selected Indian languages: English, Telugu, Hindi, Tamil, Kannada, Malayalam
    languages = ['en', 'te', 'hi', 'ta', 'kn', 'ml']
    
    # Multiple discovery strategies
    strategies = [
        {'sort_by': 'primary_release_date.desc', 'name': 'Recent'},
        {'sort_by': 'popularity.desc', 'name': 'Popular'},
        {'sort_by': 'vote_average.desc', 'vote_count.gte': 10, 'name': 'Top Rated'},
        {'sort_by': 'revenue.desc', 'name': 'Box Office'},
    ]
    
    # Year ranges for better coverage
    year_ranges = [
        (2020, 2026),  # Recent
        (2015, 2019),  # Mid-range
        (2010, 2014),  # Older
        (2000, 2009),  # Classic
        (1990, 1999),  # Vintage
    ]
    
    for lang in languages:
        logger.info(f"Crawling language: {lang}")
        
        for strategy in strategies:
            for year_start, year_end in year_ranges:
                pages = 25 if year_start >= 2015 else 15  # More pages for recent content
                
                for page in range(1, pages + 1):
                    try:
                        params = {
                            'api_key': TMDB_API_KEY,
                            'region': 'IN',
                            'with_original_language': lang,
                            'page': page,
                            'sort_by': strategy['sort_by'],
                            'include_adult': 'false',
                            'primary_release_date.gte': f'{year_start}-01-01',
                            'primary_release_date.lte': f'{year_end}-12-31',
                        }
                        
                        if 'vote_count.gte' in strategy:
                            params['vote_count.gte'] = strategy['vote_count.gte']
                        
                        url = f"https://api.themoviedb.org/3/discover/movie"
                        res = requests.get(url, params=params, timeout=10)
                        
                        if res.status_code == 429:
                            logger.warning("Rate limit hit, waiting...")
                            time.sleep(3)
                            continue
                            
                        res.raise_for_status()
                        data = res.json()
                        results = data.get('results', [])
                        
                        if not results:
                            break
                        
                        # Deduplicate
                        for movie in results:
                            if movie['id'] not in seen_ids:
                                seen_ids.add(movie['id'])
                                all_movies.append(movie)
                        
                        logger.info(f"{lang} - {strategy['name']} - {year_start}-{year_end} - Page {page}: {len(all_movies)} total")
                        
                        if len(all_movies) >= total_target:
                            logger.info(f"Target reached: {len(all_movies)} movies")
                            return all_movies
                        
                        time.sleep(0.25)  # Rate limiting
                        
                    except Exception as e:
                        logger.error(f"TMDB Fetch Error: {e}")
                        continue
    
    logger.info(f"Collected {len(all_movies)} unique movies")
    return all_movies

def get_global_books(total_target=5000):
    """Crawl global books across various categories and languages"""
    logger.info(f"Targeting {total_target} books...")
    all_books = []
    seen_ids = set()
    
    # Expanded categories
    categories = [
        "fiction", "mystery", "history", "science", "biography", "thriller",
        "philosophy", "technology", "romance", "fantasy", "business", "self-help",
        "poetry", "drama", "adventure", "horror", "crime", "psychology",
        "art", "cooking", "travel", "health", "education", "religion",
        "politics", "economics", "sociology", "mathematics", "physics",
        "literature", "classics", "contemporary", "young adult", "children"
    ]
    
    # Multiple search strategies
    order_types = ['newest', 'relevance']
    
    # Only English books
    lang = 'en'
    
    for cat in categories:
        for order in order_types:
            logger.info(f"Crawling: {cat} ({order}, {lang})")
                
            # Fetch up to 200 books per category/order combination
            for start in range(0, 200, 40):
                try:
                    params = {
                        'q': f'subject:{cat}',
                        'orderBy': order,
                        'maxResults': 40,
                        'startIndex': start,
                        'langRestrict': lang,
                        'printType': 'books'
                    }
                    
                    url = "https://www.googleapis.com/books/v1/volumes"
                    res = requests.get(url, params=params, timeout=10)
                    res.raise_for_status()
                    data = res.json()
                    items = data.get('items', [])
                    
                    if not items:
                        break
                    
                    # Deduplicate
                    for book in items:
                        if book['id'] not in seen_ids:
                            seen_ids.add(book['id'])
                            all_books.append(book)
                    
                    logger.info(f"{cat} - {order}: {len(all_books)} total books")
                    
                    if len(all_books) >= total_target:
                        logger.info(f"Target reached: {len(all_books)} books")
                        return all_books
                    
                    time.sleep(0.5)  # Anti-throttle
                    
                except Exception as e:
                    logger.error(f"Google Books Fetch Error: {e}")
                    time.sleep(1)
                    continue
    
    logger.info(f"Collected {len(all_books)} unique books")
    return all_books

def run_sync():
    # Get targets from environment or use defaults
    movie_target = int(os.getenv('MOVIE_TARGET', '10000'))
    book_target = int(os.getenv('BOOK_TARGET', '5000'))
    
    logger.info(f"Sync targets - Movies: {movie_target}, Books: {book_target}")
    
    # --- Sync Movies ---
    movie_candidates = get_indian_movies(total_target=movie_target)
    logger.info(f"Processing {len(movie_candidates)} movies...")
    synced_movies = 0
    failed_movies = 0
    
    for m in movie_candidates:
        if not m.get('overview') or not m.get('title'): 
            continue
        
        text = f"{m['title']}. {m['overview']}"
        vector = get_embedding(text)
        if not vector: 
            failed_movies += 1
            continue

        try:
            payload = {
                "tmdb_id": m['id'],
                "title": m['title'],
                "overview": m['overview'],
                "release_date": m.get('release_date'),
                "poster_url": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else None,
                "language": m.get('original_language'),
                "embedding": vector
            }
            supabase.table("movies").upsert(payload, on_conflict="tmdb_id").execute()
            synced_movies += 1
            if synced_movies % 100 == 0: 
                logger.info(f"✓ Synced {synced_movies} movies (failed: {failed_movies})...")
        except Exception as e:
            logger.error(f"DB Insert Error (Movie): {e}")
            failed_movies += 1

    logger.info(f"Movies complete: {synced_movies} synced, {failed_movies} failed")

    # --- Sync Books ---
    book_candidates = get_global_books(total_target=book_target)
    logger.info(f"Processing {len(book_candidates)} books...")
    synced_books = 0
    failed_books = 0
    
    for b in book_candidates:
        vol = b.get('volumeInfo', {})
        desc = vol.get('description', '')
        if not desc or not vol.get('title'): 
            continue

        text = f"{vol['title']}. {desc}"
        vector = get_embedding(text)
        if not vector: 
            failed_books += 1
            continue

        try:
            authors = vol.get('authors', [])
            categories = vol.get('categories', [])
            
            payload = {
                "google_id": b['id'],
                "title": vol.get('title'),
                "authors": authors[0] if authors else None,
                "description": desc[:2000],  # Truncate long descriptions
                "thumbnail_url": vol.get('imageLinks', {}).get('thumbnail'),
                "published_date": vol.get('publishedDate'),
                "categories": categories[0] if categories else None,
                "language": vol.get('language'),
                "embedding": vector
            }
            supabase.table("books").upsert(payload, on_conflict="google_id").execute()
            synced_books += 1
            if synced_books % 100 == 0: 
                logger.info(f"✓ Synced {synced_books} books (failed: {failed_books})...")
        except Exception as e:
            logger.error(f"DB Insert Error (Book): {e}")
            failed_books += 1

    logger.info(f"Books complete: {synced_books} synced, {failed_books} failed")
    logger.info(f"🎉 SYNC COMPLETE - Movies: {synced_movies}, Books: {synced_books}")

if __name__ == "__main__":
    if not all([TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
        logger.error("Missing Environment Variables!")
    else:
        run_sync()
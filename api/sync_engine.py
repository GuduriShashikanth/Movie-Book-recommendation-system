import os
import requests
import time
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# 1. Load Configuration from Environment Variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. Initialize Clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Loading ML Embedding Model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_indian_movies(total_target=2100):
    """Fetch a massive collection of Indian movies across regions to reach 2000+ rows"""
    print(f"Targeting at least {total_target} Indian movies...")
    all_movies = []
    
    # Expanded language list to cover more regional markets
    languages = ['hi', 'te', 'ta', 'kn', 'ml', 'pa', 'bn', 'mr']
    
    # Calculate pages needed per language (approx 20 movies per page)
    # We aim for ~270 movies per language to safely hit 2000+
    pages_per_lang = (total_target // len(languages) // 20) + 5 

    for lang in languages:
        print(f"Deep crawling movies for language: {lang}...")
        for page in range(1, pages_per_lang + 1):
            try:
                # We use sort_by=primary_release_date.desc to ensure we get "recent" movies first
                url = (
                    f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}"
                    f"&region=IN&with_origin_country=IN&with_original_language={lang}"
                    f"&sort_by=primary_release_date.desc&include_adult=false&page={page}"
                    f"&primary_release_year.gte=2000" # Focus on movies from the last 25 years
                )
                response = requests.get(url)
                if response.status_code == 429: # Rate limit handling
                    time.sleep(2)
                    continue
                
                response.raise_for_status()
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    break # Stop if no more movies for this language
                    
                all_movies.extend(results)
                
                # Exit early if we've gathered enough candidates to process
                if len(all_movies) > total_target + 500:
                    break
                    
            except Exception as e:
                print(f"Error fetching {lang} movies page {page}: {e}")
                continue
    
    return all_movies

def get_global_books():
    """Fetch books from 15 diverse categories to maximize row count"""
    queries = [
        "fiction", "mystery", "history", "science", "biography", "thriller",
        "philosophy", "technology", "romance", "fantasy", "business", "travel",
        "self-help", "poetry", "art"
    ]
    all_books = []
    
    for query in queries:
        try:
            print(f"Fetching books for category: {query}...")
            # Google Books max is 40 per request
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&orderBy=newest&maxResults=40"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
            all_books.extend(items)
        except Exception as e:
            print(f"Error fetching books for {query}: {e}")
            continue
    
    return all_books

def run_sync():
    # --- Process Movies ---
    # Fetching a large batch to filter for quality (must have overview)
    movie_candidates = get_indian_movies(total_target=2200) 
    synced_movies = 0
    print(f"Total movie candidates fetched: {len(movie_candidates)}. Starting vector processing...")
    
    for m in movie_candidates:
        try:
            # Skip if no metadata exists for embedding
            if not m.get('overview') or not m.get('title'):
                continue
                
            text_content = f"{m['title']}. {m.get('overview', '')}"
            # Embeddings are essential for the recommendation engine
            embedding = model.encode(text_content).tolist()
            
            movie_payload = {
                "tmdb_id": m['id'],
                "title": m['title'],
                "overview": m['overview'],
                "release_date": m.get('release_date'),
                "poster_url": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else None,
                "language": m.get('original_language'),
                "origin_country": [m.get('origin_country')] if isinstance(m.get('origin_country'), str) else m.get('origin_country'),
                "embedding": embedding
            }
            supabase.table("movies").upsert(movie_payload, on_conflict="tmdb_id").execute()
            synced_movies += 1
            
            if synced_movies % 50 == 0:
                print(f"Progress: {synced_movies} movies synced to database...")
                
        except Exception as e:
            pass # Silent skip for malformed data

    print(f"Successfully finished movie sync. Total unique movies in DB: {synced_movies}")

    # --- Process Books ---
    book_items = get_global_books()
    synced_books = 0
    print(f"Total book candidates fetched: {len(book_items)}. Starting processing...")
    
    for b in book_items:
        try:
            vol = b.get('volumeInfo', {})
            description = vol.get('description', '')
            if not description or not vol.get('title'):
                continue

            text_content = f"{vol.get('title')}. {description}"
            embedding = model.encode(text_content).tolist()
            
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
            if synced_books % 50 == 0:
                print(f"Progress: {synced_books} books synced...")
        except Exception as e:
            pass

    print(f"Successfully finished book sync. Total: {synced_books}")
    print("Full database update completed. Ready for hybrid recommendation serving.")

if __name__ == "__main__":
    if not all([TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
        print("CRITICAL ERROR: Environment variables missing.")
    else:
        run_sync()

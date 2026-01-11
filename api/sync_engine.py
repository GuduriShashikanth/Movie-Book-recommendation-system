import os
import requests
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# 1. Load Configuration from Environment Variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. Initialize Clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Loading ML Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_indian_movies(pages=10):
    """Fetch multiple pages of recent Indian movies from TMDB"""
    print(f"Fetching {pages} pages of Indian movies from TMDB...")
    all_movies = []
    
    for page in range(1, pages + 1):
        try:
            url = (
                f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}"
                f"&region=IN&with_origin_country=IN&sort_by=release_date.desc"
                f"&include_adult=false&page={page}"
            )
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            all_movies.extend(data.get('results', []))
        except Exception as e:
            print(f"Error fetching movie page {page}: {e}")
            continue
    
    return all_movies

def get_global_books(queries=["fiction", "mystery", "history", "science", "biography", "thriller"]):
    """Fetch books from multiple categories to diversify the collection"""
    all_books = []
    
    for query in queries:
        try:
            print(f"Fetching books for category: {query}...")
            # Max results per request is 40 for Google Books
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&orderBy=newest&maxResults=40"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            all_books.extend(data.get('items', []))
        except Exception as e:
            print(f"Error fetching books for {query}: {e}")
            continue
    
    return all_books

def run_sync():
    # --- Process Movies ---
    # Fetching 10 pages = approx 200 items
    movies = get_indian_movies(pages=10) 
    synced_movies = 0
    for m in movies:
        try:
            if not m.get('overview') or not m.get('title'):
                continue
                
            text_content = f"{m['title']}. {m.get('overview', '')}"
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
        except Exception as e:
            print(f"Error processing movie {m.get('title')}: {e}")

    print(f"Successfully synced {synced_movies} Indian movies.")

    # --- Process Books ---
    # Fetching 6 categories * 40 items = approx 240 items
    book_items = get_global_books()
    synced_books = 0
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
        except Exception as e:
            print(f"Error processing book {vol.get('title')}: {e}")

    print(f"Successfully synced {synced_books} global books.")
    print("Sync process completed.")

if __name__ == "__main__":
    if not all([TMDB_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
        print("CRITICAL ERROR: Environment variables missing.")
    else:
        run_sync()

import os

# --- CRITICAL MEMORY LIMITS (MUST BE AT TOP) ---
# This stops the AI engine from spawning extra threads that steal RAM
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["ONNXRUNTIME_ENABLE_TELEMETRY"] = "0"

import logging
import requests
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastembed import TextEmbedding
from dotenv import load_dotenv
from typing import List, Optional
from uuid import UUID

# Import local modules
from api.database import get_db
from api.auth import (
    hash_password, verify_password, create_access_token, 
    get_current_user
)
from api.models import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    RatingCreate, RatingResponse, InteractionCreate,
    RecommendationResponse
)

# 1. Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Configuration
load_dotenv()

# 3. Initialize FastEmbed
# We use a singleton pattern to ensure the model only ever exists once in memory
_model = None

def get_model():
    global _model
    if _model is None:
        logger.info("Loading FastEmbed Model into RAM...")
        try:
            # all-MiniLM-L6-v2 is the smallest reliable model (~80MB)
            _model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Model Load Failed: {e}")
    return _model

# 4. FastAPI App
app = FastAPI(
    title="CineLibre - Full Stack Recommendation API",
    description="MovieLens-style recommendation system for Indian cinema",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.head("/")
async def health_check():
    """Health check triggers model loading if not already loaded"""
    m = get_model()
    db = get_db()
    return {
        "status": "online",
        "engine": "FastEmbed",
        "ready": m is not None,
        "database": "connected" if db else "error",
        "version": "2.0.0"
    }

# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    db = get_db()
    
    # Check if user exists
    existing = db.table("users").select("id").eq("email", user_data.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_pw = hash_password(user_data.password)
    new_user = db.table("users").insert({
        "email": user_data.email,
        "password_hash": hashed_pw,
        "name": user_data.name
    }).execute()
    
    if not new_user.data:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    user = new_user.data[0]
    token = create_access_token({"user_id": user["id"], "email": user["email"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse(**user)
    }

@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user"""
    db = get_db()
    
    # Find user
    result = db.table("users").select("*").eq("email", credentials.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = result.data[0]
    
    # Verify password
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"user_id": user["id"], "email": user["email"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse(**user)
    }

@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    db = get_db()
    result = db.table("users").select("*").eq("id", current_user["user_id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**result.data[0])

# ==================== RATING ENDPOINTS ====================

@app.options("/ratings")
async def ratings_options():
    """Handle CORS preflight for ratings endpoint"""
    return {"message": "OK"}

@app.post("/ratings", response_model=RatingResponse)
async def create_rating(
    rating_data: RatingCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create or update a rating"""
    db = get_db()
    
    # Upsert rating
    result = db.table("ratings").upsert({
        "user_id": current_user["user_id"],
        "item_id": rating_data.item_id,
        "item_type": rating_data.item_type,
        "rating": rating_data.rating
    }, on_conflict="user_id,item_id,item_type").execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save rating")
    
    return RatingResponse(**result.data[0])

@app.get("/ratings/my", response_model=List[RatingResponse])
async def get_my_ratings(
    item_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current user's ratings"""
    db = get_db()
    query = db.table("ratings").select("*").eq("user_id", current_user["user_id"])
    
    if item_type:
        query = query.eq("item_type", item_type)
    
    result = query.order("created_at", desc=True).execute()
    return [RatingResponse(**r) for r in result.data]

@app.delete("/ratings/{rating_id}")
async def delete_rating(
    rating_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a rating"""
    db = get_db()
    result = db.table("ratings").delete().eq("id", rating_id).eq("user_id", current_user["user_id"]).execute()
    return {"message": "Rating deleted"}

# ==================== INTERACTION TRACKING ====================

@app.options("/interactions")
async def interactions_options():
    """Handle CORS preflight for interactions endpoint"""
    return {"message": "OK"}

@app.post("/interactions")
async def track_interaction(
    interaction: InteractionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Track user interaction (view, click, search)"""
    db = get_db()
    
    try:
        # Ensure item_id is a valid UUID string
        item_id = str(interaction.item_id).strip()
        
        # Validate UUID format
        from uuid import UUID
        try:
            UUID(item_id)
        except ValueError:
            logger.warning(f"Invalid UUID format for item_id: {item_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid item_id format. Expected UUID, got: {item_id}. Please use the 'id' field from movie/book objects, not tmdb_id or other numeric IDs."
            )
        
        # Validate item_type and interaction_type
        if interaction.item_type not in ["movie", "book"]:
            logger.error(f"Invalid item_type: {interaction.item_type}")
            return {
                "message": "Invalid item_type", 
                "success": False, 
                "error": f"item_type must be 'movie' or 'book', got: {interaction.item_type}"
            }
        
        if interaction.interaction_type not in ["view", "click", "search"]:
            logger.error(f"Invalid interaction_type: {interaction.interaction_type}")
            return {
                "message": "Invalid interaction_type", 
                "success": False, 
                "error": f"interaction_type must be 'view', 'click', or 'search', got: {interaction.interaction_type}"
            }
        
        # Log the data being inserted for debugging
        insert_data = {
            "user_id": current_user["user_id"],
            "item_id": item_id,
            "item_type": interaction.item_type,
            "interaction_type": interaction.interaction_type
        }
        logger.info(f"Inserting interaction: {insert_data}")
        
        result = db.table("interactions").insert(insert_data).execute()
        
        logger.info(f"Interaction tracked successfully: user={current_user['user_id']}, item={item_id}, type={interaction.interaction_type}")
        return {"message": "Interaction tracked", "success": True}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Interaction tracking error: {error_msg}")
        
        # Check if it's a UUID error
        if "invalid input syntax for type uuid" in error_msg.lower():
            return {
                "message": "Invalid item_id format", 
                "success": False, 
                "error": "item_id must be a valid UUID (e.g., 'ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f'). Use the 'id' field from movie/book objects, not 'tmdb_id'.",
                "hint": "Make sure you're using movie.id or book.id, not movie.tmdb_id"
            }
        
        # Check for constraint violations
        if "check constraint" in error_msg.lower():
            return {
                "message": "Constraint violation", 
                "success": False, 
                "error": error_msg,
                "hint": "Ensure item_type is 'movie' or 'book', and interaction_type is 'view', 'click', or 'search'"
            }
        
        # Return 200 but with success=false to not break frontend
        return {"message": "Interaction tracking failed", "success": False, "error": error_msg}

@app.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=3), 
    type: str = "movie", 
    limit: int = 12,
    threshold: float = 0.4
):
    """Semantic search with TMDB fallback - no authentication required"""
    m = get_model()
    db = get_db()
    if not m or not db:
        raise HTTPException(status_code=500, detail="System initializing...")
    
    try:
        # Generate embedding (list format for Supabase)
        query_embeddings = list(m.embed([q]))
        query_vector = query_embeddings[0].tolist()

        rpc_function = "match_movies" if type == "movie" else "match_books"
        response = db.rpc(rpc_function, {
            "query_embedding": query_vector,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        
        # If no results found in DB and searching for movies, try TMDB
        if (not response.data or len(response.data) == 0) and type == "movie":
            logger.info(f"No results in DB for '{q}', searching TMDB...")
            tmdb_results = await search_tmdb_and_add(q, limit, db, m)
            if tmdb_results:
                return {"query": q, "results": tmdb_results, "source": "tmdb"}
        
        return {"query": q, "results": response.data, "source": "database"}
    except Exception as e:
        logger.error(f"Search Error: {e}")
        raise HTTPException(status_code=500, detail="Search processing failed.")

async def search_tmdb_and_add(query: str, limit: int, db, model):
    """Search TMDB, add results to DB, and return them"""
    tmdb_api_key = os.getenv("TMDB_API_KEY")
    if not tmdb_api_key:
        logger.error("TMDB API key not configured")
        return []
    
    try:
        # Search TMDB
        url = "https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": tmdb_api_key,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": False
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200:
            logger.error(f"TMDB API error: {response.status_code}")
            return []
        
        data = response.json()
        results = data.get("results", [])[:limit]
        
        if not results:
            logger.info(f"No TMDB results for query: {query}")
            return []
        
        # Add movies to database and return formatted results
        added_movies = []
        
        for movie in results:
            if not movie.get("overview") or not movie.get("title"):
                continue
            
            try:
                # Check if movie already exists
                existing = db.table("movies").select("id, tmdb_id, title, overview, poster_url, language, release_date").eq("tmdb_id", movie["id"]).execute()
                
                if existing.data:
                    # Movie exists, return it
                    added_movies.append({
                        "id": existing.data[0]["id"],
                        "tmdb_id": existing.data[0]["tmdb_id"],
                        "title": existing.data[0]["title"],
                        "overview": existing.data[0]["overview"],
                        "poster_url": existing.data[0]["poster_url"],
                        "language": existing.data[0]["language"],
                        "similarity": 0.9,  # High similarity since it's a direct search match
                        "release_date": existing.data[0].get("release_date")
                    })
                else:
                    # Generate embedding for the movie
                    text = f"{movie['title']}. {movie['overview']}"
                    embeddings = list(model.embed([text[:2000]]))
                    vector = embeddings[0].tolist()
                    
                    # Add to database
                    payload = {
                        "tmdb_id": movie["id"],
                        "title": movie["title"],
                        "overview": movie["overview"],
                        "release_date": movie.get("release_date"),
                        "poster_url": f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None,
                        "language": movie.get("original_language", "en"),
                        "embedding": vector
                    }
                    
                    result = db.table("movies").insert(payload).execute()
                    
                    if result.data:
                        added_movies.append({
                            "id": result.data[0]["id"],
                            "tmdb_id": result.data[0]["tmdb_id"],
                            "title": result.data[0]["title"],
                            "overview": result.data[0]["overview"],
                            "poster_url": result.data[0]["poster_url"],
                            "language": result.data[0]["language"],
                            "similarity": 0.9,
                            "release_date": result.data[0].get("release_date")
                        })
                        
                        logger.info(f"Added movie from TMDB: {movie['title']}")
            
            except Exception as e:
                logger.error(f"Error adding TMDB movie '{movie.get('title', 'unknown')}': {e}")
                continue
        
        logger.info(f"TMDB search returned {len(added_movies)} movies for query: {query}")
        return added_movies
    
    except Exception as e:
        logger.error(f"TMDB search error: {e}")
        return []

# ==================== RECOMMENDATION ENDPOINTS ====================

@app.get("/recommendations/personalized")
async def get_personalized_recommendations(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get personalized recommendations using collaborative filtering"""
    db = get_db()
    
    try:
        # Call Supabase RPC function for collaborative filtering
        result = db.rpc("get_collaborative_recommendations", {
            "target_user_id": current_user["user_id"],
            "recommendation_count": limit
        }).execute()
        
        if result.data and len(result.data) > 0:
            return {"recommendations": result.data, "method": "collaborative_filtering"}
        else:
            # If no collaborative recommendations, try content-based on user's ratings
            logger.info("No collaborative recommendations, trying content-based")
            return await get_content_based_recommendations(current_user["user_id"], limit, db)
    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        # Try content-based instead of popular
        try:
            return await get_content_based_recommendations(current_user["user_id"], limit, db)
        except:
            # Last resort: return empty with error method
            return {"recommendations": [], "method": "error", "message": "Unable to generate personalized recommendations"}

async def get_content_based_recommendations(user_id: int, limit: int, db):
    """Get recommendations based on user's rated items"""
    try:
        # Get user's top-rated items
        user_ratings = db.table("ratings").select("item_id, item_type, rating").eq("user_id", user_id).gte("rating", 3.5).order("rating", desc=True).limit(5).execute()
        
        if not user_ratings.data:
            # No ratings at all - return diverse recent items instead of popular
            logger.info("No user ratings, returning diverse recent items")
            movies = db.table("movies").select("id, title, poster_url, language").order("created_at", desc=True).limit(limit // 2).execute()
            books = db.table("books").select("id, title, thumbnail_url, authors").order("created_at", desc=True).limit(limit // 2).execute()
            
            recommendations = []
            for m in movies.data:
                recommendations.append({
                    "item_id": str(m["id"]),
                    "item_type": "movie",
                    "title": m["title"],
                    "poster_url": m["poster_url"]
                })
            for b in books.data:
                recommendations.append({
                    "item_id": str(b["id"]),
                    "item_type": "book",
                    "title": b["title"],
                    "poster_url": b.get("thumbnail_url")
                })
            
            return {"recommendations": recommendations[:limit], "method": "diverse_recent"}
        
        recommendations = []
        seen_ids = set()
        
        # Add user's rated items to seen set to exclude them
        for rating in user_ratings.data:
            seen_ids.add(str(rating["item_id"]))
        
        # For each highly rated item, find similar items
        for rating in user_ratings.data:
            item_id = rating["item_id"]
            item_type = rating["item_type"]
            
            # Get item embedding
            table = "movies" if item_type == "movie" else "books"
            item = db.table(table).select("embedding").eq("id", item_id).execute()
            
            if not item.data:
                continue
            
            embedding = item.data[0]["embedding"]
            
            # Find similar items
            rpc_function = "match_movies" if item_type == "movie" else "match_books"
            result = db.rpc(rpc_function, {
                "query_embedding": embedding,
                "match_threshold": 0.3,  # Lower threshold for more results
                "match_count": 15
            }).execute()
            
            # Add to recommendations if not already seen or rated
            for rec in result.data:
                rec_id = str(rec.get("id"))
                if rec_id not in seen_ids:
                    seen_ids.add(rec_id)
                    recommendations.append({
                        "item_id": rec_id,
                        "item_type": item_type,
                        "title": rec.get("title"),
                        "poster_url": rec.get("poster_url") or rec.get("thumbnail_url"),
                        "similarity": rec.get("similarity"),
                        "based_on": rating["item_id"]  # Show what it's based on
                    })
                    
                    if len(recommendations) >= limit:
                        break
            
            if len(recommendations) >= limit:
                break
        
        if len(recommendations) == 0:
            # If still no recommendations, get items from different languages/categories
            logger.info("No similar items found, getting diverse content")
            movies = db.table("movies").select("id, title, poster_url, language").order("created_at", desc=True).limit(limit).execute()
            recommendations = [{
                "item_id": str(m["id"]),
                "item_type": "movie",
                "title": m["title"],
                "poster_url": m["poster_url"]
            } for m in movies.data]
            return {"recommendations": recommendations[:limit], "method": "diverse_fallback"}
        
        return {"recommendations": recommendations[:limit], "method": "content_based"}
    except Exception as e:
        logger.error(f"Content-based recommendation error: {e}")
        # Return diverse content instead of popular
        try:
            movies = db.table("movies").select("id, title, poster_url").order("created_at", desc=True).limit(limit).execute()
            recommendations = [{
                "item_id": str(m["id"]),
                "item_type": "movie",
                "title": m["title"],
                "poster_url": m["poster_url"]
            } for m in movies.data]
            return {"recommendations": recommendations[:limit], "method": "error_fallback"}
        except:
            return {"recommendations": [], "method": "error"}

@app.get("/recommendations/similar/{item_type}/{item_id}")
async def get_similar_items(
    item_type: str,
    item_id: str,  # UUID as string
    limit: int = 12
):
    """Get similar items using content-based filtering"""
    db = get_db()
    
    try:
        # Get item embedding
        table = "movies" if item_type == "movie" else "books"
        item = db.table(table).select("embedding").eq("id", item_id).execute()
        
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found")
        
        embedding = item.data[0]["embedding"]
        
        # Find similar items
        rpc_function = "match_movies" if item_type == "movie" else "match_books"
        result = db.rpc(rpc_function, {
            "query_embedding": embedding,
            "match_threshold": 0.5,
            "match_count": limit + 1  # +1 to exclude self
        }).execute()
        
        # Filter out the item itself
        similar = [r for r in result.data if str(r.get("id")) != str(item_id)][:limit]
        
        return {"item_id": item_id, "similar_items": similar, "method": "content_based"}
    except Exception as e:
        logger.error(f"Similar items error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get similar items")

@app.get("/recommendations/popular")
async def get_popular_items(limit: int = 20):
    """Get popular items based on ratings"""
    db = get_db()
    
    try:
        result = db.rpc("get_popular_items", {
            "item_limit": limit
        }).execute()
        
        # If no popular items (not enough ratings), return recent movies
        if not result.data or len(result.data) == 0:
            logger.info("No popular items, returning recent movies")
            recent_movies = db.table("movies").select("id, title, poster_url, language, release_date").order("created_at", desc=True).limit(limit).execute()
            
            popular_items = [{
                "item_id": m["id"],
                "item_type": "movie",
                "title": m["title"],
                "poster_url": m["poster_url"],
                "avg_rating": None,
                "rating_count": 0
            } for m in recent_movies.data]
            
            return {"popular_items": popular_items, "method": "recent_items"}
        
        return {"popular_items": result.data, "method": "popularity_based"}
    except Exception as e:
        logger.error(f"Popular items error: {e}")
        # Last resort: return some recent movies
        try:
            recent_movies = db.table("movies").select("id, title, poster_url, language").order("created_at", desc=True).limit(limit).execute()
            popular_items = [{
                "item_id": m["id"],
                "item_type": "movie",
                "title": m["title"],
                "poster_url": m["poster_url"]
            } for m in recent_movies.data]
            return {"popular_items": popular_items, "method": "fallback"}
        except:
            return {"popular_items": [], "method": "error"}

# ==================== MOVIE/BOOK ENDPOINTS ====================

@app.get("/movies/{movie_id}")
async def get_movie(movie_id: str, include_details: bool = False):
    """Get movie details, optionally with cast/crew/genres from TMDB"""
    db = get_db()
    result = db.table("movies").select("*").eq("id", movie_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    movie = result.data[0]
    
    # If include_details is True, fetch additional data from TMDB
    if include_details and movie.get("tmdb_id"):
        try:
            tmdb_api_key = os.getenv("TMDB_API_KEY")
            if tmdb_api_key:
                # Fetch movie details from TMDB
                tmdb_url = f"https://api.themoviedb.org/3/movie/{movie['tmdb_id']}"
                params = {
                    "api_key": tmdb_api_key,
                    "append_to_response": "credits"
                }
                response = requests.get(tmdb_url, params=params, timeout=5)
                
                if response.status_code == 200:
                    tmdb_data = response.json()
                    
                    # Add genres
                    movie["genres"] = [g["name"] for g in tmdb_data.get("genres", [])]
                    
                    # Add cast (top 10)
                    credits = tmdb_data.get("credits", {})
                    cast = credits.get("cast", [])[:10]
                    movie["cast"] = [{
                        "name": c.get("name"),
                        "character": c.get("character"),
                        "profile_path": f"https://image.tmdb.org/t/p/w185{c['profile_path']}" if c.get("profile_path") else None
                    } for c in cast]
                    
                    # Add crew (director, writer, producer)
                    crew = credits.get("crew", [])
                    movie["crew"] = {
                        "directors": [c["name"] for c in crew if c.get("job") == "Director"],
                        "writers": [c["name"] for c in crew if c.get("department") == "Writing"][:3],
                        "producers": [c["name"] for c in crew if c.get("job") == "Producer"][:3]
                    }
                    
                    # Add runtime, budget, revenue
                    movie["runtime"] = tmdb_data.get("runtime")
                    movie["budget"] = tmdb_data.get("budget")
                    movie["revenue"] = tmdb_data.get("revenue")
                    movie["vote_average"] = tmdb_data.get("vote_average")
                    movie["vote_count"] = tmdb_data.get("vote_count")
                else:
                    logger.error(f"TMDB API error for movie {movie['tmdb_id']}: {response.status_code}")
        except Exception as e:
            logger.error(f"TMDB fetch error: {e}")
            # Continue without TMDB data
    
    return movie

@app.get("/books/{book_id}")
async def get_book(book_id: str):  # UUID as string
    """Get book details"""
    db = get_db()
    result = db.table("books").select("*").eq("id", book_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Book not found")
    return result.data[0]

@app.get("/movies")
async def list_movies(skip: int = 0, limit: int = 20):
    """List movies with pagination"""
    db = get_db()
    result = db.table("movies").select("*").range(skip, skip + limit - 1).execute()
    return {"movies": result.data, "skip": skip, "limit": limit}

@app.get("/books")
async def list_books(skip: int = 0, limit: int = 20):
    """List books with pagination"""
    db = get_db()
    result = db.table("books").select("*").range(skip, skip + limit - 1).execute()
    return {"books": result.data, "skip": skip, "limit": limit}

if __name__ == "__main__":
    import uvicorn
    # Using environment variables for port to support Koyeb
    port = int(os.getenv("PORT", 8000))
    # CRITICAL: We set workers=1 and limit concurrency to save RAM
    uvicorn.run(
        "api.main:app", 
        host="0.0.0.0", 
        port=port, 
        workers=1, 
        limit_concurrency=10,
        loop="asyncio"
    )
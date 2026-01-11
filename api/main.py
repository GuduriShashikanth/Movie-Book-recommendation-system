import os
import requests
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Configuration
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 
# Get a free token from huggingface.co to avoid rate limits
HF_TOKEN = os.getenv("HF_TOKEN", "") 

# Initialize Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Supabase credentials missing!")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# 2. Initialize FastAPI
app = FastAPI(title="CineLibre ML API - Production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_embedding(text: str):
    """
    Calls Hugging Face Inference API to get 384-dim embeddings.
    This replaces local model loading to save 500MB+ of RAM.
    """
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    
    # Retry logic for the API warming up on Hugging Face's side
    for i in range(3):
        try:
            response = requests.post(api_url, headers=headers, json={"inputs": text}, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503: # Model is currently loading
                time.sleep(5)
                continue
            else:
                print(f"HF API Error: {response.status_code} - {response.text}")
                break
        except Exception as e:
            print(f"Embedding Request Error: {e}")
            time.sleep(1)
    return None

@app.get("/")
async def health_check():
    """Health status endpoint for Koyeb monitoring"""
    return {
        "status": "online", 
        "mode": "Lightweight-Inference",
        "database": "connected" if supabase else "error",
        "engine": "v1.2-Stable"
    }

@app.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=3), 
    type: str = "movie", 
    limit: int = 12,
    threshold: float = 0.4 
):
    """
    Search for Indian movies or books using natural language meaning.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Backend configuration error: Supabase not connected.")
    
    try:
        # Step 1: Get semantic vector from Hugging Face
        query_vector = get_embedding(q)
        if not query_vector:
            raise HTTPException(status_code=503, detail="AI Engine is busy. Please try again in a few seconds.")

        # Step 2: Choose RPC function based on content type
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # Step 3: Query Supabase pgvector
        response = supabase.rpc(rpc_function, {
            "query_embedding": query_vector,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        
        return {
            "query": q, 
            "type": type, 
            "results": response.data
        }
    except Exception as e:
        print(f"Semantic Search Error: {e}")
        raise HTTPException(status_code=500, detail="Search engine encountered an internal error.")

@app.get("/recommendations/content/{item_id}")
async def get_content_recommendations(item_id: str, type: str = "movie", limit: int = 10):
    """
    Finds items similar to a specific movie/book by fetching its existing vector.
    """
    try:
        table = "movies" if type == "movie" else "books"
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # 1. Fetch the source item's pre-calculated embedding
        item = supabase.table(table).select("embedding").eq("id", item_id).single().execute()
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found in database.")
            
        # 2. Find nearest neighbors using the vector
        response = supabase.rpc(rpc_function, {
            "query_embedding": item.data['embedding'],
            "match_threshold": 0.5,
            "match_count": limit + 1
        }).execute()
        
        # Filter out the item itself from the results
        results = [r for r in response.data if str(r['id']) != item_id]
        
        return {"source_id": item_id, "recommendations": results[:limit]}
        
    except Exception as e:
        print(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations/hybrid/{user_id}")
async def get_hybrid_recommendations(user_id: str, limit: int = 10):
    """
    Placeholder for Hybrid Logic (Phase 3 of TRD).
    Currently defaults to 'Content-Based' based on user's last liked item.
    """
    try:
        # Fetch user's most recent positive interaction
        last_like = supabase.table("interactions")\
            .select("item_id, item_type")\
            .eq("user_id", user_id)\
            .eq("interaction_type", "like")\
            .order("created_at", desc=True)\
            .limit(1).execute()
        
        if not last_like.data:
            # Fallback for new users: Trending/Latest movies
            res = supabase.table("movies").select("*").order("release_date", desc=True).limit(limit).execute()
            return {"user_id": user_id, "mode": "cold-start", "recommendations": res.data}
        
        # Get content similar to their last like
        return await get_content_recommendations(
            item_id=last_like.data[0]['item_id'], 
            type=last_like.data[0]['item_type'], 
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # PORT is provided by Koyeb
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
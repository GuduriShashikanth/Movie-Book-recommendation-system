import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# 1. Configuration
# This loads the variables from a .env file for local development
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 

# Validation to provide a cleaner error message if variables are missing
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing SUPABASE_URL or SUPABASE_KEY. "
        "Ensure you have a .env file in your project root or set these environment variables."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Initialize FastAPI
app = FastAPI(title="CineLibre ML API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Load ML Model
print("Loading Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

@app.get("/")
async def health_check():
    return {"status": "online", "message": "CineLibre Engine is healthy"}

@app.get("/search/semantic")
async def semantic_search(q: str, type: str = "movie", limit: int = 10):
    """
    Search using natural language.
    Now calls the 'match_movies' or 'match_books' RPC functions in Supabase.
    """
    try:
        # Convert search query into a vector
        query_vector = model.encode(q).tolist()
        
        # Decide which Postgres function to call
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # Call the RPC function (Remote Procedure Call)
        response = supabase.rpc(rpc_function, {
            "query_embedding": query_vector,
            "match_threshold": 0.4, # Adjust this for strictness
            "match_count": limit
        }).execute()
        
        return {"query": q, "type": type, "results": response.data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations/content/{item_id}")
async def get_content_recommendations(item_id: str, type: str = "movie"):
    """
    Finds items similar to a specific movie/book by getting its vector first.
    """
    try:
        table = "movies" if type == "movie" else "books"
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # 1. Get the source item's embedding
        item = supabase.table(table).select("embedding").eq("id", item_id).single().execute()
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found")
            
        # 2. Find similar items using the same RPC logic
        response = supabase.rpc(rpc_function, {
            "query_embedding": item.data['embedding'],
            "match_threshold": 0.5,
            "match_count": 10
        }).execute()
        
        # Filter out the source item from its own recommendations
        results = [r for r in response.data if r['id'] != item_id]
        
        return {"source_id": item_id, "recommendations": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
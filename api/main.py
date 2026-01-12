import os
import requests
import time
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv

# Set up logging for better debugging in Koyeb
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Configuration
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 
HF_TOKEN = os.getenv("HF_TOKEN", "") 

# Initialize Supabase with a safety check
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Supabase Initialization Error: {e}")
else:
    logger.error("CRITICAL: SUPABASE_URL or SUPABASE_KEY is missing from environment variables.")

# 2. Initialize FastAPI
app = FastAPI(title="CineLibre ML API - Production Ready")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_embedding(text: str):
    """
    Calls Hugging Face Inference API for embeddings with aggressive retry logic.
    Handles '503 Service Unavailable' by waiting for the model to warm up.
    """
    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    
    # Increased to 7 retries for a total possible wait time of ~90 seconds
    for i in range(7):
        try:
            # wait_for_model: True tells HF to try and load it before responding
            # timeout: 45s gives the model more time to finish initialization
            response = requests.post(
                api_url, 
                headers=headers, 
                json={"inputs": text, "options": {"wait_for_model": True}}, 
                timeout=45
            )
            
            if response.status_code == 200:
                vector = response.json()
                
                # Logic to flatten nested arrays (HF often returns [[[...]]] for token embeddings)
                if isinstance(vector, list):
                    while len(vector) > 0 and isinstance(vector[0], list):
                        vector = vector[0]
                    return vector
                return vector
            
            elif response.status_code == 503:
                # Exponential backoff: 5s, 10s, 15s, 20s...
                wait_time = (i + 1) * 5
                logger.info(f"AI Engine warming up (Attempt {i+1}/7). Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"HF API Error: {response.status_code} - {response.text}")
                break
        except Exception as e:
            logger.error(f"Embedding Request Error on attempt {i+1}: {e}")
            time.sleep(2)
            
    return None

@app.get("/")
async def health_check():
    """Health status endpoint for Koyeb monitoring"""
    return {
        "status": "online", 
        "database": "connected" if supabase else "error",
        "ai_auth": "token_present" if HF_TOKEN else "no_token_warning",
        "environment": "production"
    }

@app.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=3), 
    type: str = "movie", 
    limit: int = 12,
    threshold: float = 0.4 
):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase connection not established.")
    
    # Step 1: Get semantic vector
    query_vector = get_embedding(q)
    
    if not query_vector:
        token_msg = " Ensure HF_TOKEN is correctly set in Koyeb." if not HF_TOKEN else ""
        raise HTTPException(
            status_code=533, # Custom code to indicate AI specifically is busy
            detail=f"The AI engine is currently waking up. Please refresh in 15 seconds.{token_msg}"
        )

    # Step 2: Query Supabase using RPC
    rpc_function = "match_movies" if type == "movie" else "match_books"
    
    try:
        response = supabase.rpc(rpc_function, {
            "query_embedding": query_vector,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        
        return {"query": q, "type": type, "results": response.data}
    
    except Exception as e:
        logger.error(f"Search Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal search error: {str(e)}")

@app.get("/recommendations/content/{item_id}")
async def get_content_recommendations(item_id: str, type: str = "movie", limit: int = 10):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not connected.")
    try:
        table = "movies" if type == "movie" else "books"
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        item = supabase.table(table).select("embedding").eq("id", item_id).single().execute()
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found.")
            
        response = supabase.rpc(rpc_function, {
            "query_embedding": item.data['embedding'],
            "match_threshold": 0.5,
            "match_count": limit + 1
        }).execute()
        
        results = [r for r in response.data if str(r['id']) != item_id]
        return {"source_id": item_id, "recommendations": results[:limit]}
    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, log_level="info")
import os
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Set up logging for production debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Configuration
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2. Initialize ML Model (Local Inference)
# This replaces the Hugging Face API calls. 
# It loads the 80MB model directly into your server's RAM.
logger.info("Loading Local ML Model (all-MiniLM-L6-v2)...")
try:
    # We force CPU usage to stay within memory limits
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    logger.info("ML Model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load ML Model: {e}")
    model = None

# 3. Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connection established.")
    except Exception as e:
        logger.error(f"Supabase Connection Error: {e}")

# 4. Initialize FastAPI
app = FastAPI(title="CineLibre ML API - Local Inference Mode")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Verify system status and memory health"""
    return {
        "status": "online",
        "engine": "Local-Inference",
        "model_loaded": model is not None,
        "database": "connected" if supabase else "error"
    }

@app.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=3), 
    type: str = "movie", 
    limit: int = 12,
    threshold: float = 0.4 
):
    if not model:
        raise HTTPException(status_code=503, detail="ML Model is still loading into RAM.")
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection missing.")
    
    try:
        # Step 1: Generate Embedding Locally
        # This is 100% reliable as it doesn't depend on external AI APIs
        logger.info(f"Generating local embedding for query: {q}")
        query_vector = model.encode(q).tolist()

        # Step 2: Query Supabase using pgvector
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
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
        logger.error(f"Search Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/recommendations/content/{item_id}")
async def get_content_recommendations(item_id: str, type: str = "movie", limit: int = 10):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not connected.")
    try:
        table = "movies" if type == "movie" else "books"
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # Fetch the pre-existing vector from the database
        item = supabase.table(table).select("embedding").eq("id", item_id).single().execute()
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found.")
            
        response = supabase.rpc(rpc_function, {
            "query_embedding": item.data['embedding'],
            "match_threshold": 0.5,
            "match_count": limit + 1
        }).execute()
        
        # Remove the source item itself from recommendations
        results = [r for r in response.data if str(r['id']) != item_id]
        return {"source_id": item_id, "recommendations": results[:limit]}
    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    # Note: Use 'api.main:app' as a string for production workers
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, log_level="info")
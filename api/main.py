import os
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from fastembed import TextEmbedding
from dotenv import load_dotenv

# 1. Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Configuration
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 3. Initialize FastEmbed (ONNX-powered Local Inference)
# This model is small (~80MB) and very memory efficient.
logger.info("Initializing FastEmbed Model...")
try:
    # This automatically downloads the model into the local cache
    model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    logger.info("FastEmbed initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize FastEmbed: {e}")
    model = None

# 4. Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connection established.")
    except Exception as e:
        logger.error(f"Supabase Init Error: {e}")

# 5. Initialize FastAPI
app = FastAPI(title="CineLibre ML API - FastEmbed Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """System status and health monitoring"""
    return {
        "status": "online",
        "engine": "FastEmbed-ONNX",
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
    if not model or not supabase:
        raise HTTPException(status_code=500, detail="System not fully initialized.")
    
    try:
        # Step 1: Generate Embedding Locally
        # FastEmbed expects a list of strings, returns a generator
        logger.info(f"Generating embedding for query: {q}")
        query_embeddings = list(model.embed([q]))
        query_vector = query_embeddings[0].tolist()

        # Step 2: Vector Search via Supabase RPC
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
        logger.error(f"Search Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations/content/{item_id}")
async def get_content_recommendations(item_id: str, type: str = "movie", limit: int = 10):
    """Find items similar to a specific movie or book"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not connected.")
    
    try:
        table = "movies" if type == "movie" else "books"
        rpc_function = "match_movies" if type == "movie" else "match_books"
        
        # 1. Fetch the vector of the current item
        item = supabase.table(table).select("embedding").eq("id", item_id).single().execute()
        if not item.data:
            raise HTTPException(status_code=404, detail="Item not found.")
            
        # 2. Match similar vectors
        response = supabase.rpc(rpc_function, {
            "query_embedding": item.data['embedding'],
            "match_threshold": 0.5,
            "match_count": limit + 1
        }).execute()
        
        # Filter out the source item from the results
        results = [r for r in response.data if str(r['id']) != item_id]
        return {"source_id": item_id, "recommendations": results[:limit]}
    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Use environment PORT or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port)
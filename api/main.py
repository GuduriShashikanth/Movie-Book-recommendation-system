import os

# --- CRITICAL MEMORY LIMITS (MUST BE AT TOP) ---
# This stops the AI engine from spawning extra threads that steal RAM
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["ONNXRUNTIME_ENABLE_TELEMETRY"] = "0"

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

# 4. Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connected.")
    except Exception as e:
        logger.error(f"Supabase Init Error: {e}")

# 5. FastAPI App
app = FastAPI(title="CineLibre ML API - Nano Instance Optimized")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Health check triggers model loading if not already loaded"""
    m = get_model()
    return {
        "status": "online",
        "engine": "FastEmbed",
        "ready": m is not None,
        "database": "connected" if supabase else "error"
    }

@app.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=3), 
    type: str = "movie", 
    limit: int = 12,
    threshold: float = 0.4 
):
    m = get_model()
    if not m or not supabase:
        raise HTTPException(status_code=500, detail="System initializing...")
    
    try:
        # Generate embedding (list format for Supabase)
        query_embeddings = list(m.embed([q]))
        query_vector = query_embeddings[0].tolist()

        rpc_function = "match_movies" if type == "movie" else "match_books"
        response = supabase.rpc(rpc_function, {
            "query_embedding": query_vector,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        
        return {"query": q, "results": response.data}
    except Exception as e:
        logger.error(f"Search Error: {e}")
        raise HTTPException(status_code=500, detail="Search processing failed.")

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
"""
GeoMemo API — Geopolitical Intelligence Platform
Main application entry point. Routes are organized into modular routers.
"""
import logging
import requests

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import Groq
from sentence_transformers import SentenceTransformer

from config import UPLOAD_DIR, BEEHIIV_API_KEY, BEEHIIV_PUB_ID
from database import init_db
from models import NewsletterSignup
from routers import articles, content, sources

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Load ML Models ---
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Embedding model 'all-MiniLM-L6-v2' loaded successfully.")
except Exception as e:
    logger.critical(f"Failed to load SentenceTransformer model: {e}")
    raise e

try:
    groq_client = Groq()
except Exception as e:
    logger.critical(f"Failed to initialize Groq client: {e}. Make sure GROQ_API_KEY is set.")

# --- Initialize shared models in article router ---
articles.init_models(embedding_model, groq_client)

# --- FastAPI App ---
app = FastAPI(title="GeoMemo API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Database ---
init_db()

# --- Include Routers ---
app.include_router(articles.router)
app.include_router(content.router)
app.include_router(sources.router)


# --- Newsletter Signup (Beehiiv) ---
@app.post("/api/subscribe")
def subscribe_newsletter(signup: NewsletterSignup):
    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        logger.error("Beehiiv credentials not configured.")
        raise HTTPException(status_code=500, detail="Server configuration error.")
    url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/subscriptions"
    payload = {
        "email": signup.email,
        "reactivate_existing": False,
        "send_welcome_email": True,
        "utm_source": "geomemo_website",
        "custom_fields": [
            {"name": "Company", "value": signup.company},
            {"name": "Title", "value": signup.title},
            {"name": "My field is", "value": signup.field},
        ],
    }
    if signup.first_name:
        payload["custom_fields"].append({"name": "First Name", "value": signup.first_name})
    if signup.last_name:
        payload["custom_fields"].append({"name": "Last Name", "value": signup.last_name})
    headers = {
        "Authorization": f"Bearer {BEEHIIV_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return {"message": "Subscribed successfully"}
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 422:
            return JSONResponse(status_code=409, content={"detail": "Already subscribed."})
        raise HTTPException(status_code=400, detail="Failed to subscribe.")


# --- Health Check ---
@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


# --- Static File Mounts (must be LAST — catch-all routes) ---
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")
app.mount("/", StaticFiles(directory="public_site", html=True), name="public_site")

"""
GeoMemo API — Geopolitical Intelligence Platform
Main application entry point. Routes are organized into modular routers.
"""
import logging
import threading
import time
import requests

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import Groq
from sentence_transformers import SentenceTransformer

from config import UPLOAD_DIR, BEEHIIV_API_KEY, BEEHIIV_PUB_ID, DRIP_INTERVAL_MINUTES, CORS_ORIGINS
from auth import BasicAuthMiddleware, SecurityHeadersMiddleware
from database import init_db
from models import NewsletterSignup
from routers import articles, content, sources, newsletter, social, events

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
newsletter.init_models(groq_client)
sources.init_models(groq_client)
social.init_queue_groq(groq_client)
events.init_models(groq_client)

# --- FastAPI App ---
app = FastAPI(title="GeoMemo API", version="2.0.0")

# --- Middleware Stack (order matters: last added = outermost = runs first) ---
# 1. CORS — must be outermost to handle OPTIONS preflight before auth
# 2. Auth — checks credentials for admin/write endpoints
# 3. Security Headers — injects protective headers into every response

app.add_middleware(SecurityHeadersMiddleware)               # innermost
app.add_middleware(BasicAuthMiddleware)                      # middle
app.add_middleware(                                          # outermost
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# --- Initialize Database ---
init_db()

# --- Include Routers ---
app.include_router(articles.router)
app.include_router(content.router)
app.include_router(sources.router)
app.include_router(newsletter.router)
app.include_router(social.router)
app.include_router(events.router)


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


# --- M6: Background Article Drip Feed ---
def _drip_feed_loop():
    """
    Drip feed approved articles to Telegram every DRIP_INTERVAL_MINUTES.
    Only posts during configured posting hours (default 7AM-10PM ET).
    Posts 1 article per cycle to keep the channel active throughout the day.
    """
    interval_seconds = DRIP_INTERVAL_MINUTES * 60
    while True:
        time.sleep(interval_seconds)
        try:
            from services.social.breaking_news import drip_feed_articles
            result = drip_feed_articles()
            if result.get("articles_posted", 0) > 0:
                logger.info(f"Drip feed: {result['articles_posted']} article(s) posted")
            elif result.get("skipped_reason"):
                logger.debug(f"Drip feed skipped: {result['skipped_reason']}")
        except Exception as e:
            logger.error(f"Drip feed background error: {e}")


def _queue_processor_loop():
    """
    Process the social posting queue every 30 minutes.
    Posts one queued item per cycle (oldest first).
    """
    QUEUE_INTERVAL = 30 * 60  # 30 minutes
    while True:
        time.sleep(QUEUE_INTERVAL)
        try:
            from database import get_db_connection
            import psycopg2.extras
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            cursor.execute("""
                SELECT * FROM social_queue
                WHERE status = 'queued'
                ORDER BY queued_at ASC
                LIMIT 1
            """)
            item = cursor.fetchone()
            if not item:
                cursor.close()
                conn.close()
                continue

            item = dict(item)
            try:
                social._post_queue_item(item, cursor, conn)
                logger.info(f"Queue worker: posted item {item['id']} to {item['platform']}")
            except Exception as post_err:
                logger.error(f"Queue worker: failed to post item {item['id']}: {post_err}")

            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Queue processor error: {e}")


@app.on_event("startup")
def start_background_workers():
    """Start background threads on app startup."""
    # Drip feed thread
    thread = threading.Thread(target=_drip_feed_loop, daemon=True)
    thread.start()
    logger.info(f"Article drip feed started ({DRIP_INTERVAL_MINUTES}-minute interval, posts during ET business hours)")

    # Queue processor thread
    queue_thread = threading.Thread(target=_queue_processor_loop, daemon=True)
    queue_thread.start()
    logger.info("Social queue processor started (30-minute interval)")


# --- Static File Mounts (must be LAST — catch-all routes) ---
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")
app.mount("/", StaticFiles(directory="public_site", html=True), name="public_site")

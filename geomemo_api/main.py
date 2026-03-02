import psycopg2
import requests
import json
import logging
import re
import os
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from psycopg2.extras import execute_values
from groq import Groq
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
import psycopg2.extras
from bs4 import BeautifulSoup 

# --- Setup Directories ---
UPLOAD_DIR = Path("uploaded_images")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Load models ---
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logging.info("Embedding model 'all-MiniLM-L6-v2' loaded successfully.")
except Exception as e:
    logging.critical(f"Failed to load SentenceTransformer model: {e}")
    raise e

try:
    groq_client = Groq()
except Exception as e:
    logging.getLogger(__name__).critical(f"Failed to initialize Groq client: {e}. Make sure GROQ_API_KEY is set.")
    
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB Config ---
# WARNING: Use Environment Variables in Production
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "database": "postgres",
    "user": "postgres",
    "password": "Quantishh@1979" 
}

# --- Beehiiv Config ---
BEEHIIV_API_KEY = "P437ZJlqL1FaUkd0x8Xa9WqEqI2jm8iKsqfeVs2UpgSG5MqJp6Z65EUmeLbYBlZh"
BEEHIIV_PUB_ID = "pub_df6b5792-3b00-48d2-b01b-20c93d653e8e"

# --- Models (Pydantic) ---
class StatusUpdate(BaseModel):
    status: str
class BatchStatusUpdate(BaseModel):
    ids: List[int]
    status: str
class CategoryUpdate(BaseModel):
    category: str
class ManualArticleSubmission(BaseModel):
    headline: str
    url: str
    author: Optional[str] = None
    publication_name: Optional[str] = None
    content: str
    is_top_story: bool = False
class EnhanceRequest(BaseModel):
    summary: str  
    publication_name: Optional[str] = None
    author: Optional[str] = None
class Article(BaseModel):
    id: int
    url: str
    headline_original: str | None = None
    headline: str | None = None
    summary: str | None = None
    category: str | None = None
    status: str
    publication_name: str | None = None
    author: str | None = None
    scraped_at: datetime | None = None
    distance: Optional[float] = None
    is_top_story: bool = False
    parent_id: Optional[int] = None
    confidence_score: Optional[int] = 0
class TweetSubmission(BaseModel):
    url: str 
    content: Optional[str] = None 
    author: Optional[str] = None
class Tweet(BaseModel):
    id: int
    content: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime
class Sponsor(BaseModel):
    id: int
    company_name: str
    headline: str
    summary: str
    link_url: str
    logo_url: str
    created_at: datetime
class Podcast(BaseModel):
    id: int
    show_name: str
    episode_title: str
    description: str
    link_url: str
    image_url: str
    created_at: datetime
class ClusterAnalysisRequest(BaseModel):
    original_article_id: int
    cluster_ids: List[int]
    make_top_story: bool = False
class ClusterAnalysisResponse(BaseModel):
    new_summary: str
    approved_id: int
    parent_id: int
    child_ids: List[int]
    is_top_story: bool
class NewsletterSignup(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: str
    title: str
    field: str
class ScrapeRequest(BaseModel):
    url: str

# --- DB Connection & Setup ---
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        
        # --- FIX 1: Force AI Vector Extension to load FIRST ---
        cursor = conn.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        cursor.close()
        
        register_vector(conn)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Tweets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                url TEXT,
                author TEXT,
                image_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        # Sponsors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sponsors (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT NOT NULL,
                link_url TEXT NOT NULL,
                logo_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        # Podcasts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS podcasts (
                id SERIAL PRIMARY KEY,
                show_name TEXT NOT NULL,
                episode_title TEXT NOT NULL,
                description TEXT NOT NULL,
                link_url TEXT NOT NULL,
                image_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Ensure Articles table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                headline TEXT,
                headline_en TEXT,
                summary TEXT,
                category TEXT,
                publication_name TEXT,
                author TEXT,
                status TEXT DEFAULT 'pending',
                scraped_at TIMESTAMPTZ DEFAULT NOW(),
                is_top_story BOOLEAN DEFAULT FALSE,
                embedding vector(384),
                confidence_score INTEGER DEFAULT 0,
                parent_id INTEGER
            );
        """)
        
        # Migrations
        try: cursor.execute("ALTER TABLE tweets ADD COLUMN IF NOT EXISTS image_url TEXT")
        except: conn.rollback()
        
        try: cursor.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS parent_id INTEGER")
        except: conn.rollback()

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Init DB error: {e}")
    finally:
        cursor.close()
        conn.close()

init_db()

# --- Categories ---
VALID_CATEGORIES = [
    'Geopolitical Conflict', 'Geopolitical Economics', 'Global Markets',
    'Geopolitical Politics', 'GeoNatDisaster', 'GeoLocal', 'Other'
]
VALID_CATEGORIES_SET = set(VALID_CATEGORIES)

# --- Helper: Call Groq ---
def call_groq(headline: str, content: str) -> dict:
    system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
The user is manually submitting an article. Categorize it and return a valid JSON object:
{{"headline_en": "...", "summary": "...", "category": "..."}}
"""
    user_prompt = f"Headline: \"{headline}\"\nContent Snippet: \"{content}\""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model="llama-3.3-70b-versatile", temperature=0.0, response_format={"type": "json_object"}
        )
        processed_data = json.loads(chat_completion.choices[0].message.content)
        processed_data['headline_en'] = processed_data.get('headline_en', headline)
        processed_data['summary'] = processed_data.get('summary', 'No summary provided.')
        processed_data['category'] = processed_data.get('category', 'Other')
        if processed_data['category'] not in VALID_CATEGORIES_SET:
            processed_data['category'] = 'Other'
        return processed_data
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Groq error: {e}")

# --- Helper: URL Metadata Scraper ---
def fetch_url_metadata(url: str) -> dict:
    # 1. YOUTUBE
    if "youtube.com" in url or "youtu.be" in url:
        try:
            video_id = None
            match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if match: video_id = match.group(1)
            if video_id:
                image_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                oe_res = requests.get(oembed_url, timeout=5)
                title = ""; site_name = "YouTube"; description = ""
                if oe_res.status_code == 200:
                    data = oe_res.json()
                    title = data.get("title", ""); author = data.get("author_name", "")
                    site_name = f"YouTube: {author}"; description = title 
                return {"title": title, "description": description, "image_url": image_url, "site_name": site_name}
        except Exception as e: logger.warning(f"YouTube scrape failed: {e}")

    # 2. APPLE PODCASTS
    if "podcasts.apple.com" in url:
        try:
            match = re.search(r'id(\d+)', url)
            if match:
                pod_id = match.group(1)
                api_url = f"https://itunes.apple.com/lookup?id={pod_id}"
                res = requests.get(api_url, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('resultCount', 0) > 0:
                        result = data['results'][0]
                        image_url = result.get('artworkUrl600') or result.get('artworkUrl100')
                        show_name = result.get('collectionName', 'Apple Podcasts')
                        title = result.get('trackName') or show_name 
                        return {"title": title, "description": show_name, "image_url": image_url, "site_name": "Apple Podcasts"}
        except Exception as e: logger.warning(f"Apple scrape failed: {e}")

    # 3. GENERIC
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        
        def get_meta(prop):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return tag["content"] if tag else ""

        title = get_meta("og:title") or (soup.title.string if soup.title else "")
        description = get_meta("og:description") or get_meta("description")
        image_url = get_meta("og:image") or get_meta("twitter:image")
        site_name = get_meta("og:site_name")
        
        return {"title": title, "description": description, "image_url": image_url, "site_name": site_name}
    except Exception as e:
        logger.error(f"Generic scrape error for {url}: {e}")
        return None

# --- Helper: Scrape Tweet ---
def scrape_tweet_meta(url: str):
    try:
        match = re.search(r'/status/(\d+)', url)
        if not match: return None
        tweet_id = match.group(1)
        
        response = requests.get(f"https://api.fxtwitter.com/i/status/{tweet_id}", timeout=10)
        if response.status_code != 200: return None
        data = response.json()
        
        tweet_data = data.get('tweet', {})
        text = tweet_data.get('text', '')
        
        author_info = tweet_data.get('author', {})
        author = author_info.get('name', 'X User')
        if author_info.get('screen_name'): author += f" (@{author_info.get('screen_name')})"
        
        image_url = None
        media = tweet_data.get('media', {})
        
        if media.get('photos'): 
            image_url = media['photos'][0].get('url')
        elif media.get('videos'):
            image_url = media['videos'][0].get('thumbnail_url')
        
        # Fallback: External Link Image
        if not image_url:
            urls = re.findall(r'https?://\S+', text)
            for link in urls:
                meta = fetch_url_metadata(link)
                if meta and meta.get('image_url'):
                    image_url = meta['image_url']
                    break 

        return {"content": text, "image_url": image_url, "author": author}
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return None

# --- Helper: Save Uploaded File ---
def save_upload_file(upload_file: UploadFile) -> str:
    try:
        file_path = UPLOAD_DIR / f"{int(datetime.now().timestamp())}_{upload_file.filename}"
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return f"/uploads/{file_path.name}"
    except Exception as e:
        logger.error(f"File save error: {e}")
        return None

@app.post("/api/scrape-metadata")
def scrape_generic_metadata(request: ScrapeRequest):
    data = fetch_url_metadata(request.url)
    if not data:
        raise HTTPException(400, "Failed to fetch metadata")
    return data

# --- API Endpoints ---

@app.get("/articles", response_model=List[Article])
def get_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: 
        # --- CHANGED: Only fetch last 7 days ---
        cursor.execute("""
            SELECT id, url, headline AS headline_original, headline_en AS headline, 
            summary, category, status, publication_name, author, scraped_at, 
            is_top_story, confidence_score, parent_id 
            FROM articles 
            WHERE scraped_at >= NOW() - INTERVAL '7 days'
            ORDER BY scraped_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e: 
        logger.error(f"Fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally: 
        cursor.close()
        conn.close()

# --- NEW: Archive Route ---
@app.get("/articles/archive", response_model=List[Article])
def get_archived_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: 
        # Fetches older articles (limit 500)
        cursor.execute("""
            SELECT id, url, headline AS headline_original, headline_en AS headline, 
            summary, category, status, publication_name, author, scraped_at, 
            is_top_story, confidence_score, parent_id 
            FROM articles 
            WHERE scraped_at < NOW() - INTERVAL '7 days'
            ORDER BY scraped_at DESC
            LIMIT 500
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e: 
        logger.error(f"Archive fetch error: {e}")
        raise HTTPException(500, "DB Error")
    finally: 
        cursor.close()
        conn.close()

@app.get("/articles/approved", response_model=List[Article])
def get_approved_articles():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: 
        # --- FIX 2: Only fetch the most recent batch of news! No more midnight blanks. ---
        cursor.execute("""
            WITH LatestBatch AS (
                SELECT MAX(scraped_at::date) as max_date 
                FROM articles 
                WHERE status = 'approved'
            )
            SELECT id, url, headline AS headline_original, headline_en AS headline, 
            summary, category, status, publication_name, author, scraped_at, 
            is_top_story, confidence_score, parent_id 
            FROM articles 
            WHERE status = 'approved' 
            AND scraped_at::date = (SELECT max_date FROM LatestBatch)
            ORDER BY is_top_story DESC, scraped_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e: 
        logger.error(f"Fetch approved error: {e}")
        raise HTTPException(500, "DB Error")
    finally: 
        cursor.close()
        conn.close()

@app.post("/articles/manual-submission", status_code=201)
def manual_article_submission(article: ManualArticleSubmission):
    try:
        processed = call_groq(article.headline, article.content)
        text_to_embed = f"Headline: {article.headline}\nSummary: {article.content}"
        embed = embedding_model.encode(text_to_embed).tolist()
        conn = get_db_connection(); cursor = conn.cursor()
        pub_name = article.publication_name if article.publication_name and article.publication_name.strip() else "Manual"
        auth_name = article.author if article.author and article.author.strip() else None
        cursor.execute("""
            INSERT INTO articles (url, headline, publication_name, author, headline_en, summary, category, status, scraped_at, embedding, is_top_story) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s) RETURNING id
        """, (article.url, article.headline, pub_name, auth_name, processed['headline_en'], processed['summary'], processed['category'], embed, article.is_top_story))
        nid = cursor.fetchone()[0]; conn.commit()
        return {"message": "Saved", "article_id": nid}
    except Exception as e: logger.error(f"Manual error: {e}"); raise HTTPException(500, f"Error: {e}")
    finally: 
        if 'cursor' in locals(): cursor.close(); conn.close()

@app.post("/articles/{article_id}/enhance")
def enhance_article_summary(article_id: int, request: EnhanceRequest):
    text_input = request.summary
    if not text_input: raise HTTPException(400, "No text provided")
    
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "Summarize/Rewrite this headline/content for a professional news feed in 50 words. English only."}, {"role": "user", "content": text_input}],
            model="llama-3.3-70b-versatile", temperature=0.1
        )
        new_summary = chat.choices[0].message.content.strip()
        
        conn = get_db_connection(); cursor = conn.cursor()
        
        embedding = embedding_model.encode(new_summary).tolist()
        
        sql = "UPDATE articles SET summary = %s, embedding = %s, status = 'pending'"
        params = [new_summary, embedding]
        
        if request.publication_name and request.publication_name.strip():
            sql += ", publication_name = %s"; params.append(request.publication_name)
        if request.author and request.author.strip():
            sql += ", author = %s"; params.append(request.author)
            
        sql += " WHERE id = %s"; params.append(article_id)
        cursor.execute(sql, tuple(params)); conn.commit(); cursor.close(); conn.close()
        return {"message": "Enhanced", "new_summary": new_summary}
    except Exception as e: logger.error(f"Enhance error: {e}"); raise HTTPException(500, f"Error: {e}")

@app.post("/sponsors", status_code=201)
async def add_sponsor(company_name: str = Form(...), headline: str = Form(...), summary: str = Form(...), link_url: str = Form(...), logo_url: Optional[str] = Form(None), logo_file: UploadFile = File(None)):
    final_logo = logo_url
    if logo_file:
        saved_path = save_upload_file(logo_file)
        if saved_path: final_logo = saved_path
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("INSERT INTO sponsors (company_name, headline, summary, link_url, logo_url) VALUES (%s, %s, %s, %s, %s)", (company_name, headline, summary, link_url, final_logo)); conn.commit(); return {"message": "Sponsor added"}
    except Exception as e: conn.rollback(); raise HTTPException(500, str(e))
    finally: cursor.close(); conn.close()

@app.get("/sponsors", response_model=List[Sponsor])
def get_sponsors():
    conn = get_db_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: cursor.execute("SELECT * FROM sponsors ORDER BY created_at DESC"); return [dict(row) for row in cursor.fetchall()]
    finally: cursor.close(); conn.close()

@app.delete("/sponsors/{id}")
def delete_sponsor(id: int):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM sponsors WHERE id = %s", (id,)); conn.commit(); return {"message": "Deleted"}
    finally: cursor.close(); conn.close()

@app.post("/podcasts", status_code=201)
async def add_podcast(show_name: str = Form(...), episode_title: str = Form(...), description: str = Form(...), link_url: str = Form(...), image_url: Optional[str] = Form(None), image_file: UploadFile = File(None)):
    final_image = image_url
    if image_file:
        saved_path = save_upload_file(image_file)
        if saved_path: final_image = saved_path
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("INSERT INTO podcasts (show_name, episode_title, description, link_url, image_url) VALUES (%s, %s, %s, %s, %s)", (show_name, episode_title, description, link_url, final_image)); conn.commit(); return {"message": "Podcast added"}
    except Exception as e: conn.rollback(); raise HTTPException(500, str(e))
    finally: cursor.close(); conn.close()

@app.get("/podcasts", response_model=List[Podcast])
def get_podcasts():
    conn = get_db_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: cursor.execute("SELECT * FROM podcasts ORDER BY created_at DESC"); return [dict(row) for row in cursor.fetchall()]
    finally: cursor.close(); conn.close()

@app.delete("/podcasts/{id}")
def delete_podcast(id: int):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM podcasts WHERE id = %s", (id,)); conn.commit(); return {"message": "Deleted"}
    finally: cursor.close(); conn.close()

@app.post("/tweets", status_code=201)
def post_tweet(tweet: TweetSubmission):
    conn = get_db_connection(); cursor = conn.cursor()
    content = tweet.content; author = tweet.author; image = None
    if tweet.url and (not content or content.strip() == ""):
        scraped = scrape_tweet_meta(tweet.url)
        if scraped: content = scraped['content']; author = scraped['author']; image = scraped['image_url']
        else: content = tweet.url; author = "Link"
    try: cursor.execute("INSERT INTO tweets (content, url, author, image_url) VALUES (%s, %s, %s, %s) RETURNING id", (content, tweet.url, author, image)); nid = cursor.fetchone()[0]; conn.commit(); return {"message": "Posted", "id": nid}
    except Exception as e: conn.rollback(); raise HTTPException(500, str(e))
    finally: cursor.close(); conn.close()

@app.get("/tweets", response_model=List[Tweet])
def get_tweets():
    conn = get_db_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try: cursor.execute("SELECT id, content, url, image_url, author, created_at FROM tweets ORDER BY created_at DESC LIMIT 50"); return [dict(row) for row in cursor.fetchall()]
    finally: cursor.close(); conn.close()

@app.delete("/tweets/{tweet_id}")
def delete_tweet(tweet_id: int):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM tweets WHERE id = %s", (tweet_id,)); conn.commit(); return {"message": "Deleted"}
    finally: cursor.close(); conn.close()

@app.post("/articles/{article_id}/toggle-top")
def toggle_top_story(article_id: int):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("UPDATE articles SET is_top_story = NOT is_top_story WHERE id = %s RETURNING is_top_story", (article_id,)); conn.commit(); new_state = cursor.fetchone()[0]; return {"message": "Updated", "is_top_story": new_state}
    except Exception as e: conn.rollback(); logger.error(f"Toggle top error: {e}"); raise HTTPException(500, "DB Error")
    finally: cursor.close(); conn.close()

@app.get("/articles/{article_id}/similar", response_model=List[Article])
def get_similar_articles(article_id: int):
    conn = get_db_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT embedding, scraped_at, category FROM articles WHERE id = %s", (article_id,))
        target = cursor.fetchone()
        if not target: raise HTTPException(404, "Not found")
        cursor.execute("""
            SELECT id, url, headline AS headline_original, headline_en AS headline, summary, category, status, publication_name, author, scraped_at, is_top_story, parent_id,
            embedding <=> %s AS distance 
            FROM articles WHERE id != %s AND embedding IS NOT NULL AND scraped_at::date = %s::date AND category = %s
            ORDER BY distance ASC LIMIT 5
        """, (target['embedding'], article_id, target['scraped_at'], target['category']))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e: logger.error(f"Sim error: {e}"); raise HTTPException(500, "DB Error")
    finally: cursor.close(); conn.close()

@app.post("/cluster/approve", response_model=ClusterAnalysisResponse)
async def analyze_and_approve_cluster(request: ClusterAnalysisRequest):
    original_id = request.original_article_id; cluster_ids = request.cluster_ids
    conn = get_db_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        all_ids = [original_id] + cluster_ids
        q_placeholders = ','.join(['%s'] * len(all_ids))
        cursor.execute(f"SELECT id, headline_en, summary, publication_name, url FROM articles WHERE id IN ({q_placeholders})", tuple(all_ids))
        articles = {row['id']: dict(row) for row in cursor.fetchall()}
        
        txt = ""; orig = articles.get(original_id, {}); txt += f"--- MAIN ---\nHead: {orig.get('headline_en')}\nSum: {orig.get('summary')}\n\n"
        for i, aid in enumerate(cluster_ids): 
            rel = articles.get(aid, {}); txt += f"--- REL {i+1} ---\nHead: {rel.get('headline_en')}\nSum: {rel.get('summary')}\n\n"
            
        chat = groq_client.chat.completions.create(messages=[{"role": "system", "content": "Synthesize these into a cohesive summary. Return HTML <p>...</p> only."}, {"role": "user", "content": txt}], model="llama-3.3-70b-versatile", temperature=0.2)
        new_sum = chat.choices[0].message.content
        
        cursor.execute("UPDATE articles SET status = 'approved', summary = %s, is_top_story = %s WHERE id = %s", (new_sum, request.make_top_story, original_id))
        
        if cluster_ids:
            child_ph = ','.join(['%s'] * len(cluster_ids))
            cursor.execute(f"UPDATE articles SET status = 'approved', parent_id = %s WHERE id IN ({child_ph})", (original_id, *cluster_ids))
            
        conn.commit()
        return ClusterAnalysisResponse(new_summary=new_sum, approved_id=original_id, parent_id=original_id, child_ids=cluster_ids, is_top_story=request.make_top_story)
    except Exception as e: conn.rollback(); raise HTTPException(500, str(e))
    finally: cursor.close(); conn.close()

@app.post("/articles/{article_id}/status")
def update_article_status(article_id: int, status_update: StatusUpdate):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("UPDATE articles SET status = %s WHERE id = %s", (status_update.status, article_id)); conn.commit()
    except Exception as e: conn.rollback(); raise HTTPException(500, "DB Error")
    finally: cursor.close(); conn.close(); return {"message": "Updated"}

@app.post("/articles/{article_id}/category")
def update_article_category(article_id: int, category_update: CategoryUpdate):
    conn = get_db_connection(); cursor = conn.cursor()
    try: cursor.execute("UPDATE articles SET category = %s WHERE id = %s", (category_update.category, article_id)); conn.commit()
    except Exception as e: conn.rollback(); raise HTTPException(500, "DB Error")
    finally: cursor.close(); conn.close(); return {"message": "Updated"}

@app.post("/articles/batch-update")
def batch_update_article_status(update_data: BatchStatusUpdate):
    conn = get_db_connection(); cursor = conn.cursor()
    try: execute_values(cursor, "UPDATE articles SET status = data.status FROM (VALUES %s) AS data(status, id) WHERE articles.id = data.id", [(update_data.status, aid) for aid in update_data.ids]); conn.commit()
    except Exception as e: conn.rollback(); raise HTTPException(500, str(e))
    finally: cursor.close(); conn.close(); return {"message": "Batch updated"}

@app.post("/api/subscribe")
def subscribe_newsletter(signup: NewsletterSignup):
    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        logger.error("Beehiiv credentials not configured.")
        raise HTTPException(status_code=500, detail="Server configuration error.")
    url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/subscriptions"
    payload = {"email": signup.email, "reactivate_existing": False, "send_welcome_email": True, "utm_source": "geomemo_website", 
               "custom_fields": [{"name": "Company", "value": signup.company}, {"name": "Title", "value": signup.title}, {"name": "My field is", "value": signup.field}]}
    if signup.first_name: payload["custom_fields"].append({"name": "First Name", "value": signup.first_name})
    if signup.last_name: payload["custom_fields"].append({"name": "Last Name", "value": signup.last_name})
    headers = {"Authorization": f"Bearer {BEEHIIV_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status(); return {"message": "Subscribed successfully"}
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 422: return JSONResponse(status_code=409, content={"detail": "Already subscribed."})
        raise HTTPException(status_code=400, detail="Failed to subscribe.")

app.mount("/uploads", StaticFiles(directory="uploaded_images"), name="uploads")
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")
# Assuming public_site folder exists for the front facing website
app.mount("/", StaticFiles(directory="public_site", html=True), name="public_site")

"""
Content management endpoints: tweets, sponsors, podcasts.
Also includes URL metadata scraping helpers.
"""
import os
import re
import uuid
import logging
import shutil
from typing import List, Optional
from datetime import datetime
from pathlib import Path

import requests
import psycopg2.extras
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from bs4 import BeautifulSoup

from database import get_db_connection
from config import UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_MIME_TYPES, ALLOWED_EXTENSIONS
from models import (
    Tweet, TweetSubmission, Sponsor, Podcast, ScrapeRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Helpers ---

def fetch_url_metadata(url: str) -> dict:
    """Scrape metadata from YouTube, Apple Podcasts, or generic URLs."""
    # YouTube
    if "youtube.com" in url or "youtu.be" in url:
        try:
            match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if match:
                video_id = match.group(1)
                image_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                oe_res = requests.get(oembed_url, timeout=5)
                title = ""
                site_name = "YouTube"
                description = ""
                if oe_res.status_code == 200:
                    data = oe_res.json()
                    title = data.get("title", "")
                    author = data.get("author_name", "")
                    site_name = f"YouTube: {author}"
                    description = title
                return {"title": title, "description": description, "image_url": image_url, "site_name": site_name}
        except Exception as e:
            logger.warning(f"YouTube scrape failed: {e}")

    # Apple Podcasts
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
        except Exception as e:
            logger.warning(f"Apple scrape failed: {e}")

    # Generic OG scraping
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
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


def scrape_tweet_meta(url: str):
    """Scrape tweet content/image via fxtwitter API."""
    try:
        match = re.search(r'/status/(\d+)', url)
        if not match:
            return None
        tweet_id = match.group(1)
        response = requests.get(f"https://api.fxtwitter.com/i/status/{tweet_id}", timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        tweet_data = data.get('tweet', {})
        text = tweet_data.get('text', '')
        author_info = tweet_data.get('author', {})
        author = author_info.get('name', 'X User')
        if author_info.get('screen_name'):
            author += f" (@{author_info.get('screen_name')})"

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


def save_upload_file(upload_file: UploadFile) -> str:
    """
    Save an uploaded file with security checks. Returns URL path or None.

    Security measures:
      - MIME type validation (images only)
      - File extension validation
      - 5 MB size limit
      - UUID-based filenames (prevents path traversal)
    """
    try:
        # 1. Validate MIME type
        content_type = (upload_file.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"Upload rejected: invalid MIME type '{content_type}'")
            return None

        # 2. Validate file extension
        original_name = upload_file.filename or "file"
        ext = os.path.splitext(original_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"Upload rejected: invalid extension '{ext}'")
            return None

        # 3. Read file with size limit
        contents = upload_file.file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            logger.warning(f"Upload rejected: file too large ({len(contents)} bytes, limit {MAX_UPLOAD_SIZE})")
            return None

        # 4. Safe filename — UUID + original extension (no user path components)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / safe_name

        with file_path.open("wb") as buffer:
            buffer.write(contents)

        return f"/uploads/{safe_name}"
    except Exception as e:
        logger.error(f"File save error: {e}")
        return None


# --- Metadata Scraping ---

@router.post("/api/scrape-metadata")
def scrape_generic_metadata(request: ScrapeRequest):
    data = fetch_url_metadata(request.url)
    if not data:
        raise HTTPException(400, "Failed to fetch metadata")
    return data


# --- Sponsors ---

@router.post("/sponsors", status_code=201)
async def add_sponsor(
    company_name: str = Form(...),
    headline: str = Form(...),
    summary: str = Form(...),
    link_url: str = Form(...),
    logo_url: Optional[str] = Form(None),
    logo_file: UploadFile = File(None),
):
    final_logo = logo_url
    if logo_file:
        saved_path = save_upload_file(logo_file)
        if saved_path:
            final_logo = saved_path
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sponsors (company_name, headline, summary, link_url, logo_url) VALUES (%s, %s, %s, %s, %s)",
            (company_name, headline, summary, link_url, final_logo),
        )
        conn.commit()
        return {"message": "Sponsor added"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/sponsors", response_model=List[Sponsor])
def get_sponsors():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM sponsors ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.delete("/sponsors/{id}")
def delete_sponsor(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM sponsors WHERE id = %s", (id,))
        conn.commit()
        return {"message": "Deleted"}
    finally:
        cursor.close()
        conn.close()


# --- Podcasts ---

@router.post("/podcasts", status_code=201)
async def add_podcast(
    show_name: str = Form(...),
    episode_title: str = Form(...),
    description: str = Form(...),
    link_url: str = Form(...),
    image_url: Optional[str] = Form(None),
    image_file: UploadFile = File(None),
    video_url: Optional[str] = Form(None),
):
    final_image = image_url
    if image_file:
        saved_path = save_upload_file(image_file)
        if saved_path:
            final_image = saved_path
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO podcasts (show_name, episode_title, description, link_url, image_url, video_url) VALUES (%s, %s, %s, %s, %s, %s)",
            (show_name, episode_title, description, link_url, final_image, video_url),
        )
        conn.commit()
        return {"message": "Podcast added"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/podcasts", response_model=List[Podcast])
def get_podcasts():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM podcasts ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.delete("/podcasts/{id}")
def delete_podcast(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM podcasts WHERE id = %s", (id,))
        conn.commit()
        return {"message": "Deleted"}
    finally:
        cursor.close()
        conn.close()


# --- Tweets ---

@router.post("/tweets", status_code=201)
def post_tweet(tweet: TweetSubmission):
    conn = get_db_connection()
    cursor = conn.cursor()
    content = tweet.content
    author = tweet.author
    image = None
    if tweet.url and (not content or content.strip() == ""):
        scraped = scrape_tweet_meta(tweet.url)
        if scraped:
            content = scraped['content']
            author = scraped['author']
            image = scraped['image_url']
        else:
            content = tweet.url
            author = "Link"
    try:
        cursor.execute(
            "INSERT INTO tweets (content, url, author, image_url) VALUES (%s, %s, %s, %s) RETURNING id",
            (content, tweet.url, author, image),
        )
        nid = cursor.fetchone()[0]
        conn.commit()
        return {"message": "Posted", "id": nid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        cursor.close()
        conn.close()


@router.get("/tweets", response_model=List[Tweet])
def get_tweets():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT id, content, url, image_url, author, created_at FROM tweets ORDER BY created_at DESC LIMIT 50")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


@router.delete("/tweets/{tweet_id}")
def delete_tweet(tweet_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tweets WHERE id = %s", (tweet_id,))
        conn.commit()
        return {"message": "Deleted"}
    finally:
        cursor.close()
        conn.close()

import os
import psycopg2
import requests
from dotenv import load_dotenv
from datetime import datetime

# --- Load Environment Variables ---
load_dotenv()

BEEHIIV_API_KEY = os.getenv("BEEHIIV_API_KEY")
BEEHIIV_PUBLICATION_ID = os.getenv("BEEHIIV_PUBLICATION_ID")

# --- ADD THESE DEBUG LINES ---
# This will print the exact values being read from your .env file
print(f"DEBUG: API Key Loaded: '{BEEHIIV_API_KEY}'")
print(f"DEBUG: Publication ID Loaded: '{BEEHIIV_PUBLICATION_ID}'")
# ---------------------------

# --- Database Configuration ---
# !! IMPORTANT: Make sure this password is correct !!
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "Quantishh@1979" 
}

# --- Main Functions ---

def get_approved_articles():
    """Fetches all 'approved' articles from the database."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT headline, url, summary FROM articles WHERE status = 'approved' ORDER BY scraped_at DESC")
        articles = cursor.fetchall()
        
        cursor.close()
        return articles
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching articles: {error}")
        return []
    finally:
        if conn is not None:
            conn.close()

def create_email_html(articles):
    """Formats a list of articles into a simple HTML email body."""
    if not articles:
        return "<p>No new articles this week. Stay tuned for our next edition!</p>"

    html_content = ""
    for headline, url, summary in articles:
        html_content += f"""
        <div style="margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #eeeeee;">
            <h2 style="font-size: 20px; margin-bottom: 8px;">
                <a href="{url}" target="_blank" style="text-decoration: none; color: #1a0dab;">{headline}</a>
            </h2>
            <p style="font-size: 16px; color: #333333; margin-top: 0;">{summary}</p>
        </div>
        """
    return html_content

def create_beehiiv_post(title, html_content):
    """Creates a new post in Beehiiv as a draft."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUBLICATION_ID:
        print("Error: Beehiiv API Key or Publication ID is not set in the .env file.")
        return

    url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUBLICATION_ID}/posts"
    
    headers = {
        "Authorization": f"Bearer {BEEHIIV_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": title,
        "content_html": html_content,
        "status": "draft",
        "show_in_feed": True,
        "email_subject_line": title,
        "platform_share_title": title,
        "platform_share_description": "Your weekly briefing on global geopolitics and market trends."
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print("Successfully created draft post in Beehiiv!")
        print(f"Post ID: {response.json()['data']['id']}")
    except requests.exceptions.RequestException as e:
        print(f"Error creating Beehiiv post: {e}")
        print(f"Response Body: {e.response.text if e.response else 'No response'}")

# --- Script Execution ---
if __name__ == "__main__":
    print("Starting newsletter script...")
    
    approved_articles = get_approved_articles()
    
    if approved_articles:
        print(f"Found {len(approved_articles)} approved articles.")
        email_body = create_email_html(approved_articles)
        today_date = datetime.now().strftime("%B %d, %Y")
        post_title = f"GeoMemo: Your Weekly Briefing for {today_date}"
        create_beehiiv_post(post_title, email_body)
    else:
        print("No approved articles found. No post will be created.")
        
    print("Newsletter script finished.")
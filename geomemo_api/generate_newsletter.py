import psycopg2
import psycopg2.extras
from datetime import datetime
import os

# --- DB Config ---
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "Quantishh@1979" 
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def generate_html():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    print("Fetching today's news...")
    cursor.execute("""
        SELECT * FROM articles 
        WHERE status = 'approved' 
        AND scraped_at::date = CURRENT_DATE
        ORDER BY is_top_story DESC, scraped_at DESC
    """)
    articles = cursor.fetchall()
    conn.close()

    if not articles:
        print("No approved articles found for today!")
        return

    # Grouping Logic
    top_stories = [a for a in articles if a['is_top_story']]
    other_stories = [a for a in articles if not a['is_top_story']]
    categories = {}
    valid_cats = ['Geopolitical Conflict', 'Geopolitical Economics', 'Geopolitical Politics', 'Global Markets', 'GeoNatDisaster', 'GeoLocal']
    
    for a in other_stories:
        cat = a['category'] if a['category'] in valid_cats else 'Other'
        if cat not in categories: categories[cat] = []
        categories[cat].append(a)

    # --- STYLE CONFIGURATION ---
    # Fonts: Calibri first, fallback to Helvetica/Arial
    FONT_STACK = "'Calibri', 'Segoe UI', Helvetica, Arial, sans-serif"
    
    # 4. Start Building HTML
    # width: 100% ensures mobile responsiveness. max-width keeps it readable on desktop.
    html = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: {FONT_STACK}; color: #111111; margin: 0; padding: 0; background-color: #ffffff;">
        
        <div style="max-width: 600px; width: 100%; margin: 0 auto; padding: 20px;">
        
            <div style="border-bottom: 2px solid #eeeeee; padding-bottom: 15px; margin-bottom: 30px;">
                <span style="font-size: 24px; font-weight: 800; color: #430297; letter-spacing: -0.5px; text-transform: uppercase;">GeoMemo</span>
                <br>
                <span style="color: #666; font-size: 13px; font-weight: 400;">Daily Intelligence • {datetime.now().strftime("%B %d, %Y")}</span>
            </div>
    """

    # Helper to format one item
    def format_item(a):
        # Logic to handle cluster lists vs standard summaries
        text = a['summary'] if a['summary'] else a['headline']
        cluster_html = ""
        
        # Handle Clusters
        if "<ul>" in text:
            # Extract the main summary text (before the UL)
            if "<p>" in text:
                # If it's formatted with P tags, grab the first P
                import re
                match = re.search(r'<p>(.*?)</p>', text)
                main_text = match.group(1) if match else a['headline']
            else:
                # Fallback: split by UL
                main_text = text.split("<ul>")[0]

            # Format the Cluster Items
            ul_content = text.split("<ul>")[1].split("</ul>")[0]
            
            # 1. Style the links inside the cluster items (The Sources)
            # Green, Bold
            ul_content = ul_content.replace("<a ", "<a style='color:#5cb85c; font-weight:700; text-decoration:none;' ")
            
            # 2. Style the list items (The Cluster Text)
            # Removed &bull; per request. Just a clean div with margin.
            ul_content = ul_content.replace("<li>", "<div style='margin-bottom:8px; font-weight:300; font-size:13px; color:#333; line-height:1.4;'>").replace("</li>", "</div>")
            
            cluster_html = f"<div style='margin-top:8px; padding-left:0px;'>{ul_content}</div>"
            text = main_text # Set main text to just the summary line
        
        time_str = a['scraped_at'].strftime("%I:%M %p")
        
        # --- ITEM LAYOUT ---
        return f"""
        <div style="border-bottom: 1px solid #eeeeee; padding-bottom: 15px; margin-bottom: 15px;">
            <div style="display:inline;">
                <a href="{a['url']}" style="color: #1f2937; text-decoration: none; font-weight: 700; font-size: 16px; line-height: 1.3;">
                    {text} 
                </a>
                <span style="color: #888888; font-size: 12px; font-weight: 300; margin-left: 6px;">
                    ({a['publication_name']}) {time_str}
                </span>
            </div>
            {cluster_html}
        </div>
        """

    # 5. Render Top News
    if top_stories:
        html += f"""<div style="color: #b00; font-family: {FONT_STACK}; font-weight: 700; font-size: 14px; border-bottom: 2px solid #b00; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.5px;">Top News</div>"""
        for a in top_stories:
            html += format_item(a)

    # 6. Render Categories in Order
    for cat in valid_cats + ['Other']:
        if cat in categories and categories[cat]:
            html += f"""<div style="color: #b00; font-family: {FONT_STACK}; font-weight: 700; font-size: 14px; border-bottom: 1px solid #dddddd; margin-top: 30px; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.5px;">{cat}</div>"""
            for a in categories[cat]:
                html += format_item(a)

    # 7. Footer
    html += """
            <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #eeeeee; color: #999999; font-size: 11px; text-align: center; line-height: 1.6;">
                &copy; 2025 GeoMemo.<br>
                Briefing the world's decision makers.<br>
                <a href="{{unsubscribe_url}}" style="color: #999; text-decoration: underline;">Unsubscribe</a>
            </div>
        </div> </body>
    </html>
    """

    # 8. Save File
    with open("todays_newsletter.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Success! Generated todays_newsletter.html with {len(articles)} articles.")
    print("OPEN THIS FILE IN BROWSER -> COPY -> PASTE INTO GMAIL/BEEHIIV.")

if __name__ == "__main__":
    generate_html()
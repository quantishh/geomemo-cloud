"""
Author Extraction — extracts author name, email, X handle from article HTML.

Three-layer approach:
  Layer 1: HTML parsing (JSON-LD, meta tags, byline CSS, email/handle regex)
  Layer 2: Groq extraction from full_content text (in scoring pipeline)
  Layer 3: Weekly enrichment (batch lookup from X/Twitter API, publication sites)

This module implements Layer 1 (called during scraping/content fetch).
"""
import re
import json
import logging

logger = logging.getLogger(__name__)


def extract_author_info(html: str, url: str = "") -> dict:
    """
    Extract author metadata from article HTML.
    Returns dict with: name, email, x_handle, bio, linkedin_url
    """
    result = {
        "name": None,
        "email": None,
        "x_handle": None,
        "bio": None,
        "linkedin_url": None,
    }

    if not html:
        return result

    # --- 1. JSON-LD structured data (most reliable) ---
    try:
        ld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE
        )
        for ld_text in ld_matches:
            try:
                ld = json.loads(ld_text.strip())
                # Handle both single object and array
                if isinstance(ld, list):
                    for item in ld:
                        _extract_from_jsonld(item, result)
                else:
                    _extract_from_jsonld(ld, result)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass

    # --- 2. Meta tags ---
    if not result["name"]:
        meta_patterns = [
            r'<meta\s+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\'][^>]+name=["\']author["\']',
            r'<meta\s+property=["\']article:author["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\'][^>]+property=["\']article:author["\']',
        ]
        for pat in meta_patterns:
            match = re.search(pat, html, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if _is_valid_author_name(name):
                    result["name"] = name
                    break

    # --- 3. Byline patterns in HTML ---
    if not result["name"]:
        byline_patterns = [
            # Common byline class/id patterns
            r'class=["\'][^"\']*(?:byline|author-name|article-author|writer)[^"\']*["\'][^>]*>(?:<[^>]*>)*\s*(?:By\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            # "By Name" patterns
            r'<(?:span|div|p|a)[^>]*>\s*By\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*</',
            # rel="author"
            r'rel=["\']author["\'][^>]*>([^<]+)</',
        ]
        for pat in byline_patterns:
            match = re.search(pat, html, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if _is_valid_author_name(name):
                    result["name"] = name
                    break

    # --- 4. Email extraction ---
    if not result["email"]:
        # Look for email addresses, prefer those near author-related context
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, html)
        # Filter out common non-author emails
        skip_domains = {'example.com', 'email.com', 'test.com', 'sentry.io',
                        'google.com', 'facebook.com', 'twitter.com', 'googleapis.com',
                        'w3.org', 'schema.org', 'cloudflare.com'}
        skip_prefixes = {'info@', 'admin@', 'support@', 'contact@', 'noreply@',
                        'webmaster@', 'editor@', 'news@', 'subscribe@', 'feedback@'}
        for email in emails:
            domain = email.split('@')[1].lower()
            if domain in skip_domains:
                continue
            if any(email.lower().startswith(p) for p in skip_prefixes):
                continue
            result["email"] = email
            break

    # --- 5. X/Twitter handle ---
    if not result["x_handle"]:
        twitter_patterns = [
            r'(?:twitter\.com|x\.com)/(@?[A-Za-z0-9_]{1,15})(?:["\s?/]|$)',
            r'@([A-Za-z0-9_]{3,15})\s*(?:on\s+(?:Twitter|X))',
        ]
        for pat in twitter_patterns:
            match = re.search(pat, html)
            if match:
                handle = match.group(1).lstrip('@')
                # Skip publication handles
                skip_handles = {'share', 'intent', 'home', 'search', 'login',
                              'signup', 'settings', 'notifications', 'i'}
                if handle.lower() not in skip_handles and len(handle) >= 3:
                    result["x_handle"] = f"@{handle}"
                    break

    # --- 6. LinkedIn URL ---
    if not result["linkedin_url"]:
        linkedin_match = re.search(
            r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9-]+)',
            html
        )
        if linkedin_match:
            result["linkedin_url"] = linkedin_match.group(0)

    return result


def _extract_from_jsonld(ld: dict, result: dict):
    """Extract author info from a JSON-LD object."""
    if not isinstance(ld, dict):
        return

    author = ld.get('author')
    if not author:
        return

    # Author can be a dict or list
    if isinstance(author, list):
        author = author[0] if author else {}
    if isinstance(author, str):
        if _is_valid_author_name(author):
            result["name"] = author
        return
    if not isinstance(author, dict):
        return

    name = author.get('name', '')
    if name and _is_valid_author_name(name):
        result["name"] = name

    # Some JSON-LD includes email and social
    if author.get('email'):
        result["email"] = author['email']
    for social in author.get('sameAs', []):
        if isinstance(social, str):
            if 'twitter.com' in social or 'x.com' in social:
                handle_match = re.search(r'/([A-Za-z0-9_]+)$', social)
                if handle_match:
                    result["x_handle"] = f"@{handle_match.group(1)}"
            elif 'linkedin.com/in/' in social:
                result["linkedin_url"] = social


def _is_valid_author_name(name: str) -> bool:
    """Check if a string looks like a real person's name."""
    if not name or len(name) < 3 or len(name) > 100:
        return False
    # Skip common non-name values
    skip = {'staff', 'admin', 'editor', 'team', 'correspondent', 'reporter',
            'desk', 'newsroom', 'editorial', 'agency', 'reuters', 'ap', 'afp',
            'bbc', 'cnn', 'staff writer', 'staff reporter', 'the associated press',
            'by', 'from', 'unknown', 'anonymous', 'contributor'}
    if name.lower().strip() in skip:
        return False
    # Should have at least 2 words (first + last name)
    if len(name.split()) < 2:
        return False
    # Should start with a capital letter
    if not name[0].isupper():
        return False
    return True


def store_author(cursor, name: str, publication_name: str = None,
                 email: str = None, x_handle: str = None,
                 linkedin_url: str = None) -> int:
    """
    Upsert author into authors table. Returns author_id.
    Also creates/links entity record for the author.
    """
    if not name or not _is_valid_author_name(name):
        return None

    try:
        cursor.execute("""
            INSERT INTO authors (name, publication_name, email, x_handle, linkedin_url,
                                total_articles, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, 1, NOW())
            ON CONFLICT (LOWER(name), LOWER(COALESCE(publication_name, '')))
            DO UPDATE SET
                total_articles = authors.total_articles + 1,
                last_seen_at = NOW(),
                email = COALESCE(EXCLUDED.email, authors.email),
                x_handle = COALESCE(EXCLUDED.x_handle, authors.x_handle),
                linkedin_url = COALESCE(EXCLUDED.linkedin_url, authors.linkedin_url),
                publications = (
                    SELECT array_agg(DISTINCT pub) FROM unnest(
                        array_append(COALESCE(authors.publications, '{}'), EXCLUDED.publication_name)
                    ) AS pub WHERE pub IS NOT NULL
                )
            RETURNING id
        """, (name, publication_name, email, x_handle, linkedin_url))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.debug(f"Author store failed for '{name}': {e}")
        cursor.connection.rollback()
        return None

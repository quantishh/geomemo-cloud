import scrapy
from geomemo_scraper.items import ArticleItem
import json
from urllib.parse import urlencode
import logging

class NewsapiSpider(scrapy.Spider):
    name = 'newsapi'
    logger = logging.getLogger(__name__)
    
    # Base URL for the NewsAPI 'everything' endpoint
    api_url = 'https://newsapi.org/v2/everything?'

    # Define your search queries based on your categories
    search_keywords = [
        'geopolitics',
        'global security',
        'international relations',
        'global trade',
        'supply chain',
        'global stock market',
        'foreign elections',
        'natural disaster'
    ]

    def start_requests(self):
        api_key = self.settings.get('NEWS_API_KEY')
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            self.logger.error("NEWS_API_KEY not set in settings.py. Spider is stopping.")
            return

        # Correct headers for NewsAPI (use 'X-Api-Key' or 'Authorization')
        # 'Authorization' is preferred for production.
        headers = {'Authorization': f'Bearer {api_key}'}
        
        # Create a request for each keyword
        for keyword in self.search_keywords:
            params = {
                'q': keyword,
                'language': 'en',
                'sortBy': 'publishedAt', # Get the most recent articles
                'pageSize': 100 # Max 100 per request (NewsAPI default)
            }
            query_string = urlencode(params)
            url = self.api_url + query_string
            
            self.logger.info(f"Queueing request for NewsAPI keyword: {keyword}")
            
            # Yield a request for this keyword
            yield scrapy.Request(
                url, 
                headers=headers, 
                callback=self.parse,
                # Pass the keyword for logging purposes
                meta={'keyword': keyword} 
            )

    def parse(self, response):
        keyword = response.meta['keyword']
        self.logger.info(f"Parsing response for keyword: {keyword}")

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON from NewsAPI for keyword: {keyword}")
            return

        if data.get('status') != 'ok':
            self.logger.error(f"NewsAPI returned an error for keyword '{keyword}': {data.get('message')}")
            return

        articles = data.get('articles', [])
        if not articles:
            self.logger.info(f"No articles found for keyword: {keyword}")
            return

        self.logger.info(f"Received {len(articles)} articles for keyword: {keyword}")

        for article in articles:
            item = ArticleItem()
            
            # Map NewsAPI fields to our ArticleItem fields
            item['headline'] = article.get('title')
            item['url'] = article.get('url')
            item['publication_name'] = article.get('source', {}).get('name', 'Unknown Source')
            item['author'] = article.get('author')
            # Use 'description' or 'content' for the summary snippet
            item['description'] = article.get('description') or article.get('content', '')

            # Validate essential fields
            if not item['headline'] or not item['url'] or 'news.google.com' in item['url']:
                self.logger.warning(f"Skipping article, missing headline/URL or is Google redirect: {article.get('title')}")
                continue

            # Send the item to the pipeline
            yield item


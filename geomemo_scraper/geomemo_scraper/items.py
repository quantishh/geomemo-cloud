import scrapy

class ArticleItem(scrapy.Item):
    # Blueprint for a single article.
    url = scrapy.Field()
    headline = scrapy.Field() # The original headline
    publication_name = scrapy.Field()
    author = scrapy.Field()
    
    # --- THIS IS THE FIX ---
    # Add this line to match the spider and pipeline
    description = scrapy.Field() 
    
    # Fields to be filled by the LLM
    headline_en = scrapy.Field() # The translated headline
    summary = scrapy.Field()
    summary_long = scrapy.Field()  # M5: 100-word analytical summary for map layer
    category = scrapy.Field()
    embedding = scrapy.Field()
    confidence_score = scrapy.Field()
    source_id = scrapy.Field()  # Pre-resolved source ID from DB-loaded feeds
    og_image = scrapy.Field()   # OG image URL from RSS media tags or article page
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
    category = scrapy.Field()
    embedding = scrapy.Field()
    confidence_score = scrapy.Field()
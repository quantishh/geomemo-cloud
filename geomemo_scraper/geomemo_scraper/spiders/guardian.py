import scrapy
from geomemo_scraper.items import ArticleItem

class GuardianSpider(scrapy.Spider):
    # The unique name for this spider
    name = 'guardian'
    
    # The list of URLs the spider will start crawling from
    start_urls = [
        'https://www.theguardian.com/world'
    ]

    # This is the main function that Scrapy calls to process the downloaded page
    def parse(self, response):
        """
        This function parses the response from the start_urls, finds all the
        article links, and yields them as structured ArticleItems.
        """
        
        # This is a CSS selector that targets the main story links on the page.
        article_links = response.css('a[data-link-name="article"]')
        
        # We loop through each link that we found
        for article in article_links:
            # We extract the text of the headline from within the a> tag
            headline_text = article.css('::text').get()
            
            # We extract the URL (the 'href' attribute) from the <a> tag
            relative_url = article.attrib['href']
            
            # Create an instance of our structured item blueprint
            item = ArticleItem()
            item['headline'] = headline_text.strip() if headline_text else "No Headline Found"
            item['url'] = response.urljoin(relative_url)
            
            # Yield the structured item to the pipeline
            yield item
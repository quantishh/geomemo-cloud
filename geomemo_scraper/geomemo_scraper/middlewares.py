# geomemo_scraper/geomemo_scraper/middlewares.py
from scrapy.exceptions import NotConfigured

class BrightDataProxyMiddleware:
    
    @classmethod
    def from_crawler(cls, crawler):
        # Read the proxy URL from settings.py
        proxy_url = crawler.settings.get('PROXY_URL')
        if not proxy_url:
            raise NotConfigured("PROXY_URL not found in settings.py")
        return cls(proxy_url)

    def __init__(self, proxy_url):
        self.proxy_url = proxy_url

    def process_request(self, request, spider):
        # Apply the proxy to every request
        request.meta['proxy'] = self.proxy_url
# Scrapy settings for geomemo_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
import logging

BOT_NAME = "geomemo_scraper"

SPIDER_MODULES = ["geomemo_scraper.spiders"]
NEWSPIDER_MODULE = "geomemo_scraper.spiders"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False # Set to False for easier debugging

# Configure maximum concurrent requests performed by Scrapy (default: 16)
# NOTE: Reduced to 8 to improve stability with residential proxies and avoid timeouts.
CONCURRENT_REQUESTS = 8

# Configure a delay for requests for the same website (default: 0)
# NOTE: Increased to 1 second to be more polite to servers and proxies.
DOWNLOAD_DELAY = 1
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
   "Accept-Language": "en",
   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
}

# --- Path Configuration ---
# This file (settings.py) is in geomemo_scraper/geomemo_scraper/
# BASE_DIR is geomemo_scraper/geomemo_scraper/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT is geomemo_scraper/
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# --- NewsAPI.org Configuration ---
# !!! V-V-V  ADD YOUR API KEY HERE V-V-V !!!
NEWS_API_KEY = "5243fc9f81a54faeb8e4ba5795782c1f" 
# !!! A-A-A  ADD YOUR API KEY HERE A-A-A !!!

# --- Bright Data Proxy Settings ---
BRIGHTDATA_USERNAME = 'brd-customer-hl_9363c7cd-zone-residential_proxy1_geomemo' 
BRIGHTDATA_PASSWORD = 'o9g31v2pc6cr'
BRIGHTDATA_HOST = 'brd.superproxy.io'
BRIGHTDATA_PORT = '33335'
PROXY_URL = f'http://{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}'

# --- Path to your SSL certificate ---
# Assumes brightdata_ca.crt is in the project's root folder (next to scrapy.cfg)
BRIGHTDATA_CERT_PATH = os.path.join(PROJECT_ROOT, 'brightdata_ca.crt')
logging.info(f"Calculated BRIGHTDATA_CERT_PATH: {BRIGHTDATA_CERT_PATH}")


# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
   'geomemo_scraper.middlewares.BrightDataProxyMiddleware': 100,
   'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
   'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
   'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550,
   'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
}

# Tell Scrapy to use your custom SSL context factory
DOWNLOADER_CLIENTCONTEXTFACTORY = 'geomemo_scraper.contextfactory.CustomClientContextFactory'


# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   "geomemo_scraper.pipelines.GeomemoDatabasePipeline": 300,
}

LOG_LEVEL = 'INFO'
DOWNLOAD_TIMEOUT = 180 # 3 minutes for slow proxy connections

# Enable and configure the AutoThrottle extension (optional)
#AUTOTHROTTLE_ENABLED = True
#AUTOTHROTTLE_START_DELAY = 5
#AUTOTHROTTLE_MAX_DELAY = 60
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (optional)
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"


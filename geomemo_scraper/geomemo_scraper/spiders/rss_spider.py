import os
import scrapy
import psycopg2
from geomemo_scraper.items import ArticleItem
import re
from parsel import Selector
from lxml.etree import XMLSyntaxError

# We now use the more flexible scrapy.Spider instead of XMLFeedSpider
class RssSpider(scrapy.Spider):
    name = 'rss_spider'
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'
    }

    start_urls = [
        # --- Your Existing RSS Feeds ---
        'http://timesofindia.indiatimes.com/rssfeeds/296589292.cms',
        'https://www.chathamhouse.org/path/whatsnew.xml',
        'https://www.rusi.org/rss/latest-commentary.xml',
        'https://www.rusi.org/rss/latest-publications.xml',
        'https://www.rusi.org/rss/whats-new.xml',
        'http://timesofindia.indiatimes.com/rssfeedstopstories.cms',
        'https://timesofindia.indiatimes.com/rssfeeds_us/72258322.cms',
        'https://www.thehindu.com/news/international/feeder/default.rss',
        'https://www.thehindu.com/business/markets/feeder/default.rss',
        'https://www.thehindu.com/business/Economy/feeder/default.rss',
        'https://www.thehindu.com/rssfeeds/',
        'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',
        # 'https://indianexpress.com/section/india/feed/',
        'https://feeds.feedburner.com/ndtvnews-top-stories',
        'https://feeds.feedburner.com/ndtvnews-world-news',
        'https://en.antaranews.com/rss/news.xml',
        'https://e.vnexpress.net/rss/news.rss',
        'https://www.abc.net.au/news/rural/rss/2011-04-26/rss-feeds/4808396?utm_campaign=abc_news_web&utm_content=link&utm_medium=content_shared&utm_source=abc_news_web',
        'https://www.abc.net.au/news/feed/2942460/rss.xml',
        'https://www.news.com.au/content-feeds/latest-news-national',
        'https://www.9news.com.au/rss',
        'https://www.smh.com.au/rss/feed.xml',
        'https://www.smh.com.au/rss/world.xml',
        'https://www.smh.com.au/rss/politics/federal.xml',
        'https://www.theage.com.au/rss/feed.xml',
        'https://www.theage.com.au/rss/world.xml',
        'https://www.theage.com.au/rss/national.xml',
        'https://www.theage.com.au/rss/politics/federal.xml',
        'https://www.heraldsun.com.au/news/breaking-news/rss',
        'https://www.dailytelegraph.com.au/news/breaking-news/rss',
        'https://www.theguardian.com/australia-news/rss',
        'https://www.sbs.com.au/news/feed',
        'https://www.sbs.com.au/news/topic/world/feed',
        'https://www.canberratimes.com.au/rss.xml',
        'https://www.batimes.com.ar/feed',
        #'https://buenosairesherald.com/the-archives/feed',
        'https://www.batimes.com.ar/feed',
        'https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml',
        'https://feeds.feedburner.com/LaGaceta-General',
        'https://www.eldia.com/.rss',
        'https://www.cronista.com/arc/outboundfeeds/news/',
        'https://www.perfil.com/feed',
        'https://www.lavoz.com.ar/arc/outboundfeeds/feeds/rss/?outputType=xml',
        'https://elintransigente.com/feed/',
        'https://www.cronista.com/files/rss/news.xml',
        'https://www.diarioregistrado.com/rss.xml',
        'https://www.aljazeera.com/xml/rss/all.xml',
        'https://nationalpost.com/feed',
        'https://www.cbc.ca/webfeed/rss/rss-topstories',
        'https://www.ft.com/rss/world',
        'https://www.economist.com/finance-and-economics/rss.xml',
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://www.dailyrecord.co.uk/news/?service=rss',
        'https://www.thesun.co.uk/feed/',
        'https://feeds.skynews.com/feeds/rss/home.xml',
        'https://www.theguardian.com/uk-news/rss',
        'https://www.telegraph.co.uk/rss.xml',
        'https://www.independent.co.uk/rss',
        'https://www.huffingtonpost.co.uk/feeds/index.xml',
        'https://www.politics.co.uk/feed/',
        'https://www.yorkpress.co.uk/news/rss/',
        'https://www.mirror.co.uk/?service=rss',
        'https://www.cityam.com/feed/',
        'https://www.newstatesman.com/feed',
        'https://feeds.thelocal.com/rss/fr',
        'https://mondediplo.com/backend',
        'https://www.mediapart.fr/articles/feed',
        'https://rss.dw.com/rdf/rss-en-top',
        'https://feeds.thelocal.com/rss/de',
        'https://newsfeed.zeit.de/index',
        'https://www.scmp.com/rss/91/feed',
        # 'http://www.xinhuanet.com/english2010/rss/index.htm',
        'https://www.cgtn.com/subscribe/rss/section/china.xml',
        'https://www.cgtn.com/subscribe/rss/section/world.xml',
        'https://www.cgtn.com/subscribe/rss/section/politics.xml',
        'https://www.chinadaily.com.cn/rss/world_rss.xml',
        'https://asia.nikkei.com/rss/feed/nar',
        # 'https://www.japantimes.co.jp/feed/',
        # 'https://english.kyodonews.net/rss/all.xml',
        # 'https://www3.nhk.or.jp/nhkworld/en/news/index.xml',
        'https://www.arabnews.com/rss.xml',
        'https://saudigazette.com.sa/rssFeed/0',
        'https://saudigazette.com.sa/rssFeed/31',
        'https://saudigazette.com.sa/rssFeed/32',
        'https://english.alarabiya.net/feed/rss2/en.xml',
        'https://english.alarabiya.net/feed/rss2/en/business/energy.xml',
        'https://english.alarabiya.net/feed/rss2/en/News.xml',
        'https://gulfnews.com/feed',
        'https://www.emirates247.com/cmlink/rss-feed-1.4268?localLinksEnabled=false',
        'https://www.emaratalyoum.com/1.533091?ot=ot.AjaxPageLayout',
        'https://www.arabianbusiness.com/gcc/uae/feed',
        'https://thearabianpost.com/feed/',
        'https://www.dubaichronicle.com/feed/',
        'https://en.irna.ir/rss',
        'https://www.tehrantimes.com/rss',
        'http://en.mehrnews.com/rss',
        'https://www.tasnimnews.com/en/rss/feed/0/7/0/all-stories',
        'https://www.entekhab.ir/fa/rss/allnews',
        'https://irannewsdaily.com/feed/',
        'https://ifpnews.com/feed/',
        'https://iran-times.com/feed/',
        'https://en.isna.ir/rss',
        'https://en.isna.ir/rss-homepage',
        'https://en.isna.ir/rss/tp/13',
        'https://www.tehrantimes.com/rss/tp/702',
        'https://www.tehrantimes.com/rss/tp/698',
        # 'https://newspaper.irandaily.ir/#rss',
        'http://www.irdiplomacy.ir/fa/news/rss',
        # 'https://www.presstv.ir/RSS/',
        'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
        'https://feeds.washingtonpost.com/rss/world?itid=lk_inline_manual_26',
        # 'https://apnews.com/hub/politics/rssfeed.xml',
        'https://www.politico.com/rss/politicopicks.xml',
        'https://www.bostonherald.com/feed/',
        'https://observer.com/feed/',
        'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
        'https://www.washingtontimes.com/rss/headlines/news',
        'https://www.latimes.com/local/rss2.0.xml',
        'https://www.vox.com/rss/index.xml',
        'https://www.cbsnews.com/',
        # 'https://bhaskar.com/rss-v1--category--national--uid-7629234.xml',
        # 'https://www.amarujala.com/rss/breaking-news.xml',
        'https://api.livehindustan.com/feeds/rss/news-brief/rssfeed.xml',
        'https://rss.tempo.co/nasional',
        'https://vnexpress.net/rss/thoi-su.rss',
        'https://tuoitre.vn/rss/tin-moi-nhat.rss',
        'https://thanhnien.vn/rss/home.rss',
        # 'https://www.teaomaori.news/rss',
        'https://thespinoff.co.nz/feed',
        # 'https://www.rnz.co.nz/news/te-manu-korihi/feed',
        'https://www.waateanews.com/feed/',
        'https://e-tangata.co.nz/feed/',
        # 'https://www.philstar.com/pilipino-star-ngayon/rss',
        # 'https://www.bulgaronline.com/rss.xml',
        # 'https://www.abante.com.ph/feed/',
        'https://data.gmanetwork.com/gno/rss/news/feed.xml',
        'https://balita.mb.com.ph/rssFeed/0/',
        'https://feeds.bbci.co.uk/hausa/rss.xml',
        'https://nnn.ng/category/politics/feed/',
        'https://thenewsguru.ng/category/politics/feed/',
        'https://www.gistlover.com/category/politics/feed/',
        'https://pointblanknews.com/pbn/category/news/feed/',
        'https://independent.ng/category/politics/feed/',
        'https://www.legit.ng/rss/politics.rss',
        #  'https://hausa.legit.ng/rss/index.rss',
        'https://www.rfi.fr/ha/rss',
        # 'https://www.voahausa.com/rss',
        'https://www.egyptindependent.com/feed/',
        'https://www.dailynewsegypt.com/feed/',
        'https://egyptianstreets.com/feed/',
        'https://egyptoil-gas.com/news/feed/',
        'https://ilanganews.co.za/feed/',
        'https://www.almasryalyoum.com/rss/rss.xml',
        'https://www.shorouknews.com/rss',
        'https://www.israelhayom.com/feed/',
        'https://www.haaretz.co.il/cmlink/1.1462502',
        'https://www.clarin.com/rss/lo-ultimo/',
        'https://www.pagina12.com.ar/rss/portada',
        'https://www.infobae.com/feeds/rss/',
        'https://www.ambito.com/rss/home.xml',
        'https://g1.globo.com/rss/g1/',
        'https://www.estadao.com.br/rss/ultimas.xml',
        'https://rss.uol.com.br/feed/geral',
        'https://www.gazetadopovo.com.br/rss/ultimas-noticias/',
        'https://www.lapresse.ca/actualites/rss',
        'https://www.journaldemontreal.com/rss.xml',
        'https://www.ledevoir.com/rss/ledevoir_en_continu.xml',
        'https://ici.radio-canada.ca/rss/4185',
        'https://www.lesoleil.com/actualites/rss',
        'https://www.eltiempo.com/rss/colombia.xml',
        'https://www.elespectador.com/rss.xml',
        'https://www.elpais.com.co/feed/',
        'https://www.elcolombiano.com/c/rss/todas-las-noticias',
        'https://www.eluniversal.com.mx/rss/ultima-hora.xml',
        'https://www.reforma.com/rss/portada.xml',
        'https://www.jornada.com.mx/rss/edicion.xml',
        'https://www.milenio.com/rss/homepage',
        'https://www.excelsior.com.mx/rss.xml',
        'https://www.kathimerini.gr/rss',
        'https://www.tanea.gr/feed/',
        'https://www.tovima.gr/feed/',
        'https://www.protothema.gr/rss/',
        'https://www.efsyn.gr/rss',
        'https://www.tg4.ie/ga/feed/',
        'https://tuairisc.ie/feed/',
        'https://www.okaz.com.sa/rss',
        'https://www.albayan.ae/c/rss',
        'https://www.aletihad.ae/rss',
        'https://ettelaat.com/rss',
        'https://kayhan.ir/fa/rss/allnews',
        'https://www.hamshahrionline.ir/rss',
        'https://www.sharghdaily.com/rss-all',
        'https://www.farsnews.ir/rss',
        'https://www.ft.com/chinese-economy?format=rss',
        'https://www.economist.com/china/rss.xml',
        'https://ecipe.org/category/regions/far-east/feed/',
        'https://www.atlanticcouncil.org/region/china/feed/',
        'https://andrewbatson.com/category/economics/feed/',
        'https://chinaeconomicreview.com/feed/',
        'https://asia.nikkei.com/Economy/East-Asia/China',
        'http://en.mercopress.com/rss/latin-america',
        'http://news.google.com/news?hl=en&amp;q=colombia&amp;ie=UTF-8&amp;output=rss',
        'http://www.elcolombiano.com/rss/Colombia.xml',
        'http://www.globalvoicesonline.org/-/world/americas/feed/',
        'http://www.economist.com/feeds/print-sections/74/international.xml',
        'https://ifpnews.com/feed/',
        'https://irannewsdaily.com/category/technology/feed/',
        'https://foreignpolicy.com/tag/iran/feed/',
        'https://irannewsdaily.com/feed/',
        'https://ifpnews.com/category/news/politics/feed/',
        'https://www.entekhab.ir/fa/rss/allnews',
        'https://en.mehrnews.com/rss',
        'https://www.tasnimnews.com/en/rss/feed/0/7/0/all-stories',
        'https://iranonline.blog/feed/',

        # --- Google News RSS Feeds (TRANSITIONAL) ---
        # These are being migrated to the sources database via the admin dashboard.
        # Once migrated, the scraper picks them up from DB in start_requests().
        # Use POST /api/sources/migrate-google-feeds to perform the migration.
        # After migration is confirmed, these hardcoded entries can be removed.
        'https://news.google.com/rss/search?q=geopolitics+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=international+relations+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=global+economy+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=world+conflict+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=foreign+policy+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=(geopolitical+conflict+OR+war+OR+sanctions+OR+embargo)+AND+(trade+OR+"market+impact"+OR+"supply+chain"+OR+financial+impact)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("climate+change"+OR+"natural+disaster"+OR+drought+OR+flood)+AND+(geopolitics+OR+"economic+impact"+OR+"resource+scarcity"+OR+migration)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("stock+market"+OR+"major+indices"+OR+Sensex+OR+Nifty+OR+Nikkei+OR+Hang+Seng+OR+FTSE+OR+DAX+OR+"ASX+200"+OR+Bovespa+OR+"JSE")+AND+(forecast+OR+performance+OR+outlook)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=(AI+OR+"Artificial+Intelligence")+AND+(labor+OR+displacement+OR+unemployment+OR+"economic+revolution"+OR+regulation)+AND+(geopolitics+OR+global)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("global+economy"+OR+GDP+OR+recession+OR+inflation+OR+"central+bank")+AND+(Asia+OR+India+OR+Europe+OR+"South+America"+OR+Africa+OR+Australia)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("foreign+policy"+OR+"international+relations"+OR+diplomacy)+AND+("United+States"+OR+US)+AND+(impact+OR+implication+OR+effect)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("think+tank"+OR+"policy+brief"+OR+"strategic+analysis")+AND+(geopolitics+OR+global)+when:1d&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=("S%26P+500"+OR+"Nasdaq"+OR+"Dow+Jones"+OR+"Russell+2000"+OR+"TSX+Composite"+OR+"S%26P/TSX"+OR+"IPC+Index")+AND+(forecast+OR+performance+OR+outlook)+when:1d&hl=en-US&gl=US&ceid=US:en',
        # Add more keyword searches as desired
    ]

    def start_requests(self):
        """Load RSS feeds from database (additive), then yield hardcoded feeds as fallback."""
        db_feed_count = 0
        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "db"),
                database=os.getenv("POSTGRES_DB", "postgres"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, rss_feed_url FROM sources "
                "WHERE rss_feed_url IS NOT NULL AND rss_feed_url != ''"
            )
            db_feeds = cursor.fetchall()
            cursor.close()
            conn.close()

            # Track DB feed URLs to avoid duplicates with hardcoded list
            db_urls = set()
            for source_id, source_name, rss_url in db_feeds:
                db_urls.add(rss_url)
                db_feed_count += 1
                yield scrapy.Request(
                    url=rss_url,
                    callback=self.parse,
                    meta={'source_id': source_id, 'source_name': source_name},
                    dont_filter=True,
                )
            self.logger.info(f"Loaded {db_feed_count} RSS feeds from database")

            # Yield hardcoded feeds, skipping any already in DB
            hardcoded_count = 0
            for url in self.start_urls:
                if url not in db_urls:
                    hardcoded_count += 1
                    yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)
            self.logger.info(f"Loaded {hardcoded_count} hardcoded RSS feeds (skipped {len(self.start_urls) - hardcoded_count} duplicates)")

        except Exception as e:
            self.logger.warning(f"DB feed loading failed, falling back to hardcoded feeds only: {e}")
            # Fallback: yield all hardcoded feeds
            for url in self.start_urls:
                yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)
            self.logger.info(f"Loaded {len(self.start_urls)} hardcoded RSS feeds (fallback mode)")

    # The parse method is called for every downloaded response
    def _extract_image_from_node(self, node, node_type):
        """Extract image URL from RSS/Atom item using common media tags."""
        img = None

        # 1. media:content / media:thumbnail (Yahoo Media RSS)
        img = img or node.xpath('media:content/@url').get()
        img = img or node.xpath('media:thumbnail/@url').get()
        img = img or node.xpath('*[local-name()="content"]/@url').get()
        img = img or node.xpath('*[local-name()="thumbnail"]/@url').get()

        # 2. <enclosure> tag (standard RSS)
        if not img:
            enc_type = node.xpath('enclosure/@type').get() or ''
            if 'image' in enc_type:
                img = node.xpath('enclosure/@url').get()
            elif not enc_type:
                # Some feeds have enclosure without type; check URL extension
                enc_url = node.xpath('enclosure/@url').get()
                if enc_url and any(enc_url.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                    img = enc_url

        # 3. <image> child element
        img = img or node.xpath('image/url/text()').get()
        img = img or node.xpath('image/@href').get()

        # 4. Extract from description/content HTML (img src)
        if not img:
            desc_html = node.xpath('description/text()').get() or ''
            if not desc_html and node_type == 'atom':
                desc_html = node.xpath('atom:content/text()').get() or ''
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_html)
            if img_match:
                candidate = img_match.group(1)
                # Filter out tiny tracking pixels and icons
                if not any(skip in candidate.lower() for skip in ['pixel', 'tracking', '1x1', 'beacon', 'spacer', 'logo']):
                    img = candidate

        # Validate: must be a proper URL
        if img and img.startswith('http'):
            return img.strip()
        return None

    def parse(self, response):
        try:
            sel = Selector(text=response.text, type='xml')
            sel.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
            sel.register_namespace('atom', 'http://www.w3.org/2005/Atom')
            sel.register_namespace('media', 'http://search.yahoo.com/mrss/')

        except (XMLSyntaxError, TypeError) as e:
            self.logger.warning(f"Failed to parse XML from {response.url}. Error: {e}. Skipping.")
            return

        # Try to get the overall feed publication name (less relevant for Google News search)
        feed_title = sel.xpath('//channel/title/text()').get() or sel.xpath('//atom:feed/atom:title/text()').get()

        nodes = sel.xpath('//item')
        node_type = 'rss'
        if not nodes:
            nodes = sel.xpath('//atom:entry')
            node_type = 'atom'
            if not nodes: # Try Google News specific <item> without namespace
                 nodes = sel.xpath('/rss/channel/item')


        if not nodes:
            self.logger.warning(f"No <item> or <entry> nodes found in {response.url}. Skipping.")
            return

        for node in nodes:
            item = ArticleItem()

            headline = None
            url = None
            author = None
            publication_name = None # Reset for each item
            description = None # For NewsAPI

            # --- Extract data using XPath ---
            if node_type == 'rss': # Handles standard RSS and Google News RSS <item>
                headline = node.xpath('title/text()').get()
                url = node.xpath('link/text()').get()
                guid = node.xpath('guid/text()').get()
                guid_is_permalink = node.xpath('guid/@isPermaLink').get()
                description = node.xpath('description/text()').get()
                # Google News often puts the real URL in <guid>
                if not url or "news.google.com" in url: # If link is missing or is a Google redirect
                    if guid and guid.startswith('http') and guid_is_permalink != 'false':
                        url = guid # Use the GUID as the primary URL
                author = node.xpath('dc:creator/text()').get()
                # --- Google News Specific Source Extraction ---
                # Google News puts the source publication in <source> or sometimes <dc:publisher>
                publication_name = node.xpath('source/text()').get() or node.xpath('dc:publisher/text()').get()


            else: # Atom (<entry>) - Google News doesn't typically use Atom for search results
                headline = node.xpath('atom:title/text()').get()
                url = node.xpath("atom:link[@rel='alternate']/@href").get() # More specific Atom link
                author = node.xpath('.//atom:author/atom:name/text()').get()
                description = node.xpath('atom:summary/text()').get() or node.xpath('atom:content/text()').get()
                # Atom feeds might have source info differently, add if needed
                # publication_name = node.xpath('...').get() # Add specific Atom source path if found

            # --- Clean and Validate ---
            headline = headline.strip() if headline else None
            if headline:
                headline = re.sub(r'<[^>]+>', '', headline)

            description = description.strip() if description else None
            if description:
                description = re.sub(r'<[^>]+>', '', description) # Clean stray HTML

            url = url.strip() if url else None
            author = author.strip() if author else None
            publication_name = publication_name.strip() if publication_name else None

            # Essential data check
            if not headline or not url or not url.startswith('http'):
                self.logger.debug(f"Skipping item from {response.url} - Missing headline/URL.")
                continue

            # --- Load Item ---
            item['headline'] = headline
            item['url'] = url
            # Use specific publication name if found, else fallback to feed title or URL
            item['publication_name'] = publication_name or (feed_title.strip() if feed_title else response.url)
            item['author'] = author
            item['description'] = description # Pass description to pipeline

            # Extract image from RSS media tags
            item['og_image'] = self._extract_image_from_node(node, node_type)

            # Pass source_id from DB-loaded feeds (avoids re-lookup in pipeline)
            if response.meta.get('source_id'):
                item['source_id'] = response.meta['source_id']

            yield item
import psycopg2
import json
import re
import urllib.request
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import logging
import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from psycopg2 import InternalError

# Optional: pycountry for ISO country code resolution
try:
    import pycountry
except ImportError:
    pycountry = None
    logging.warning("pycountry not installed. Country code resolution will be skipped.")

# --- Non-English source name → English display name mapping ---
# Exact matches for full strings found in the DB, plus partial matches for variations
SOURCE_NAME_MAP = {
    # === EXACT MATCHES (full publication_name as stored in DB) ===
    # Persian / Farsi (Iran)
    'پایگاه خبری تحلیلی انتخاب | Entekhab.ir': 'Entekhab',
    'اطلاعات آنلاین': 'Ettela\'at Online',
    'همشهری آنلاین، سایت خبری روزنامه همشهری | hamshahrionline': 'Hamshahri Online',
    'همشهری آنلاین': 'Hamshahri Online',
    'روزنامه همشهری': 'Hamshahri',
    'آخرین اخبار | خبرگزاری تسنیم | Tasnim': 'Tasnim News Agency',
    'آخرین اخبار, اخبار روز | خبرگزاری تسنیم | Tasnim': 'Tasnim News Agency',
    'تسنیم': 'Tasnim News Agency',
    'ایسنا': 'ISNA',
    'فارس': 'Fars News Agency',
    'ایرنا': 'IRNA',
    'مهر': 'Mehr News Agency',
    'کیهان': 'Kayhan',
    'ایران اینترنشنال': 'Iran International',
    'صدا و سیما': 'IRIB',
    'فرهیختگان': 'Farhikhtegan',
    'شفقنا': 'Shafaqna',
    'باشگاه خبرنگاران جوان': 'Young Journalists Club',
    'خبرآنلاین': 'Khabar Online',
    'نورنیوز': 'Nour News',
    'میزان': 'Mizan News',
    'جوان': 'Javan',
    'مشرق': 'Mashregh News',
    'ایران': 'Iran Daily',
    'ایلنا': 'ILNA',
    'خبرگزاری برنا': 'BORNA News Agency',
    'خبرگزاری اطلس': 'Atlas News Agency',
    'اخبار': 'Akhbar News',
    'محليات': 'Local News',
    # Arabic (Middle East & North Africa)
    'شفق نيوز': 'Shafaq News',
    'صحيفة مال': 'Mal Newspaper',
    'وزارة الخارجية الإماراتية': 'UAE Foreign Ministry',
    'اسلام تايمز': 'Islam Times',
    'الهيئة العامة للاستعلامات': 'State Information Service',
    'شبكة تواصل الإخبارية': 'Tawasul News',
    'وكالة الأنباء السعودية': 'Saudi Press Agency',
    'وكالة صدى نيوز': 'Sada News Agency',
    'وزارة الخارجية القطرية': 'Qatar Foreign Ministry',
    'صحيفة الأنباط': 'Al-Anbat',
    'وكالة أنباء البحرين': 'Bahrain News Agency',
    'وكالة وام': 'WAM',
    'يمن مونيتور': 'Yemen Monitor',
    'الوكالة الموريتانية للأنباء': 'Mauritanian News Agency',
    'المتداول العربي': 'Arab Trader',
    'الصحيفة': 'Al-Sahifa',
    'صوت الإمارات': 'Voice of UAE',
    'سانا': 'SANA',
    'ارقام': 'Argaam',
    'ارقام : اخبار ومعلومات سوق الأسهم السعودي - تاسي': 'Argaam',
    'موقع عمان نت': 'Amman Net',
    'عالم تسعة': 'Alam Tis3a',
    'مركز الروابط للدراسات الاستراتيجية والسياسية': 'Rawabet Center',
    'مركز المستقبل': 'Future Center',
    'خبرگزاری صدای افغان(آوا)': 'AVA Press',
    # Greek
    'Πρώτο Θέμα: RSS': 'Protothema',
    'Πρώτο Θέμα': 'Protothema',
    'ΤΟ ΒΗΜΑ': 'To Vima',
    'ΒΗΜΑ': 'To Vima',
    'ΤΑ ΝΕΑ': 'Ta Nea',
    'Καθημερινή': 'Kathimerini',
    'Η Εφημερίδα των Συντακτών': 'Efimerida Syntakton',
    # Vietnamese
    'Tuổi Trẻ Online - Tin mới nhất - RSS Feed': 'Tuoi Tre',
    'Tuổi Trẻ Online': 'Tuoi Tre',
    'Báo Thanh Niên': 'Thanh Nien',
    'Thời sự - VnExpress RSS': 'VnExpress',
    'Báo VietNamNet': 'VietNamNet',
    'Thông tấn xã Việt Nam': 'Vietnam News Agency',
    'Việt Báo': 'Viet Bao',
    'BỘ NỘI VỤ': 'Vietnam Ministry of Home Affairs',
    # Turkish
    'Anadolu Ajansı': 'Anadolu Agency',
    'Hürriyet': 'Hurriyet',
    'Hürriyet Daily News': 'Hurriyet Daily News',
    'Yeni Şafak': 'Yeni Safak',
    'Evrim Ağacı': 'Evrim Agaci',
    'Türkiye Today': 'Turkiye Today',
    # German
    'DIE ZEIT | Nachrichten, News, Hintergründe und Debatten': 'Die Zeit',
    'Münchner Sicherheitskonferenz': 'Munich Security Conference',
    # Korean
    '조선일보': 'Chosun Ilbo',
    '매일경제': 'Maeil Business Newspaper',
    '아시아경제': 'Asia Economy',
    '한겨레': 'Hankyoreh',
    '디지털투데이': 'Digital Today',
    '위키리크스한국': 'WikiLeaks Korea',
    '포스코그룹 뉴스룸': 'POSCO Group Newsroom',
    'IT조선': 'IT Chosun',
    # Chinese
    '富途牛牛': 'Futu Moomoo',
    '富途资讯': 'Futu News',
    '新华网': 'Xinhua',
    '香港電台新聞網': 'RTHK News',
    '香港電台': 'RTHK',
    'Rti 中央廣播電臺': 'RTI Taiwan',
    'TVBS新聞網': 'TVBS News',
    '點新聞': 'Dot Dot News',
    '天下雜誌': 'CommonWealth Magazine',
    '中华人民共和国驻大韩民国大使馆': 'Chinese Embassy in South Korea',
    '中国科技网': 'China Science & Tech Net',
    '中安在线': 'Zhongan Online',
    '极目新闻': 'Jimu News',
    '群众新闻网': 'Qunzhong News',
    '荆楚网': 'Jingchu Net',
    '昆明信息港': 'Kunming Info',
    '深潮TechFlow': 'DeepTide TechFlow',
    '公益財団法人日本国際問題研究所': 'JIIA Japan',
    '驻印度大使馆': 'Chinese Embassy in India',
    '驻韩国大使馆': 'Chinese Embassy in South Korea',
    # Japanese
    '朝日新聞': 'Asahi Shimbun',
    '毎日新聞': 'Mainichi Shimbun',
    '沖縄タイムス社': 'Okinawa Times',
    '第一生命経済研究所': 'Dai-ichi Life Research Institute',
    # Ukrainian
    'Букви': 'Bukvy',
    'Українська правда': 'Ukrainska Pravda',
    'Українські Національні Новини (УНН)': 'Ukrainian National News',
    'Українські Національні Новини': 'Ukrainian National News',
    'Українські Новини': 'Ukrainian News',
    'Прямий': 'Pryamiy',
    'Цензор.НЕТ': 'Censor.NET',
    'ТСН': 'TSN',
    # Russian
    'Военное дело': 'Military Affairs',
    'Министерство иностранных дел России': 'Russian Foreign Ministry',
    'Улправда': 'Ulpravda',
    'Геополитика.RU': 'Geopolitika.RU',
    'Акчабар': 'Akchebar',
    'Газета.uz': 'Gazeta.uz',
    'ТопЖир': 'TopZhyr',
    'Азия-Плюс': 'Asia-Plus',
    'сайт ОДКБ': 'CSTO',
    'Святлана Ціханоўская': 'Sviatlana Tsikhanouskaya',
    # Azerbaijani
    'Operativ Məlumat Mərkəzi': 'Operative Information Center',
    'Azərtac': 'AZERTAC',
    # Armenian
    'Այսօր` թdelays լուրdelays Հdays': 'Aysor',
    # Thai
    'กระทรวงการต่างประเทศ': 'Thailand Foreign Ministry',
    'วารสารการเงินธนาคาร': 'Banking & Finance Journal',
    # Spanish
    'Clarin.com - Home - Lo último': 'Clarin',
    'Excélsior - RSS': 'Excelsior',
    'Diálogo Americas': 'Dialogo Americas',
    'Diario Las Américas': 'Diario Las Americas',
    'Latinoamérica 21': 'Latinoamerica 21',
    'Agenda Pública': 'Agenda Publica',
    'Aviación al Día': 'Aviacion al Dia',
    # Portuguese
    'Diário Carioca': 'Diario Carioca',
    'CPG Click Petróleo e Gás': 'CPG Click',
    # French
    'Le Journal de Montréal': 'Le Journal de Montreal',
    'LaPresse.ca - Actualités': 'La Presse',
    'Le Monde diplomatique': 'Le Monde Diplomatique',
    "Ministère de l'Europe et des Affaires étrangères": 'French Foreign Ministry',
    'Naître et grandir': 'Naitre et Grandir',
    'IRIS - Institut de relations internationales et stratégiques': 'IRIS',
    'Fondation pour la Recherche Stratégique': 'FRS',
    "Agence française de développement (AFD)": 'AFD',
    # Finnish
    'Ulkoministeriö': 'Finnish Foreign Ministry',
    # Austrian/German
    'Wiener Börse': 'Vienna Stock Exchange',
    'The Market – Analysen und Hintergründe aus der Wirtschaft': 'The Market',
    # Special: Al Jazeera (long English name → short)
    'Al Jazeera – Breaking News, World News and Video from Al Jazeera': 'Al Jazeera',
    # Informante (Namibia)
    'Informanté': 'Informante',
    # Maori
    'Waatea News: Māori Radio Station': 'Waatea News',
    # Hawaiian
    'University of Hawaiʻi at Mānoa': 'University of Hawaii',
    # Other long English names → cleaner versions
    'news.com.au — Australia\'s leading news site for latest headlines | National News': 'news.com.au',
    'Nigeria Breaking News Today | Latest News On Nigerian Politics Today – Pointblank News': 'Pointblank News',
    'The Diplomat – Asia-Pacific Current Affairs Magazine': 'The Diplomat',
    'NOTUS — News of the United States': 'NOTUS',
    'Iran – Foreign Policy': 'Foreign Policy',
    'Politics – Independent Newspaper Nigeria': 'Independent Nigeria',
    'Politics – Iran Front Page': 'Iran Front Page',
    'The Kākā by Bernard Hickey': 'The Kaka',
    'Global Banking & Finance Review®': 'Global Banking & Finance Review',
    'Global Banking And Finance Awards®': 'Global Banking & Finance Awards',
    'TradingView — Track All Markets': 'TradingView',
    'EL PAÍS English': 'El Pais',
    'TechStock²': 'TechStock',
    'BelTA – News': 'BelTA',
    'Economics – The Tangled Woof': 'The Tangled Woof',
    'Morning Star | The People\'s Daily': 'Morning Star',
}

def normalize_source_name(name):
    """Map non-English source names to their English equivalents."""
    if not name:
        return name
    name = name.strip()
    # Exact match first
    if name in SOURCE_NAME_MAP:
        return SOURCE_NAME_MAP[name]
    # Strip © prefix from photo credits (e.g. "© Reuters" → "Reuters")
    if name.startswith('© ') or name.startswith('©'):
        cleaned = name.lstrip('© ').strip()
        # If it's a photo credit (contains / which indicates photographer/agency), skip mapping
        if '/' in cleaned:
            return name
        # Map known agencies
        credit_map = {'Reuters': 'Reuters', 'REUTERS': 'Reuters', 'AP': 'AP', 'AFP': 'AFP', 'rfi': 'RFI', 'RFI': 'RFI'}
        if cleaned in credit_map:
            return credit_map[cleaned]
    return name

# --- Load models ---
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logging.info("Embedding model 'all-MiniLM-L6-v2' loaded successfully.")
except Exception as e:
    logging.critical(f"Failed to load SentenceTransformer model: {e}")
    raise e

try:
    groq_client = Groq()
except Exception as e:
    logging.getLogger(__name__).critical(f"Failed to initialize Groq client: {e}. Make sure GROQ_API_KEY is set.")
    raise e

class GeomemoDatabasePipeline:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.seen_urls = set()
        self.report_stats = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        self.categories_list = [
            'Geopolitical Conflict', 'Geopolitical Economics', 'Global Markets',
            'Geopolitical Politics', 'GeoNatDisaster', 'GeoLocal', 'Other'
        ]
        self.valid_categories_set = set(self.categories_list)
        self.embedding_model = embedding_model

        # M2: Scoring weights
        self.scoring_weights = {
            "confidence": 0.40,
            "credibility": 0.30,
            "novelty": 0.15,
            "category_bonus": 0.15,
        }
        self.category_bonus_map = {
            'Geopolitical Conflict': 95,
            'Geopolitical Economics': 90,
            'Global Markets': 85,
            'Geopolitical Politics': 80,
            'GeoNatDisaster': 60,
            'GeoLocal': 40,
            'Other': 10,
        }
        self.repetition_threshold = 0.85
        self.default_credibility = 50

    def open_spider(self, spider):
        try:
            # --- Database connection from environment ---
            self.connection = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "db"),
                database=os.getenv("POSTGRES_DB", "postgres"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
            )
            self.cursor = self.connection.cursor()
            register_vector(self.connection)
            self.logger.info("Database connection opened and vector type registered")
        except psycopg2.OperationalError as e:
            self.logger.critical(f"DATABASE CONNECTION FAILED: {e}")
            raise e

    def close_spider(self, spider):
        self.logger.info("--- CRAWL STATS REPORT ---")
        self.logger.info(json.dumps(self.report_stats, indent=2))
        if self.cursor: self.cursor.close()
        if self.connection: self.connection.close()
        self.logger.info("Database connection closed")

    # =========================================
    # GROQ CLASSIFICATION (M2: + country extraction)
    # =========================================

    def _get_groq_completion(self, headline: str, content_snippet: str) -> dict:
        """
        Sends the article to Groq (Llama 3) for classification.
        M2: Now also extracts country names from the article.
        """
        system_prompt = f"""
You are a top-tier geopolitical analyst for 'GeoMemo'.
Your goal is to curate high-value geopolitical news.

INSTRUCTION:
Judge this article STRICTLY based on the definitions below.
Do not use previous rejections as a guide. If it fits a category, approve it.

STEP 1: Analyze relevance based on these rules:
- `Geopolitical Conflict`: War, civil war, terrorism, defense pacts.
- `Geopolitical Politics`: NATIONAL elections/outcomes, diplomatic tensions.
- `GeoNatDisaster`: MAJOR climate disasters with international aid/impact.
- `Geopolitical Economics`: Trade wars, sanctions, economic pacts (EU, BRICS, etc).
- `Global Markets`: Major stock/commodity/currency moves driven by policy.
- `GeoLocal`: Local event with INTERNATIONAL implications.

STEP 2: Assign a CONFIDENCE SCORE (0-100).
- High Score (80-100): Fits the rules clearly.
- Low Score (0-30): Sports, Celebrity Gossip, Local Crime, or minor local news.

STEP 3: Extract ALL countries mentioned or implied in the headline and content.
Return their common English names (e.g., "United States", "China", "Russia").
If no specific country is mentioned, return an empty list.

STEP 4: Output valid JSON:
{{
    "is_relevant": "yes/no",
    "confidence_score": <integer 0-100>,
    "headline_en": "Formal English Headline",
    "summary": "2-3 sentence news summary (40-60 words). Authoritative analytical tone for investment bankers. Sentence 1: core development with specific actors. Sentence 2: quantify with numbers/figures from the article. ONLY add a 3rd sentence if the article contains a concrete forward-looking fact (a date, deadline, vote, named action). NEVER end with speculative 'this may impact...' or 'this could lead to...' statements. NEVER invent details. Every sentence must contain a verifiable fact. English only.",
    "summary_long": "100-word analytical summary for social media. Sentence 1-2: what happened with specific actors and figures. Sentence 3-4: quantified impact with numbers, dollar amounts, percentages. Sentence 5: ONLY if a concrete next step exists (scheduled date, named action, deadline). NEVER end with vague 'this may impact...' or 'this could affect...' statements. ONLY use facts from the provided content. NEVER invent or hallucinate details. Do NOT include dates of publication. English only.",
    "category": "Category Name",
    "countries": ["Country1", "Country2"]
}}
"""
        user_prompt = f"""
--- NEW ARTICLE ---
Headline: "{headline}"
Content: "{content_snippet}"
"""
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            self.logger.error(f"Groq API error: {e}")
            raise DropItem(f"Groq API failed: {e}")

    # =========================================
    # M2: SCORING HELPER METHODS
    # =========================================

    def _resolve_country_codes(self, country_names: list) -> tuple:
        """Convert country names to ISO 3166-1 alpha-2 codes and determine region."""
        if not pycountry or not country_names:
            return [], None

        codes = []
        for name in country_names:
            name = name.strip()
            if not name:
                continue
            # Try exact match first
            country = pycountry.countries.get(name=name)
            if not country:
                # Try common name
                country = pycountry.countries.get(common_name=name)
            if not country:
                # Try fuzzy search
                try:
                    results = pycountry.countries.search_fuzzy(name)
                    country = results[0] if results else None
                except LookupError:
                    country = None
            if country:
                codes.append(country.alpha_2)

        # Determine region from first country code
        region = None
        if codes:
            region = self._get_region(codes[0])

        return codes, region

    def _get_region(self, alpha2_code: str) -> str:
        """Map a country's ISO alpha-2 code to a broad region."""
        REGION_MAP = {
            'US': 'North America', 'CA': 'North America', 'MX': 'North America',
            'GB': 'Europe', 'FR': 'Europe', 'DE': 'Europe', 'IT': 'Europe',
            'ES': 'Europe', 'PL': 'Europe', 'UA': 'Europe', 'NL': 'Europe',
            'SE': 'Europe', 'NO': 'Europe', 'FI': 'Europe', 'DK': 'Europe',
            'CH': 'Europe', 'AT': 'Europe', 'BE': 'Europe', 'PT': 'Europe',
            'GR': 'Europe', 'RO': 'Europe', 'CZ': 'Europe', 'HU': 'Europe',
            'IE': 'Europe', 'BG': 'Europe', 'HR': 'Europe', 'SK': 'Europe',
            'CN': 'East Asia', 'JP': 'East Asia', 'KR': 'East Asia',
            'KP': 'East Asia', 'TW': 'East Asia', 'MN': 'East Asia',
            'IN': 'South Asia', 'PK': 'South Asia', 'BD': 'South Asia',
            'LK': 'South Asia', 'NP': 'South Asia', 'AF': 'South Asia',
            'RU': 'Russia & Central Asia', 'KZ': 'Russia & Central Asia',
            'UZ': 'Russia & Central Asia', 'TM': 'Russia & Central Asia',
            'KG': 'Russia & Central Asia', 'TJ': 'Russia & Central Asia',
            'SA': 'Middle East', 'IR': 'Middle East', 'IQ': 'Middle East',
            'IL': 'Middle East', 'PS': 'Middle East', 'AE': 'Middle East',
            'TR': 'Middle East', 'SY': 'Middle East', 'LB': 'Middle East',
            'YE': 'Middle East', 'JO': 'Middle East', 'QA': 'Middle East',
            'KW': 'Middle East', 'BH': 'Middle East', 'OM': 'Middle East',
            'BR': 'South America', 'AR': 'South America', 'CO': 'South America',
            'CL': 'South America', 'PE': 'South America', 'VE': 'South America',
            'EC': 'South America', 'BO': 'South America', 'PY': 'South America',
            'UY': 'South America', 'GY': 'South America', 'SR': 'South America',
            'AU': 'Oceania', 'NZ': 'Oceania', 'FJ': 'Oceania',
            'PG': 'Oceania', 'SB': 'Oceania',
        }
        region = REGION_MAP.get(alpha2_code)
        if not region:
            # Default unmapped codes to Africa (most unmapped will be African nations)
            region = 'Africa'
        return region

    def _compute_repetition_score(self, embedding: list) -> float:
        """
        Compute max cosine similarity against articles from the last 48 hours.
        Returns a float 0.0-1.0 where higher means MORE repetitive.
        """
        try:
            self.cursor.execute("""
                SELECT 1 - (embedding <=> %s::vector) AS similarity
                FROM articles
                WHERE scraped_at >= NOW() - INTERVAL '48 hours'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 1
            """, (embedding, embedding))
            row = self.cursor.fetchone()
            if row and row[0] is not None:
                return max(0.0, float(row[0]))
            return 0.0
        except Exception as e:
            self.logger.warning(f"Repetition check failed: {e}")
            self.connection.rollback()
            return 0.0

    def _get_source_credibility(self, publication_name: str) -> int:
        """Look up source credibility score from sources table."""
        if not publication_name:
            return self.default_credibility
        try:
            self.cursor.execute(
                "SELECT credibility_score FROM sources WHERE name = %s",
                (publication_name,)
            )
            row = self.cursor.fetchone()
            if row:
                return row[0]
            return self.default_credibility
        except Exception as e:
            self.logger.warning(f"Source lookup failed: {e}")
            self.connection.rollback()
            return self.default_credibility

    def _compute_novelty_score(self, embedding: list) -> float:
        """
        Compute novelty: 1 - max_cosine_similarity to APPROVED articles in last 48h.
        Returns 0-100 scale. Higher = more novel.
        """
        try:
            self.cursor.execute("""
                SELECT 1 - (embedding <=> %s::vector) AS similarity
                FROM articles
                WHERE scraped_at >= NOW() - INTERVAL '48 hours'
                  AND status = 'approved'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 1
            """, (embedding, embedding))
            row = self.cursor.fetchone()
            if row and row[0] is not None:
                max_sim = float(row[0])
                # novelty = 1 - similarity, scaled to 0-100
                return max(0, min(100, (1.0 - max_sim) * 100))
            # No approved articles yet = fully novel
            return 100.0
        except Exception as e:
            self.logger.warning(f"Novelty check failed: {e}")
            self.connection.rollback()
            return 100.0

    def _compute_auto_approval_score(
        self, confidence: int, credibility: int, novelty: float, category: str
    ) -> float:
        """
        Composite score = weighted sum of:
          40% confidence (0-100)
          30% credibility (0-100)
          15% novelty (0-100)
          15% category bonus (0-100)
        Returns a float 0-100.
        """
        w = self.scoring_weights
        cat_bonus = self.category_bonus_map.get(category, 10)

        score = (
            w["confidence"] * confidence +
            w["credibility"] * credibility +
            w["novelty"] * novelty +
            w["category_bonus"] * cat_bonus
        )
        return round(min(100, max(0, score)), 2)

    def _lookup_or_create_source(self, publication_name: str):
        """Look up source_id, auto-creating if it doesn't exist. Returns int or None."""
        if not publication_name:
            return None
        try:
            self.cursor.execute(
                "SELECT id FROM sources WHERE name = %s", (publication_name,)
            )
            row = self.cursor.fetchone()
            if row:
                return row[0]
            # Auto-create source entry
            self.cursor.execute(
                "INSERT INTO sources (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
                (publication_name,)
            )
            new_row = self.cursor.fetchone()
            if new_row:
                return new_row[0]
            # Conflict path: source was created concurrently, re-fetch
            self.cursor.execute(
                "SELECT id FROM sources WHERE name = %s", (publication_name,)
            )
            row = self.cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            self.logger.warning(f"Source lookup/create failed: {e}")
            self.connection.rollback()
            return None

    # =========================================
    # OG IMAGE EXTRACTION
    # =========================================

    def _fetch_og_image(self, url: str) -> str:
        """
        Fetch the article URL and extract og:image meta tag.
        Reads only the first 20KB to minimize latency.
        Returns the image URL or None.
        """
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; GeoMemoBot/1.0)"
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read(20000).decode("utf-8", errors="ignore")
            # Try both meta tag orderings
            pat1 = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
            pat2 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            match = re.search(pat1, html, re.IGNORECASE) or re.search(pat2, html, re.IGNORECASE)
            if match:
                img_url = match.group(1).strip()
                if img_url.startswith('http'):
                    return img_url
        except Exception as e:
            self.logger.debug(f"OG image fetch failed for {url[:60]}: {e}")
        return None

    # =========================================
    # MAIN PROCESSING
    # =========================================

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if adapter.get('url') in self.seen_urls:
            raise DropItem(f"Duplicate: {item['url']}")
        self.seen_urls.add(adapter['url'])

        headline = adapter['headline']
        content_snippet = adapter.get('description', '') or ""
        publication_name = adapter.get('publication_name')

        # Normalize non-English source names to English
        if publication_name:
            publication_name = normalize_source_name(publication_name)
            adapter['publication_name'] = publication_name

        self.logger.info(f"Processing: '{headline}'")

        try:
            # 1. Ask Groq FIRST (M2: includes country extraction)
            processed_data = self._get_groq_completion(headline, content_snippet)

            # 2. Check Relevance
            if processed_data.get("is_relevant") == "no":
                self.logger.info(f"DROPPED (Irrelevant): '{headline}' (Score: {processed_data.get('confidence_score', 0)})")
                raise DropItem(f"Irrelevant: {headline}")

            # 3. Assign Data from Groq
            adapter['headline_en'] = processed_data.get('headline_en', headline)
            adapter['summary'] = processed_data.get('summary', 'No summary.')
            adapter['summary_long'] = processed_data.get('summary_long', adapter['summary'])

            # 4. Generate Embedding AFTER Groq — use English headline + AI summary
            #    for accurate cross-language similarity matching
            text_to_embed = f"Headline: {adapter['headline_en']}\nSummary: {adapter['summary']}"
            embedding = self.embedding_model.encode(text_to_embed).tolist()
            adapter['embedding'] = embedding
            adapter['category'] = processed_data.get('category', 'Other')
            adapter['confidence_score'] = processed_data.get('confidence_score', 50)

            if adapter['category'] not in self.valid_categories_set:
                adapter['category'] = 'Other'

            # 5. M2: Resolve country codes from Groq response
            country_names = processed_data.get('countries', [])
            if not isinstance(country_names, list):
                country_names = []
            country_codes, region = self._resolve_country_codes(country_names)

            # 6. M2: Compute repetition score (against ALL articles in 48h)
            repetition_score = self._compute_repetition_score(embedding)

            # 7. M2: Look up source credibility
            source_credibility = self._get_source_credibility(publication_name)

            # 8. M2: Compute novelty (against APPROVED articles in 48h)
            novelty_score = self._compute_novelty_score(embedding)

            # 9. M2: Compute composite auto-approval score
            auto_approval_score = self._compute_auto_approval_score(
                adapter['confidence_score'],
                source_credibility,
                novelty_score,
                adapter['category']
            )

            # 10. M2: Look up or auto-create source_id
            # Use pre-resolved source_id from DB-loaded feeds if available
            source_id = adapter.get('source_id') or self._lookup_or_create_source(publication_name)

            # 11. OG Image: use RSS-extracted image, or fetch from article URL
            og_image = adapter.get('og_image')
            if not og_image:
                og_image = self._fetch_og_image(adapter['url'])
            if og_image:
                self.logger.info(f"OG Image: {og_image[:80]}")

            self.logger.info(
                f"Scored: '{headline}' | Confidence: {adapter['confidence_score']} | "
                f"Credibility: {source_credibility} | Novelty: {novelty_score:.1f} | "
                f"Repetition: {repetition_score:.3f} | Auto: {auto_approval_score} | "
                f"Countries: {country_codes}"
            )

            # 12. Save to DB (expanded INSERT with og_image)
            self.cursor.execute(
                """
                INSERT INTO articles
                (url, headline, publication_name, author, headline_en, summary,
                 summary_long, category, status, scraped_at, embedding, confidence_score,
                 source_id, repetition_score, auto_approval_score,
                 country_codes, region, og_image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), %s, %s,
                        %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    adapter['url'], adapter['headline'], publication_name,
                    adapter.get('author'),
                    adapter['headline_en'], adapter['summary'],
                    adapter['summary_long'], adapter['category'],
                    adapter['embedding'], adapter['confidence_score'],
                    source_id, repetition_score, auto_approval_score,
                    country_codes if country_codes else None,
                    region, og_image
                )
            )
            self.connection.commit()

        except DropItem as e:
            raise e
        except Exception as e:
            # Rollback on any other error to keep connection alive
            self.connection.rollback()
            self.logger.error(f"Error processing '{headline}': {e}")
            raise DropItem(f"Processing failed: {item['url']}")

        return item

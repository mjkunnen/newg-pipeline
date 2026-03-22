"""Central configuration for the NEWGARMENTS intelligence bot."""
import os
from dotenv import load_dotenv

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Meta Ad Library API
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_API_VERSION = "v21.0"
META_AD_ARCHIVE_URL = f"https://graph.facebook.com/{META_API_VERSION}/ads_archive"
META_DEFAULT_AD_LIMIT = 50
META_API_FIELDS = [
    "ad_creation_time",
    "ad_creative_bodies",
    "ad_creative_link_captions",
    "ad_creative_link_titles",
    "ad_creative_link_descriptions",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "ad_snapshot_url",
    "bylines",
    "currency",
    "impressions",
    "page_id",
    "page_name",
    "publisher_platforms",
    "spend",
    "demographic_distribution",
    "delivery_by_region",
    "languages",
]
DOCS_DIR = BASE_DIR
BOT_DIR = os.path.join(BASE_DIR, "bot")
OUTPUT_DIR = os.path.join(BOT_DIR, "output")

# Ensure output dir exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Document files
DOC_FILES = [
    "Core beliefs customers newgarments.txt",
    "Gen Z Streetwear Audience & Market Research.txt",
    "NEWGARMENTS AVATAR SHEET TEMPLATE.txt",
    "NEWGARMENTS Offer brief template .txt",
    "research docs.txt",
]

# Search settings
MAX_SEARCH_RESULTS = 20
REQUEST_TIMEOUT = 30000  # ms
RATE_LIMIT_DELAY = 2  # seconds between requests

# Scoring weights (out of 1.0)
SCORING_WEIGHTS = {
    "audience_overlap": 0.20,
    "aesthetic_similarity": 0.15,
    "messaging_similarity": 0.15,
    "offer_similarity": 0.10,
    "platform_presence": 0.10,
    "ad_activity": 0.10,
    "website_quality": 0.10,
    "confidence_level": 0.10,
}

# Search queries for competitor discovery
SEARCH_QUERIES = [
    "Gen Z streetwear brand limited drops heavyweight hoodie",
    "archive streetwear brand no restock limited edition",
    "underground streetwear brand premium quality 2025 2026",
    "streetwear brand like Vicinity Corteiz Represent",
    "best new streetwear brands Gen Z TikTok Instagram",
    "heavyweight hoodie brand archive style limited run",
    "exclusive streetwear drops Europe UK",
    "streetwear brand premium blanks custom cut 500gsm",
    "niche streetwear brand D2C online drops",
    "streetwear brand trust transparency quality",
]

# Known competitor seeds (from documents + niche research)
SEED_COMPETITORS = [
    # Directly mentioned in documents
    {
        "name": "Vicinity (Vicinityclo)",
        "website": "https://vicinityclo.de",
        "instagram": "vicinityclo",
        "tiktok": "vicinityclo",
        "source": "document_mention",
    },
    {
        "name": "Divinbydivin",
        "website": "https://us.divinbydivin.com",
        "instagram": "divinbydivin",
        "tiktok": "divinbydivin",
        "source": "document_mention",
    },
    {
        "name": "TheSupermade",
        "website": "https://thesupermade.com",
        "instagram": "thesupermade",
        "tiktok": "thesupermade",
        "source": "document_mention",
    },
    {
        "name": "Scuffers",
        "website": "https://scuffers.es",
        "instagram": "scuffers",
        "tiktok": "scuffers",
        "source": "document_mention",
    },
    {
        "name": "Corteiz",
        "website": "https://www.corteiz.com",
        "instagram": "corteiz",
        "tiktok": "corteiz",
        "source": "document_mention",
    },
    {
        "name": "Represent Clo",
        "website": "https://representclo.com",
        "instagram": "representclo",
        "tiktok": "representclo",
        "source": "document_mention",
    },
    {
        "name": "Trapstar",
        "website": "https://trapstarlondon.com",
        "instagram": "trapstar",
        "tiktok": "trapstar",
        "source": "document_mention",
    },
    # Adjacent niche competitors (same audience/aesthetic)
    {
        "name": "Cold Culture",
        "website": "https://coldculture.com",
        "instagram": "coldculture",
        "tiktok": "coldculture",
        "source": "niche_research",
    },
    {
        "name": "Pegador",
        "website": "https://pegador.de",
        "instagram": "pegador",
        "tiktok": "pegador",
        "source": "niche_research",
    },
    {
        "name": "Unknown London",
        "website": "https://unknownlondon.com",
        "instagram": "unknownlondon",
        "tiktok": "unknownlondon",
        "source": "niche_research",
    },
    {
        "name": "Broken Planet Market",
        "website": "https://brokenplanetmarket.com",
        "instagram": "brokenplanetmarket",
        "tiktok": "brokenplanetmarket",
        "source": "niche_research",
    },
    {
        "name": "ERL",
        "website": "https://erlstudio.com",
        "instagram": "erl____",
        "tiktok": "",
        "source": "niche_research",
    },
    {
        "name": "Cole Buxton",
        "website": "https://colebuxton.com",
        "instagram": "colebuxton",
        "tiktok": "colebuxton",
        "source": "niche_research",
    },
    {
        "name": "Stussy",
        "website": "https://www.stussy.com",
        "instagram": "stussy",
        "tiktok": "stussy",
        "source": "document_mention",
    },
    {
        "name": "Market Studios",
        "website": "https://marketstudios.com",
        "instagram": "market",
        "tiktok": "market",
        "source": "niche_research",
    },
    {
        "name": "Daily Paper",
        "website": "https://www.dailypaperclothing.com",
        "instagram": "dailypaper",
        "tiktok": "dailypaper",
        "source": "niche_research",
    },
    {
        "name": "Filling Pieces",
        "website": "https://www.fillingpieces.com",
        "instagram": "fillingpieces",
        "tiktok": "fillingpieces",
        "source": "niche_research",
    },
    {
        "name": "Patta",
        "website": "https://www.patta.nl",
        "instagram": "paboroughtta",
        "tiktok": "",
        "source": "niche_research",
    },
    {
        "name": "Essentials (Fear of God)",
        "website": "https://www.fearofgod.com",
        "instagram": "fearofgod",
        "tiktok": "fearofgod",
        "source": "niche_research",
    },
    {
        "name": "Noah NY",
        "website": "https://noahny.com",
        "instagram": "noahclothing",
        "tiktok": "",
        "source": "document_mention",
    },
    {
        "name": "Aimé Leon Dore",
        "website": "https://www.aimeleondore.com",
        "instagram": "aimeleondore",
        "tiktok": "aimeleondore",
        "source": "niche_research",
    },
    {
        "name": "New Amsterdam Surf Association",
        "website": "https://newamsterdamsurf.com",
        "instagram": "newamsterdamsurf",
        "tiktok": "",
        "source": "niche_research",
    },
]

# Platform URL templates
INSTAGRAM_URL = "https://www.instagram.com/{handle}/"
TIKTOK_URL = "https://www.tiktok.com/@{handle}"
META_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={query}&media_type=all"

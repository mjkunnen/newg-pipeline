import os
from dotenv import load_dotenv

load_dotenv()

META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
META_AD_ACCOUNT_ID = os.environ["META_AD_ACCOUNT_ID"]
META_PAGE_ID = os.environ.get("META_PAGE_ID", "")
META_PIXEL_ID = os.environ.get("META_PIXEL_ID", "")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
FAL_KEY = os.environ.get("FAL_KEY", "")
DATABASE_URL = os.environ["DATABASE_URL"]
DASHBOARD_SECRET = os.environ["DASHBOARD_SECRET"]
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "10"))
ROAS_ALERT_THRESHOLD = float(os.environ.get("ROAS_ALERT_THRESHOLD", "1.5"))
CPA_ALERT_THRESHOLD = float(os.environ.get("CPA_ALERT_THRESHOLD", "15.0"))
GRAPH_API = "https://graph.facebook.com/v21.0"

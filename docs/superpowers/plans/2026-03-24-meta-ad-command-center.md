# NEWG Ad Command Center — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Railway-hosted Meta ad performance dashboard with AI creative analysis, one-click iteration, and ad management actions.

**Architecture:** Python FastAPI backend serving a single-page frontend. PostgreSQL stores synced ad data. APScheduler triggers Meta API sync every 10 minutes. Frontend auto-refreshes to show latest data. AI analysis runs daily via GPT-4o Vision.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, APScheduler, Chart.js, OpenAI API, fal.ai, Meta Marketing API v21.0

**Spec:** `docs/superpowers/specs/2026-03-24-meta-ad-command-center-design.md`

---

## File Structure

```
ad-command-center/
├── main.py                    # FastAPI app entry point, scheduler setup, static file serving
├── config.py                  # Environment variables, settings
├── db.py                      # SQLAlchemy engine, session, Base
├── models.py                  # All SQLAlchemy models (campaigns, ads, snapshots, etc.)
├── meta_client.py             # Meta Marketing API client (sync, pause, activate, budget, launch)
├── sync.py                    # Sync orchestrator (calls meta_client, stores in DB, generates notifications)
├── analysis.py                # AI analysis (GPT-4o Vision creative analysis, pattern detection)
├── iteration.py               # Make Iterations pipeline (fetch creative, fal.ai, GPT copy, Meta launch)
├── routes/
│   ├── kpis.py                # GET /api/kpis, /api/kpis/history
│   ├── ads.py                 # GET/POST /api/ads, pause, activate, iterate
│   ├── analysis.py            # GET /api/analysis, POST /api/analysis/refresh
│   ├── notifications.py       # GET/POST /api/notifications
│   └── auth.py                # POST /api/auth/login, auth middleware
├── static/
│   └── index.html             # Single-page dashboard (inline CSS/JS, Chart.js)
├── requirements.txt           # Python dependencies
├── Procfile                   # Railway process file
├── railway.toml               # Railway config
└── .env.example               # Example environment variables
```

---

### Task 1: Project Scaffold & Config

**Files:**
- Create: `ad-command-center/config.py`
- Create: `ad-command-center/requirements.txt`
- Create: `ad-command-center/Procfile`
- Create: `ad-command-center/railway.toml`
- Create: `ad-command-center/.env.example`

- [ ] **Step 1: Create project directory**

```bash
mkdir -p "ad-command-center/routes" "ad-command-center/static"
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
apscheduler==3.10.4
httpx==0.27.0
openai==1.50.0
python-dotenv==1.0.1
```

- [ ] **Step 3: Write config.py**

```python
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
```

- [ ] **Step 4: Write Procfile and railway.toml**

Procfile:
```
web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

railway.toml:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

- [ ] **Step 5: Write .env.example**

```
META_ACCESS_TOKEN=
META_AD_ACCOUNT_ID=
META_PAGE_ID=
META_PIXEL_ID=
OPENAI_API_KEY=
FAL_KEY=
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DASHBOARD_SECRET=your-secret-password
SYNC_INTERVAL_MINUTES=10
ROAS_ALERT_THRESHOLD=1.5
CPA_ALERT_THRESHOLD=15.0
```

- [ ] **Step 6: Commit**

```bash
git add ad-command-center/
git commit -m "feat: scaffold ad command center project"
```

---

### Task 2: Database Models

**Files:**
- Create: `ad-command-center/db.py`
- Create: `ad-command-center/models.py`

- [ ] **Step 1: Write db.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Write models.py**

```python
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, LargeBinary, ForeignKey
from sqlalchemy.sql import func
from db import Base

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    status = Column(String)
    daily_budget = Column(Integer)  # cents
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class AdSet(Base):
    __tablename__ = "ad_sets"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    campaign_id = Column(String, ForeignKey("campaigns.id"))
    status = Column(String)
    daily_budget = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Ad(Base):
    __tablename__ = "ads"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    ad_set_id = Column(String, ForeignKey("ad_sets.id"))
    status = Column(String)
    creative_url = Column(Text)
    creative_cached = Column(LargeBinary, nullable=True)
    ad_copy = Column(Text)
    parent_ad_id = Column(String, ForeignKey("ads.id"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String, default="meta")
    ad_id = Column(String, ForeignKey("ads.id"))
    timestamp = Column(DateTime, server_default=func.now())
    spend = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    add_to_carts = Column(Integer, default=0)
    purchases = Column(Integer, default=0)
    revenue = Column(Float, default=0)
    roas = Column(Float, default=0)

class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String, default="meta")
    timestamp = Column(DateTime, server_default=func.now())
    analysis_json = Column(Text)
    recommendations = Column(Text)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    read = Column(Boolean, default=False)

class IterationJob(Base):
    __tablename__ = "iteration_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String, ForeignKey("ads.id"))
    status = Column(String, default="pending")  # pending/generating/launching/done/failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
```

- [ ] **Step 3: Commit**

```bash
git add ad-command-center/db.py ad-command-center/models.py
git commit -m "feat: add database models for ad command center"
```

---

### Task 3: Meta API Client

**Files:**
- Create: `ad-command-center/meta_client.py`

- [ ] **Step 1: Write meta_client.py**

```python
import httpx
from config import GRAPH_API, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID

async def graph_get(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{GRAPH_API}{path}",
            params={"access_token": META_ACCESS_TOKEN},
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            raise Exception(f"Meta API error: {data['error'].get('message', data['error'])}")
        return data

async def graph_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{GRAPH_API}{path}",
            params={"access_token": META_ACCESS_TOKEN},
            json=body,
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            raise Exception(f"Meta API error: {data['error'].get('message', data['error'])}")
        return data

def act_id():
    return f"act_{META_AD_ACCOUNT_ID}"

async def fetch_campaigns() -> list[dict]:
    data = await graph_get(f"/{act_id()}/campaigns?fields=id,name,status,daily_budget")
    return data.get("data", [])

async def fetch_ad_sets(campaign_id: str) -> list[dict]:
    data = await graph_get(f"/{campaign_id}/adsets?fields=id,name,status,daily_budget")
    return data.get("data", [])

async def fetch_ads(adset_id: str) -> list[dict]:
    data = await graph_get(f"/{adset_id}/ads?fields=id,name,status,creative")
    return data.get("data", [])

async def fetch_ad_insights(ad_id: str, date_preset: str = "today") -> dict | None:
    data = await graph_get(
        f"/{ad_id}/insights?fields=spend,impressions,clicks,cpc,ctr,actions,action_values"
        f"&date_preset={date_preset}"
    )
    results = data.get("data", [])
    return results[0] if results else None

async def fetch_creative_thumbnail(creative_id: str) -> str | None:
    data = await graph_get(f"/{creative_id}?fields=thumbnail_url,image_url,object_story_spec")
    return data.get("thumbnail_url") or data.get("image_url")

async def download_image(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=30)
        return r.content

async def pause_ad(ad_id: str) -> dict:
    return await graph_post(f"/{ad_id}", {"status": "PAUSED"})

async def activate_ad(ad_id: str) -> dict:
    return await graph_post(f"/{ad_id}", {"status": "ACTIVE"})

async def update_adset_budget(adset_id: str, daily_budget_cents: int) -> dict:
    return await graph_post(f"/{adset_id}", {"daily_budget": daily_budget_cents})

async def fetch_account_insights(date_preset: str = "today") -> dict | None:
    data = await graph_get(
        f"/{act_id()}/insights?fields=spend,impressions,clicks,cpc,ctr,actions,action_values"
        f"&date_preset={date_preset}"
    )
    results = data.get("data", [])
    return results[0] if results else None

async def fetch_account_insights_daily(days: int = 30) -> list[dict]:
    data = await graph_get(
        f"/{act_id()}/insights?fields=spend,impressions,clicks,cpc,ctr,actions,action_values"
        f"&time_increment=1&date_preset=last_{days}d"
    )
    return data.get("data", [])
```

- [ ] **Step 2: Commit**

```bash
git add ad-command-center/meta_client.py
git commit -m "feat: add Meta Marketing API client"
```

---

### Task 4: Sync Orchestrator

**Files:**
- Create: `ad-command-center/sync.py`

- [ ] **Step 1: Write sync.py**

```python
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from db import SessionLocal
from models import Campaign, AdSet, Ad, Snapshot, Notification
import meta_client
from config import ROAS_ALERT_THRESHOLD, CPA_ALERT_THRESHOLD

logger = logging.getLogger(__name__)

def parse_actions(actions: list[dict] | None, action_type: str) -> int:
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(a.get("value", 0))
    return 0

def parse_action_values(action_values: list[dict] | None, action_type: str) -> float:
    if not action_values:
        return 0.0
    for a in action_values:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0

async def run_sync():
    logger.info("Starting Meta sync...")
    db = SessionLocal()
    try:
        campaigns = await meta_client.fetch_campaigns()
        for c in campaigns:
            existing = db.query(Campaign).filter_by(id=c["id"]).first()
            if existing:
                existing.name = c["name"]
                existing.status = c["status"]
                existing.daily_budget = int(c.get("daily_budget", 0))
            else:
                db.add(Campaign(
                    id=c["id"], channel="meta", name=c["name"],
                    status=c["status"], daily_budget=int(c.get("daily_budget", 0))
                ))
            db.flush()

            ad_sets = await meta_client.fetch_ad_sets(c["id"])
            for aset in ad_sets:
                existing_aset = db.query(AdSet).filter_by(id=aset["id"]).first()
                if existing_aset:
                    existing_aset.name = aset["name"]
                    existing_aset.status = aset["status"]
                    existing_aset.daily_budget = int(aset.get("daily_budget", 0))
                else:
                    db.add(AdSet(
                        id=aset["id"], channel="meta", name=aset["name"],
                        campaign_id=c["id"], status=aset["status"],
                        daily_budget=int(aset.get("daily_budget", 0))
                    ))
                db.flush()

                ads = await meta_client.fetch_ads(aset["id"])
                for ad in ads:
                    ad_id = ad["id"]
                    creative_id = ad.get("creative", {}).get("id")

                    existing_ad = db.query(Ad).filter_by(id=ad_id).first()
                    if not existing_ad:
                        thumb_url = None
                        thumb_bytes = None
                        if creative_id:
                            thumb_url = await meta_client.fetch_creative_thumbnail(creative_id)
                            if thumb_url:
                                try:
                                    thumb_bytes = await meta_client.download_image(thumb_url)
                                except Exception:
                                    pass
                        db.add(Ad(
                            id=ad_id, channel="meta", name=ad["name"],
                            ad_set_id=aset["id"], status=ad["status"],
                            creative_url=thumb_url, creative_cached=thumb_bytes,
                        ))
                    else:
                        existing_ad.status = ad["status"]
                        existing_ad.name = ad["name"]
                    db.flush()

                    insights = await meta_client.fetch_ad_insights(ad_id)
                    if insights:
                        spend = float(insights.get("spend", 0))
                        purchases = parse_actions(insights.get("actions"), "purchase")
                        revenue = parse_action_values(insights.get("action_values"), "purchase")
                        roas = revenue / spend if spend > 0 else 0

                        snapshot = Snapshot(
                            channel="meta", ad_id=ad_id,
                            spend=spend,
                            impressions=int(insights.get("impressions", 0)),
                            clicks=int(insights.get("clicks", 0)),
                            ctr=float(insights.get("ctr", 0)),
                            cpc=float(insights.get("cpc", 0)),
                            add_to_carts=parse_actions(insights.get("actions"), "add_to_cart"),
                            purchases=purchases,
                            revenue=revenue,
                            roas=roas,
                        )
                        db.add(snapshot)

                        # Generate alerts
                        if spend > 5 and roas < ROAS_ALERT_THRESHOLD:
                            db.add(Notification(
                                type="roas_low",
                                message=f"Ad '{ad['name']}' ROAS is {roas:.1f}x (below {ROAS_ALERT_THRESHOLD}x threshold)"
                            ))
                        if purchases > 0:
                            cpa = spend / purchases
                            if cpa > CPA_ALERT_THRESHOLD:
                                db.add(Notification(
                                    type="cpa_high",
                                    message=f"Ad '{ad['name']}' CPA is €{cpa:.2f} (above €{CPA_ALERT_THRESHOLD} threshold)"
                                ))

        db.commit()
        logger.info("Meta sync complete")
    except Exception as e:
        db.rollback()
        logger.error(f"Sync failed: {e}")
        if "OAuthException" in str(e):
            db.add(Notification(type="token_expired", message="Meta access token expired. Please refresh."))
            db.commit()
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add ad-command-center/sync.py
git commit -m "feat: add sync orchestrator for Meta ad data"
```

---

### Task 5: API Routes — KPIs & Ads

**Files:**
- Create: `ad-command-center/routes/auth.py`
- Create: `ad-command-center/routes/kpis.py`
- Create: `ad-command-center/routes/ads.py`

- [ ] **Step 1: Write routes/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Header
from config import DASHBOARD_SECRET

router = APIRouter()

async def verify_auth(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {DASHBOARD_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/api/auth/login")
async def login(body: dict):
    if body.get("password") == DASHBOARD_SECRET:
        return {"token": DASHBOARD_SECRET}
    raise HTTPException(status_code=401, detail="Invalid password")
```

- [ ] **Step 2: Write routes/kpis.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Snapshot, Ad
from routes.auth import verify_auth
from datetime import datetime, timedelta

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    def day_totals(date):
        rows = db.query(
            func.sum(Snapshot.spend),
            func.sum(Snapshot.clicks),
            func.sum(Snapshot.impressions),
            func.sum(Snapshot.add_to_carts),
            func.sum(Snapshot.purchases),
            func.sum(Snapshot.revenue),
        ).filter(
            cast(Snapshot.timestamp, Date) == date
        ).first()
        spend = rows[0] or 0
        return {
            "spend": round(spend, 2),
            "clicks": rows[1] or 0,
            "impressions": rows[2] or 0,
            "add_to_carts": rows[3] or 0,
            "purchases": rows[4] or 0,
            "revenue": round(rows[5] or 0, 2),
            "roas": round((rows[5] or 0) / spend, 2) if spend > 0 else 0,
            "cpc": round(spend / (rows[1] or 1), 2),
        }

    t = day_totals(today)
    y = day_totals(yesterday)
    return {
        "today": t,
        "yesterday": y,
        "changes": {
            "spend": round(t["spend"] - y["spend"], 2),
            "roas": round(t["roas"] - y["roas"], 2),
            "cpc": round(t["cpc"] - y["cpc"], 2),
            "add_to_carts": t["add_to_carts"] - y["add_to_carts"],
            "purchases": t["purchases"] - y["purchases"],
        }
    }

@router.get("/api/kpis/history")
def get_kpis_history(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.utcnow().date() - timedelta(days=days)
    rows = db.query(
        cast(Snapshot.timestamp, Date).label("date"),
        func.sum(Snapshot.spend).label("spend"),
        func.sum(Snapshot.revenue).label("revenue"),
        func.sum(Snapshot.clicks).label("clicks"),
        func.sum(Snapshot.impressions).label("impressions"),
    ).filter(
        cast(Snapshot.timestamp, Date) >= since
    ).group_by(
        cast(Snapshot.timestamp, Date)
    ).order_by("date").all()

    return [
        {
            "date": str(r.date),
            "spend": round(r.spend or 0, 2),
            "revenue": round(r.revenue or 0, 2),
            "clicks": r.clicks or 0,
            "impressions": r.impressions or 0,
        }
        for r in rows
    ]
```

- [ ] **Step 3: Write routes/ads.py**

```python
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Ad, Snapshot, IterationJob
from routes.auth import verify_auth
import meta_client
from datetime import datetime
import base64

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/ads")
def get_ads(db: Session = Depends(get_db)):
    ads = db.query(Ad).all()
    result = []
    for ad in ads:
        latest = db.query(Snapshot).filter_by(ad_id=ad.id).order_by(Snapshot.timestamp.desc()).first()
        thumb_b64 = None
        if ad.creative_cached:
            thumb_b64 = base64.b64encode(ad.creative_cached).decode()
        result.append({
            "id": ad.id,
            "name": ad.name,
            "status": ad.status,
            "ad_copy": ad.ad_copy,
            "parent_ad_id": ad.parent_ad_id,
            "thumbnail": thumb_b64,
            "metrics": {
                "spend": latest.spend if latest else 0,
                "impressions": latest.impressions if latest else 0,
                "clicks": latest.clicks if latest else 0,
                "ctr": latest.ctr if latest else 0,
                "cpc": latest.cpc if latest else 0,
                "add_to_carts": latest.add_to_carts if latest else 0,
                "purchases": latest.purchases if latest else 0,
                "revenue": latest.revenue if latest else 0,
                "roas": latest.roas if latest else 0,
            }
        })
    result.sort(key=lambda a: a["metrics"]["spend"], reverse=True)
    return result

@router.get("/api/ads/{ad_id}")
def get_ad_detail(ad_id: str, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if not ad:
        raise HTTPException(404, "Ad not found")
    snapshots = db.query(Snapshot).filter_by(ad_id=ad_id).order_by(Snapshot.timestamp).all()
    return {
        "id": ad.id,
        "name": ad.name,
        "status": ad.status,
        "history": [
            {"timestamp": str(s.timestamp), "spend": s.spend, "roas": s.roas, "cpc": s.cpc, "clicks": s.clicks}
            for s in snapshots
        ]
    }

@router.post("/api/ads/{ad_id}/pause")
async def pause_ad(ad_id: str, db: Session = Depends(get_db)):
    await meta_client.pause_ad(ad_id)
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if ad:
        ad.status = "PAUSED"
        db.commit()
    return {"success": True}

@router.post("/api/ads/{ad_id}/activate")
async def activate_ad(ad_id: str, db: Session = Depends(get_db)):
    await meta_client.activate_ad(ad_id)
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if ad:
        ad.status = "ACTIVE"
        db.commit()
    return {"success": True}

@router.post("/api/ads/{ad_id}/iterate")
async def iterate_ad(ad_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if not ad:
        raise HTTPException(404, "Ad not found")
    job = IterationJob(ad_id=ad_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    # Run iteration in background (Task 7 implements this)
    from iteration import run_iteration
    background_tasks.add_task(run_iteration, job.id)
    return {"job_id": job.id, "status": "pending"}
```

- [ ] **Step 4: Commit**

```bash
git add ad-command-center/routes/
git commit -m "feat: add API routes for KPIs, ads, and auth"
```

---

### Task 6: Notifications & Analysis Routes

**Files:**
- Create: `ad-command-center/routes/notifications.py`
- Create: `ad-command-center/routes/analysis.py`

- [ ] **Step 1: Write routes/notifications.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db import get_db
from models import Notification
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter_by(read=False).order_by(Notification.created_at.desc()).limit(50).all()
    return [
        {"id": n.id, "type": n.type, "message": n.message, "created_at": str(n.created_at)}
        for n in notifs
    ]

@router.post("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter_by(id=notif_id).first()
    if n:
        n.read = True
        db.commit()
    return {"success": True}
```

- [ ] **Step 2: Write routes/analysis.py**

```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from db import get_db
from models import AiAnalysis
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/analysis")
def get_analysis(db: Session = Depends(get_db)):
    latest = db.query(AiAnalysis).order_by(AiAnalysis.timestamp.desc()).first()
    if not latest:
        return {"analysis": None, "recommendations": None, "timestamp": None}
    return {
        "analysis": latest.analysis_json,
        "recommendations": latest.recommendations,
        "timestamp": str(latest.timestamp),
    }

@router.post("/api/analysis/refresh")
async def refresh_analysis(background_tasks: BackgroundTasks):
    from analysis import run_analysis
    background_tasks.add_task(run_analysis)
    return {"status": "started"}
```

- [ ] **Step 3: Commit**

```bash
git add ad-command-center/routes/notifications.py ad-command-center/routes/analysis.py
git commit -m "feat: add notification and analysis API routes"
```

---

### Task 7: AI Analysis Engine

**Files:**
- Create: `ad-command-center/analysis.py`

- [ ] **Step 1: Write analysis.py**

```python
import json
import logging
import base64
from openai import OpenAI
from db import SessionLocal
from models import Ad, Snapshot, AiAnalysis
from config import OPENAI_API_KEY
from sqlalchemy import func

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

def run_analysis():
    logger.info("Running AI analysis...")
    db = SessionLocal()
    try:
        # Get all ads with their latest metrics
        ads = db.query(Ad).filter(Ad.status != "DELETED").all()
        ad_data = []
        for ad in ads:
            latest = db.query(Snapshot).filter_by(ad_id=ad.id).order_by(Snapshot.timestamp.desc()).first()
            if not latest or latest.spend == 0:
                continue
            ad_data.append({
                "id": ad.id,
                "name": ad.name,
                "status": ad.status,
                "ad_copy": ad.ad_copy or "N/A",
                "spend": latest.spend,
                "roas": latest.roas,
                "cpc": latest.cpc,
                "ctr": latest.ctr,
                "purchases": latest.purchases,
                "add_to_carts": latest.add_to_carts,
                "has_image": ad.creative_cached is not None,
            })

        if len(ad_data) < 2:
            logger.info("Not enough ads for analysis")
            return

        # Sort by ROAS
        ad_data.sort(key=lambda x: x["roas"], reverse=True)
        top_3 = ad_data[:3]
        bottom_3 = ad_data[-3:]

        # Build messages with images for top/bottom ads
        messages = [
            {"role": "system", "content": "You are an expert Meta ads analyst for NEWGARMENTS, a streetwear brand. Analyze ad performance data and creative images to find patterns. Be specific and actionable. Respond in JSON."},
        ]

        content_parts = [
            {"type": "text", "text": f"""Analyze these Meta ads performance data.

TOP PERFORMERS:
{json.dumps(top_3, indent=2)}

BOTTOM PERFORMERS:
{json.dumps(bottom_3, indent=2)}

Provide analysis as JSON with these keys:
- "top_vs_bottom": What do top performers have in common vs bottom performers?
- "visual_patterns": Patterns in visuals (style, colors, composition)
- "copy_patterns": Patterns in ad copy (hooks, tone, length, urgency)
- "recommendations": List of 3-5 concrete actionable recommendations
- "iterate_on": Which ad ID would you iterate on first and why?"""}
        ]

        # Add top performer images if available
        for ad in top_3:
            db_ad = db.query(Ad).filter_by(id=ad["id"]).first()
            if db_ad and db_ad.creative_cached:
                b64 = base64.b64encode(db_ad.creative_cached).decode()
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

        messages.append({"role": "user", "content": content_parts})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=2000,
        )

        analysis_text = response.choices[0].message.content
        analysis = json.loads(analysis_text)

        recommendations = "\n".join(f"• {r}" for r in analysis.get("recommendations", []))

        db.add(AiAnalysis(
            channel="meta",
            analysis_json=analysis_text,
            recommendations=recommendations,
        ))
        db.commit()
        logger.info("AI analysis complete")
    except Exception as e:
        db.rollback()
        logger.error(f"Analysis failed: {e}")
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add ad-command-center/analysis.py
git commit -m "feat: add AI creative analysis engine with GPT-4o Vision"
```

---

### Task 8: Iteration Pipeline

**Files:**
- Create: `ad-command-center/iteration.py`

- [ ] **Step 1: Write iteration.py**

```python
import json
import logging
import base64
from datetime import datetime
from openai import OpenAI
from db import SessionLocal
from models import Ad, IterationJob, Notification
from config import OPENAI_API_KEY, FAL_KEY, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, META_PAGE_ID
import meta_client
import httpx

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

async def generate_image_variation(original_image_b64: str, analysis: str) -> bytes:
    """Generate a visual variation using fal.ai"""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://queue.fal.run/fal-ai/nanobanana-2",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={
                "prompt": f"Professional streetwear product photography, flat lay style. {analysis}. Clean dark background, high fashion editorial. NEWGARMENTS brand aesthetic.",
                "image_url": f"data:image/jpeg;base64,{original_image_b64}",
                "strength": 0.6,
                "num_images": 1,
            },
            timeout=120,
        )
        data = r.json()
        image_url = data.get("images", [{}])[0].get("url", "")
        if image_url:
            img_r = await client.get(image_url, timeout=30)
            return img_r.content
    return b""

def generate_copy_variations(original_copy: str, analysis: str) -> list[str]:
    """Generate 3 copy variations using GPT-4o-mini"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You write short, punchy Meta ad copy for NEWGARMENTS streetwear. Max 2 sentences. Urgency + exclusivity tone."},
            {"role": "user", "content": f"Original ad copy: {original_copy}\n\nAnalysis of why it works: {analysis}\n\nWrite 3 different variations that keep what works but try new angles. Return as JSON array of strings."},
        ],
        response_format={"type": "json_object"},
        max_tokens=500,
    )
    data = json.loads(response.choices[0].message.content)
    return data.get("variations", data.get("copies", []))[:3]

def run_iteration(job_id: int):
    """Run full iteration pipeline for a job"""
    db = SessionLocal()
    try:
        job = db.query(IterationJob).filter_by(id=job_id).first()
        if not job:
            return

        job.status = "generating"
        db.commit()

        ad = db.query(Ad).filter_by(id=job.ad_id).first()
        if not ad or not ad.creative_cached:
            job.status = "failed"
            job.error = "No creative image cached for this ad"
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        # Step 1: Analyze what makes this ad work
        b64 = base64.b64encode(ad.creative_cached).decode()
        analysis_resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Analyze this ad creative. What visual elements, composition, and style make it effective? Be specific and concise."},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Ad copy: {ad.ad_copy or 'N/A'}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}
            ],
            max_tokens=500,
        )
        analysis = analysis_resp.choices[0].message.content

        # Step 2: Generate copy variations
        copies = generate_copy_variations(ad.ad_copy or "", analysis)

        # Step 3: Launch iterations via Meta API
        job.status = "launching"
        db.commit()

        import asyncio
        loop = asyncio.new_event_loop()

        # Find existing campaign & ad set
        campaigns = loop.run_until_complete(meta_client.fetch_campaigns())
        campaign = next((c for c in campaigns if "NEWG" in c["name"]), campaigns[0] if campaigns else None)
        if not campaign:
            raise Exception("No campaign found")

        ad_sets = loop.run_until_complete(meta_client.fetch_ad_sets(campaign["id"]))
        ad_set = ad_sets[0] if ad_sets else None
        if not ad_set:
            raise Exception("No ad set found")

        launched = 0
        for i, copy in enumerate(copies):
            try:
                # Upload original image as new creative (reuse same visual for now)
                act = f"act_{META_AD_ACCOUNT_ID}"

                # Upload image
                async def upload_and_create():
                    async with httpx.AsyncClient() as client:
                        r = await client.post(
                            f"https://graph.facebook.com/v21.0/{act}/adimages",
                            params={"access_token": META_ACCESS_TOKEN},
                            files={"filename": (f"iteration_{i}.jpg", ad.creative_cached, "image/jpeg")},
                            timeout=60,
                        )
                        img_data = r.json()
                        images = img_data.get("images", {})
                        image_hash = list(images.values())[0]["hash"] if images else None
                        if not image_hash:
                            raise Exception(f"Image upload failed: {img_data}")

                        # Create creative
                        creative = await meta_client.graph_post(f"/{act}/adcreatives", {
                            "name": f"Iteration {i+1} of {ad.name}",
                            "object_story_spec": {
                                "page_id": META_PAGE_ID,
                                "link_data": {
                                    "image_hash": image_hash,
                                    "message": copy,
                                    "link": "https://newgarments.store",
                                    "call_to_action": {"type": "SHOP_NOW"},
                                }
                            }
                        })

                        # Create ad
                        new_ad = await meta_client.graph_post(f"/{act}/ads", {
                            "name": f"{ad.name} - Iter {i+1}",
                            "adset_id": ad_set["id"],
                            "creative": {"creative_id": creative["id"]},
                            "status": "ACTIVE",
                        })
                        return new_ad

                result = loop.run_until_complete(upload_and_create())

                # Track in DB
                db.add(Ad(
                    id=result["id"], channel="meta",
                    name=f"{ad.name} - Iter {i+1}",
                    ad_set_id=ad_set["id"], status="ACTIVE",
                    ad_copy=copy, parent_ad_id=ad.id,
                    creative_cached=ad.creative_cached,
                ))
                launched += 1
            except Exception as e:
                logger.error(f"Failed to launch iteration {i+1}: {e}")

        loop.close()

        if launched > 0:
            job.status = "done"
            job.completed_at = datetime.utcnow()
            db.add(Notification(
                type="iteration_launched",
                message=f"Launched {launched} iterations of '{ad.name}'"
            ))
        else:
            job.status = "failed"
            job.error = "All iteration launches failed"
            job.completed_at = datetime.utcnow()

        db.commit()
    except Exception as e:
        logger.error(f"Iteration failed: {e}")
        job = db.query(IterationJob).filter_by(id=job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
```

- [ ] **Step 2: Commit**

```bash
git add ad-command-center/iteration.py
git commit -m "feat: add iteration pipeline (fal.ai + GPT copy + Meta launch)"
```

---

### Task 9: Main App Entry Point

**Files:**
- Create: `ad-command-center/main.py`

- [ ] **Step 1: Write main.py**

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import init_db
from config import SYNC_INTERVAL_MINUTES
from sync import run_sync
from analysis import run_analysis
from routes import auth, kpis, ads, notifications, analysis as analysis_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(run_sync, "interval", minutes=SYNC_INTERVAL_MINUTES, id="meta_sync")
    scheduler.add_job(run_analysis, "cron", hour=0, minute=0, id="daily_analysis")
    scheduler.start()
    logger.info(f"Scheduler started: sync every {SYNC_INTERVAL_MINUTES}min, analysis daily at midnight")
    # Run initial sync
    try:
        await run_sync()
    except Exception as e:
        logger.error(f"Initial sync failed: {e}")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# Routes
app.include_router(auth.router)
app.include_router(kpis.router)
app.include_router(ads.router)
app.include_router(notifications.router)
app.include_router(analysis_routes.router)

# Manual sync trigger
@app.post("/api/sync")
async def trigger_sync():
    await run_sync()
    return {"status": "done"}

# Serve frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")
```

- [ ] **Step 2: Create routes/__init__.py**

```python
# empty init
```

- [ ] **Step 3: Commit**

```bash
git add ad-command-center/main.py ad-command-center/routes/__init__.py
git commit -m "feat: add FastAPI app with scheduler and route registration"
```

---

### Task 10: Frontend Dashboard

**Files:**
- Create: `ad-command-center/static/index.html`

- [ ] **Step 1: Write index.html**

This is the largest file. Single HTML with inline CSS/JS. Key sections:
- Login screen (password input)
- KPI cards row (spend, ROAS, CPC, ATCs, purchases)
- Spend/Revenue chart (Chart.js)
- Creative grid (sortable cards with action buttons)
- AI Analysis section (top vs bottom, patterns, recommendations)
- Notification bell
- Budget adjust modal
- Auto-refresh every 10 minutes

The HTML should follow the NEWG brand: dark theme (#1a1a2e), accent #e04400, DM Sans font. Use Chart.js from CDN for charts. Fetch all data from /api/* endpoints with Bearer token auth.

Key frontend functions:
- `login()` — POST /api/auth/login, store token in localStorage
- `fetchKPIs()` — GET /api/kpis → render KPI cards with change indicators
- `fetchHistory()` — GET /api/kpis/history → render Chart.js bar+line chart
- `fetchAds()` — GET /api/ads → render creative grid with thumbnails (base64)
- `fetchAnalysis()` — GET /api/analysis → render AI analysis section
- `fetchNotifications()` — GET /api/notifications → badge count + dropdown
- `pauseAd(id)` — POST /api/ads/:id/pause → update card status
- `activateAd(id)` — POST /api/ads/:id/activate → update card status
- `iterateAd(id)` — POST /api/ads/:id/iterate → show "Generating..." status
- `adjustBudget()` — modal with input, POST budget update
- `autoRefresh()` — setInterval every 10min, re-fetch all data

Full implementation to be written during execution (800+ lines HTML/CSS/JS). Structure follows the decarba dashboard pattern from `decarba-remixer/src/dashboard/template.ts`.

- [ ] **Step 2: Commit**

```bash
git add ad-command-center/static/index.html
git commit -m "feat: add frontend dashboard with KPIs, charts, creative grid, AI analysis"
```

---

### Task 11: Railway Deployment

- [ ] **Step 1: Test locally**

```bash
cd ad-command-center
pip install -r requirements.txt
# Set env vars in .env file
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000, verify login, KPI loading, and ad grid.

- [ ] **Step 2: Create Railway project**

```bash
# Install Railway CLI if needed
# npm install -g @railway/cli
railway login
railway init
railway add --name postgres  # Add PostgreSQL plugin
```

- [ ] **Step 3: Set environment variables on Railway**

Set all variables from .env.example in Railway dashboard or CLI:
```bash
railway variables set META_ACCESS_TOKEN="..."
railway variables set META_AD_ACCOUNT_ID="675097301583244"
railway variables set META_PAGE_ID="..."
railway variables set META_PIXEL_ID="2589323428122293"
railway variables set OPENAI_API_KEY="..."
railway variables set FAL_KEY="..."
railway variables set DASHBOARD_SECRET="..."
railway variables set SYNC_INTERVAL_MINUTES="10"
railway variables set ROAS_ALERT_THRESHOLD="1.5"
railway variables set CPA_ALERT_THRESHOLD="15.0"
```

DATABASE_URL is auto-set by Railway when you add PostgreSQL.

- [ ] **Step 4: Deploy**

```bash
railway up
```

- [ ] **Step 5: Verify deployment**

Open the Railway-provided URL, login, and verify:
- KPI cards load with real Meta data
- Chart shows spend/revenue history
- Creative grid shows ads with thumbnails
- Pause/Activate buttons work
- AI analysis section loads (may be empty until first midnight run — use refresh button)
- Notifications badge works

- [ ] **Step 6: Commit deployment config**

```bash
git add ad-command-center/
git commit -m "feat: complete ad command center, ready for Railway deployment"
```

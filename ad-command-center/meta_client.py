import asyncio
import httpx
from config import GRAPH_API, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID

# Reuse a single client and add delays to avoid rate limiting
_client = None

async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30)
    return _client

async def graph_get(path: str) -> dict:
    await asyncio.sleep(2)  # Rate limit: max 2 requests/sec
    client = await _get_client()
    r = await client.get(
        f"{GRAPH_API}{path}",
        params={"access_token": META_ACCESS_TOKEN},
    )
    data = r.json()
    if "error" in data:
        raise Exception(f"Meta API error: {data['error'].get('message', data['error'])}")
    return data

async def graph_post(path: str, body: dict) -> dict:
    await asyncio.sleep(2)
    client = await _get_client()
    r = await client.post(
        f"{GRAPH_API}{path}",
        params={"access_token": META_ACCESS_TOKEN},
        json=body,
    )
    data = r.json()
    if "error" in data:
        raise Exception(f"Meta API error: {data['error'].get('message', data['error'])}")
    return data

def act_id():
    return f"act_{META_AD_ACCOUNT_ID}"

async def fetch_campaigns() -> list[dict]:
    data = await graph_get(f"/{act_id()}/campaigns?fields=id,name,status,daily_budget&filtering=[{{'field':'effective_status','operator':'IN','value':['ACTIVE','PAUSED']}}]&limit=50")
    return data.get("data", [])

async def fetch_ad_sets(campaign_id: str) -> list[dict]:
    data = await graph_get(f"/{campaign_id}/adsets?fields=id,name,status,daily_budget")
    return data.get("data", [])

async def fetch_ads(adset_id: str) -> list[dict]:
    data = await graph_get(f"/{adset_id}/ads?fields=id,name,status,creative")
    return data.get("data", [])

async def fetch_all_ads() -> list[dict]:
    """Fetch ALL ads at account level with insights inline — single API call."""
    data = await graph_get(
        f"/{act_id()}/ads?fields=id,name,status,creative,campaign{{id,name}},adset{{id,name,status,daily_budget}},"
        f"insights.date_preset(today){{spend,impressions,clicks,cpc,ctr,actions,action_values}}"
        f"&filtering=[{{'field':'effective_status','operator':'IN','value':['ACTIVE','PAUSED']}}]"
        f"&limit=100"
    )
    return data.get("data", [])

async def fetch_ad_insights(ad_id: str, date_preset: str = "today") -> dict | None:
    data = await graph_get(
        f"/{ad_id}/insights?fields=spend,impressions,clicks,cpc,ctr,actions,action_values"
        f"&date_preset={date_preset}"
    )
    results = data.get("data", [])
    return results[0] if results else None

async def fetch_creative_thumbnail(creative_id: str) -> str | None:
    data = await graph_get(f"/{creative_id}?fields=image_url,thumbnail_url,object_story_spec")
    # Prefer full-size image_url over tiny thumbnail_url
    return data.get("image_url") or data.get("thumbnail_url")

async def download_image(url: str) -> bytes:
    client = await _get_client()
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

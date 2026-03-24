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
    """Sync Meta ads data using minimal API calls to avoid rate limiting.

    Strategy: Use account-level ads endpoint to fetch everything in ~3 calls
    instead of traversing campaigns → ad sets → ads (N*M*K calls).
    """
    logger.info("Starting Meta sync...")
    db = SessionLocal()
    try:
        # Step 1: Fetch all active campaigns (1 API call)
        all_campaigns = await meta_client.fetch_campaigns()
        campaigns = [c for c in all_campaigns if c.get("status") == "ACTIVE"]
        logger.info(f"Found {len(campaigns)} active campaigns (of {len(all_campaigns)} total)")

        for c in campaigns:
            try:
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
            except Exception as e:
                logger.warning(f"Failed to sync campaign {c.get('id')}: {e}")
        db.flush()

        # Step 2: Fetch ALL ads at account level (1 API call instead of N*M)
        try:
            all_ads = await meta_client.fetch_all_ads()
            logger.info(f"Fetched {len(all_ads)} ads at account level")
        except Exception as e:
            logger.error(f"Failed to fetch ads: {e}")
            all_ads = []

        for ad in all_ads:
            try:
                ad_id = ad["id"]
                adset_data = ad.get("adset", {})
                adset_id = adset_data.get("id") or ad.get("adset_id")
                campaign_id = ad.get("campaign", {}).get("id") or ad.get("campaign_id")
                creative_id = ad.get("creative", {}).get("id")

                # Upsert ad set if we have data
                if adset_id and adset_data.get("name"):
                    existing_aset = db.query(AdSet).filter_by(id=adset_id).first()
                    if not existing_aset:
                        db.add(AdSet(
                            id=adset_id, channel="meta", name=adset_data["name"],
                            campaign_id=campaign_id, status=adset_data.get("status", "ACTIVE"),
                            daily_budget=int(adset_data.get("daily_budget", 0))
                        ))
                    else:
                        existing_aset.name = adset_data["name"]
                        existing_aset.status = adset_data.get("status", "ACTIVE")

                # Upsert ad
                existing_ad = db.query(Ad).filter_by(id=ad_id).first()
                if not existing_ad:
                    thumb_url = None
                    thumb_bytes = None
                    if creative_id:
                        try:
                            thumb_url = await meta_client.fetch_creative_thumbnail(creative_id)
                            if thumb_url:
                                thumb_bytes = await meta_client.download_image(thumb_url)
                        except Exception:
                            pass
                    db.add(Ad(
                        id=ad_id, channel="meta", name=ad["name"],
                        ad_set_id=adset_id, status=ad["status"],
                        creative_url=thumb_url, creative_cached=thumb_bytes,
                    ))
                else:
                    existing_ad.status = ad["status"]
                    existing_ad.name = ad["name"]
                db.flush()

                # Parse inline insights (already included in the API response)
                insights_data = ad.get("insights", {}).get("data", [])
                insights = insights_data[0] if insights_data else None

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
                                message=f"Ad '{ad['name']}' CPA is \u20ac{cpa:.2f} (above \u20ac{CPA_ALERT_THRESHOLD} threshold)"
                            ))
            except Exception as e:
                logger.warning(f"Failed to sync ad {ad.get('id')}: {e}")
                continue

        db.commit()
        logger.info("Meta sync complete")
    except Exception as e:
        db.rollback()
        logger.error(f"Sync failed: {e}")
        if "OAuthException" in str(e):
            try:
                db.add(Notification(type="token_expired", message="Meta access token expired. Please refresh."))
                db.commit()
            except Exception:
                pass
    finally:
        db.close()

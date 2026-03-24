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
                db.flush()
            except Exception as e:
                logger.warning(f"Failed to sync campaign {c.get('id')}: {e}")
                continue

            try:
                ad_sets = await meta_client.fetch_ad_sets(c["id"])
            except Exception as e:
                logger.warning(f"Failed to fetch ad sets for campaign {c['id']}: {e}")
                continue

            for aset in ad_sets:
                try:
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
                except Exception as e:
                    logger.warning(f"Failed to sync ad set {aset.get('id')}: {e}")
                    continue

                try:
                    ads = await meta_client.fetch_ads(aset["id"])
                except Exception as e:
                    logger.warning(f"Failed to fetch ads for ad set {aset['id']}: {e}")
                    continue

                for ad in ads:
                    try:
                        ad_id = ad["id"]
                        creative_id = ad.get("creative", {}).get("id")

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
                                ad_set_id=aset["id"], status=ad["status"],
                                creative_url=thumb_url, creative_cached=thumb_bytes,
                            ))
                        else:
                            existing_ad.status = ad["status"]
                            existing_ad.name = ad["name"]
                        db.flush()

                        try:
                            insights = await meta_client.fetch_ad_insights(ad_id)
                        except Exception:
                            insights = None

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

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

        recommendations = "\n".join(f"\u2022 {r}" for r in analysis.get("recommendations", []))

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

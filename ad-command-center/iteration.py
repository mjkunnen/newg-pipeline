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
            {"role": "user", "content": f"Original ad copy: {original_copy}\n\nAnalysis of why it works: {analysis}\n\nWrite 3 different variations that keep what works but try new angles. Return as JSON object with key \"variations\" containing an array of strings."},
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
                act = f"act_{META_AD_ACCOUNT_ID}"

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

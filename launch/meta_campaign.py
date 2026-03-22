"""
Meta Marketing API Campaign Launcher

Creates PAUSED campaigns with ad sets and ads via the Meta Marketing API.
Designed to be used standalone or as Stage 7 of the brand cloning pipeline.

Usage:
    from launch.meta_campaign import MetaCampaignLauncher

    launcher = MetaCampaignLauncher()
    result = launcher.launch(
        brand_name="NEWGARMENTS",
        product_urls=["https://newgarments.store/products/hoodie-1"],
        creative_image_paths=["path/to/image1.jpg", "path/to/image2.jpg"],
        ad_copy=[{"headline": "Shop Now", "body": "Limited drop", "cta": "SHOP_NOW"}],
        daily_budget_cents=3000,  # €30.00
        target_countries=["NL", "BE", "DE", "FR", "IT", "PL", "AT", "DK", "IE", "SE"],
    )
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_env():
    """Load environment variables from .env file."""
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

# Meta API config
META_API_VERSION = "v21.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"
AD_ACCOUNT_ID = "act_675097301583244"
PAGE_ID = "337283139475030"
PIXEL_ID = "2589323428122293"


def _get_token():
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise ValueError("META_ACCESS_TOKEN not found in environment or .env")
    return token


def _api_call(method, endpoint, params=None, data=None):
    """Make a Meta API call. Returns parsed JSON response."""
    url = f"{META_BASE_URL}/{endpoint}"
    token = _get_token()

    if method == "GET":
        params = params or {}
        params["access_token"] = token
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
        req = urllib.request.Request(url, method="GET")
    elif method == "POST":
        data = data or {}
        data["access_token"] = token
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
    else:
        raise ValueError(f"Unsupported method: {method}")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"Meta API Error ({e.code}): {error_body}", file=sys.stderr)
        raise RuntimeError(f"Meta API {method} {endpoint} failed: {error_body}") from e


class MetaCampaignLauncher:
    """Creates Meta ad campaigns via the Marketing API."""

    def __init__(self, ad_account_id=None, page_id=None, pixel_id=None):
        self.ad_account_id = ad_account_id or AD_ACCOUNT_ID
        self.page_id = page_id or PAGE_ID
        self.pixel_id = pixel_id or PIXEL_ID

    def create_campaign(self, name, objective="OUTCOME_SALES", status="PAUSED",
                        special_ad_categories=None):
        """Create a campaign. Returns campaign ID."""
        data = {
            "name": name,
            "objective": objective,
            "status": status,
            "special_ad_categories": json.dumps(special_ad_categories or []),
            "is_adset_budget_sharing_enabled": "false",
        }
        result = _api_call("POST", f"{self.ad_account_id}/campaigns", data=data)
        campaign_id = result["id"]
        print(f"Campaign created: {campaign_id} ({name})")
        return campaign_id

    def create_adset(self, campaign_id, name, daily_budget_cents=3000,
                     target_countries=None, age_min=18, age_max=65,
                     optimization_goal="OFFSITE_CONVERSIONS",
                     billing_event="IMPRESSIONS", status="PAUSED",
                     bid_strategy="LOWEST_COST_WITHOUT_CAP"):
        """Create an ad set with targeting. Returns ad set ID."""
        countries = target_countries or ["NL", "BE", "DE", "FR", "IT", "PL",
                                          "AT", "DK", "IE", "SE"]
        targeting = {
            "geo_locations": {"countries": countries},
            "age_min": age_min,
            "age_max": age_max,
        }

        # Start time = tomorrow to give Meta time to review
        start_time = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+0000")

        data = {
            "campaign_id": campaign_id,
            "name": name,
            "daily_budget": str(daily_budget_cents),
            "targeting": json.dumps(targeting),
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "bid_strategy": bid_strategy,
            "status": status,
            "start_time": start_time,
            "promoted_object": json.dumps({"pixel_id": self.pixel_id, "custom_event_type": "PURCHASE"}),
        }
        result = _api_call("POST", f"{self.ad_account_id}/adsets", data=data)
        adset_id = result["id"]
        print(f"Ad set created: {adset_id} ({name})")
        return adset_id

    def upload_image(self, image_path):
        """Upload an image to the ad account. Returns image hash."""
        import base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        data = {
            "bytes": image_data,
            "access_token": _get_token(),
        }
        # Use multipart-like approach via bytes parameter
        body = urllib.parse.urlencode(data).encode("utf-8")
        url = f"{META_BASE_URL}/{self.ad_account_id}/adimages"
        req = urllib.request.Request(url, data=body, method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Image upload failed: {error_body}") from e

        # Response format: {"images": {"bytes": {"hash": "...", "url": "..."}}}
        images = result.get("images", {})
        for key, img_data in images.items():
            image_hash = img_data["hash"]
            print(f"Image uploaded: {image_hash} ({Path(image_path).name})")
            return image_hash

        raise RuntimeError(f"Unexpected image upload response: {result}")

    def upload_image_from_url(self, image_url):
        """Upload an image from URL to the ad account. Returns image hash."""
        data = {
            "url": image_url,
        }
        result = _api_call("POST", f"{self.ad_account_id}/adimages", data=data)
        images = result.get("images", {})
        for key, img_data in images.items():
            image_hash = img_data["hash"]
            print(f"Image uploaded from URL: {image_hash}")
            return image_hash
        raise RuntimeError(f"Unexpected image upload response: {result}")

    def create_ad_creative(self, name, image_hash, headline, body_text,
                           destination_url, cta_type="SHOP_NOW",
                           link_description=""):
        """Create an ad creative. Returns creative ID."""
        object_story_spec = {
            "page_id": self.page_id,
            "link_data": {
                "image_hash": image_hash,
                "link": destination_url,
                "message": body_text,
                "name": headline,
                "call_to_action": {"type": cta_type, "value": {"link": destination_url}},
            },
        }
        if link_description:
            object_story_spec["link_data"]["description"] = link_description

        data = {
            "name": name,
            "object_story_spec": json.dumps(object_story_spec),
        }
        result = _api_call("POST", f"{self.ad_account_id}/adcreatives", data=data)
        creative_id = result["id"]
        print(f"Creative created: {creative_id} ({name})")
        return creative_id

    def create_ad(self, adset_id, creative_id, name, status="PAUSED"):
        """Create an ad. Returns ad ID."""
        data = {
            "name": name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": status,
        }
        result = _api_call("POST", f"{self.ad_account_id}/ads", data=data)
        ad_id = result["id"]
        print(f"Ad created: {ad_id} ({name})")
        return ad_id

    def launch(self, brand_name, product_urls, creative_image_paths=None,
               creative_image_urls=None, ad_copy=None, daily_budget_cents=3000,
               target_countries=None, age_min=18, age_max=34):
        """
        Full campaign launch flow.

        Args:
            brand_name: Brand name for campaign naming
            product_urls: List of destination URLs for ads
            creative_image_paths: List of local image file paths
            creative_image_urls: List of image URLs (alternative to paths)
            ad_copy: List of dicts with 'headline', 'body', 'cta' keys
            daily_budget_cents: Daily budget in cents (3000 = €30.00)
            target_countries: List of country codes
            age_min: Minimum target age
            age_max: Maximum target age

        Returns:
            dict with campaign_id, adset_id, ad_ids, and summary
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Default ad copy if none provided
        if not ad_copy:
            ad_copy = [{"headline": f"Shop {brand_name}", "body": "Shop the latest collection", "cta": "SHOP_NOW"}]

        # Default destination URL
        if not product_urls:
            raise ValueError("At least one product_url is required")

        # 1. Create Campaign (PAUSED)
        campaign_name = f"{brand_name} - Launch - {today}"
        campaign_id = self.create_campaign(campaign_name)

        # 2. Create Ad Set (PAUSED)
        adset_name = f"{brand_name} - Prospecting - {today}"
        adset_id = self.create_adset(
            campaign_id=campaign_id,
            name=adset_name,
            daily_budget_cents=daily_budget_cents,
            target_countries=target_countries,
            age_min=age_min,
            age_max=age_max,
        )

        # 3. Upload images and create ads
        image_hashes = []
        if creative_image_paths:
            for path in creative_image_paths:
                h = self.upload_image(path)
                image_hashes.append(h)
        elif creative_image_urls:
            for url in creative_image_urls:
                h = self.upload_image_from_url(url)
                image_hashes.append(h)
        else:
            raise ValueError("Provide either creative_image_paths or creative_image_urls")

        ad_ids = []
        for i, image_hash in enumerate(image_hashes):
            copy = ad_copy[i % len(ad_copy)]
            dest_url = product_urls[i % len(product_urls)]

            # Create creative
            creative_name = f"{brand_name} - Creative {i+1}"
            creative_id = self.create_ad_creative(
                name=creative_name,
                image_hash=image_hash,
                headline=copy.get("headline", f"Shop {brand_name}"),
                body_text=copy.get("body", ""),
                destination_url=dest_url,
                cta_type=copy.get("cta", "SHOP_NOW"),
            )

            # Create ad
            ad_name = f"{brand_name} - Ad {i+1}"
            ad_id = self.create_ad(adset_id, creative_id, ad_name)
            ad_ids.append(ad_id)

        result = {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "adset_id": adset_id,
            "ad_ids": ad_ids,
            "status": "PAUSED",
            "daily_budget": f"€{daily_budget_cents/100:.2f}",
            "target_countries": target_countries or ["NL", "BE", "DE", "FR", "IT", "PL", "AT", "DK", "IE", "SE"],
            "num_ads": len(ad_ids),
            "created_at": today,
        }

        print(f"\n{'='*50}")
        print(f"Campaign '{campaign_name}' created as DRAFT")
        print(f"  {len(ad_ids)} ads ready")
        print(f"  Budget: €{daily_budget_cents/100:.2f}/day")
        print(f"  Status: PAUSED — review and activate in Ads Manager")
        print(f"{'='*50}")

        # Save report
        run_dir = PROJECT_ROOT / "clone_runs"
        run_dir.mkdir(exist_ok=True)
        report_path = run_dir / f"campaign_report_{today}_{brand_name.replace(' ', '_')}.json"
        with open(report_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Report saved: {report_path}")

        return result


def get_account_info():
    """Get ad account info for verification."""
    result = _api_call("GET", AD_ACCOUNT_ID, params={
        "fields": "name,account_status,currency,balance"
    })
    return result


if __name__ == "__main__":
    # Quick test: verify API access
    print("Verifying Meta API access...")
    info = get_account_info()
    print(f"Ad Account: {info.get('name')} (Status: {info.get('account_status')})")
    print(f"Currency: {info.get('currency')}")
    print("API access verified!")

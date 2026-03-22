"""
Capture module — downloads source images/videos from URLs.
No Playwright needed. Uses HTTP requests for Pinterest and yt-dlp for TikTok.
"""
import os
import json
import logging
import requests
from datetime import date
from pathlib import Path

logger = logging.getLogger("pipeline.capture")

OUTPUT_DIR = Path(__file__).parent / "output"


def capture_pinterest_pin(image_url: str, pin_id: str, description: str = "") -> dict:
    """Download a Pinterest pin image from its direct URL (provided by Zapier)."""
    today = date.today().isoformat()
    source_dir = OUTPUT_DIR / today / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    ext = "jpg"
    if ".png" in image_url.lower():
        ext = "png"

    filename = f"pin-{pin_id}.{ext}"
    filepath = source_dir / filename

    logger.info(f"Downloading pin {pin_id} from {image_url[:80]}...")
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    filepath.write_bytes(resp.content)
    logger.info(f"Saved source image: {filepath}")

    return {
        "source_type": "pinterest",
        "pin_id": pin_id,
        "image_url": image_url,
        "description": description,
        "local_path": str(filepath),
        "date": today,
    }


def capture_tiktok(tiktok_url: str) -> dict:
    """Capture TikTok content using oembed API for metadata + yt-dlp for video."""
    import subprocess

    today = date.today().isoformat()
    source_dir = OUTPUT_DIR / today / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    # Get metadata via oembed
    oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
    logger.info(f"Fetching TikTok metadata: {tiktok_url}")
    resp = requests.get(oembed_url, timeout=15)
    metadata = {}
    if resp.ok:
        metadata = resp.json()

    # Extract a video ID from the URL
    video_id = tiktok_url.rstrip("/").split("/")[-1].split("?")[0]

    # Download thumbnail
    thumbnail_path = None
    if metadata.get("thumbnail_url"):
        thumbnail_path = source_dir / f"tiktok-{video_id}-thumb.jpg"
        thumb_resp = requests.get(metadata["thumbnail_url"], timeout=15)
        if thumb_resp.ok:
            thumbnail_path.write_bytes(thumb_resp.content)
            logger.info(f"Saved thumbnail: {thumbnail_path}")

    # Try downloading video with yt-dlp
    video_path = source_dir / f"tiktok-{video_id}.mp4"
    try:
        result = subprocess.run(
            ["yt-dlp", "-o", str(video_path), "--no-warnings", "-q", tiktok_url],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            logger.warning(f"yt-dlp failed: {result.stderr[:200]}")
            video_path = None
        else:
            logger.info(f"Downloaded video: {video_path}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"yt-dlp error: {e}")
        video_path = None

    return {
        "source_type": "tiktok",
        "video_id": video_id,
        "url": tiktok_url,
        "title": metadata.get("title", ""),
        "author": metadata.get("author_name", ""),
        "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
        "video_path": str(video_path) if video_path else None,
        "local_path": str(thumbnail_path or video_path),
        "date": today,
    }

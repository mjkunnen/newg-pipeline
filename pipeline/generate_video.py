"""
Video generation module — uses Kling v2 via Replicate for image-to-video generation.
Only runs when the source creative is a video.
"""
import os
import json
import logging
import requests
import replicate
from pathlib import Path
from datetime import date

logger = logging.getLogger("pipeline.generate_video")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def generate_video_from_image(
    image_path: str,
    motion_prompt: str = "slow zoom in, subtle camera movement",
    duration: str = "5s",
) -> str | None:
    """Generate a short video from a product image using Kling v2 on Replicate.

    Returns the video URL or None if failed.
    """
    logger.info(f"Generating video from: {image_path}")

    try:
        output = replicate.run(
            "kling-ai/kling-v2",
            input={
                "image": open(image_path, "rb"),
                "prompt": motion_prompt,
                "duration": duration,
                "aspect_ratio": "9:16",
            }
        )
        if output:
            video_url = str(output)
            logger.info(f"Generated video: {video_url[:80]}...")
            return video_url
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        return None

    return None


def download_video(video_url: str, save_path: str) -> str:
    """Download generated video to local path."""
    resp = requests.get(video_url, timeout=120)
    resp.raise_for_status()
    Path(save_path).write_bytes(resp.content)
    return save_path


def generate_videos_for_images(
    generated_images: list[dict],
    motion_prompt: str = "slow product reveal, subtle zoom, cinematic lighting",
) -> list[dict]:
    """Generate videos for all successfully generated images.

    Takes the output of generate_image.generate_for_catalog() and creates
    video versions for each.
    """
    today = date.today().isoformat()
    results = []

    for img in generated_images:
        if img.get("status") != "success":
            continue

        image_path = img["local_path"]
        video_dir = Path(image_path).parent
        video_filename = Path(image_path).stem + ".mp4"
        video_path = str(video_dir / video_filename)

        video_url = generate_video_from_image(image_path, motion_prompt)
        if video_url:
            download_video(video_url, video_path)
            results.append({
                **img,
                "video_path": video_path,
                "video_url": video_url,
                "video_status": "success",
            })
            logger.info(f"Video: {img['product_name']} ({img['colorway']}) -> {video_path}")
        else:
            results.append({
                **img,
                "video_status": "failed",
            })

    return results

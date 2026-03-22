"""
Delivery module — uploads generated creatives to Google Drive via Zapier MCP.
Organizes files in: NEWGARMENTS Remakes / YYYY-MM-DD / Collection / files
"""
import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger("pipeline.deliver")


def build_delivery_manifest(
    source_info: dict,
    creative_brief: dict,
    generated_images: list[dict],
    generated_videos: list[dict] | None = None,
) -> dict:
    """Build a manifest of all files to deliver, organized by collection."""
    today = date.today().isoformat()

    collections = {}
    for img in generated_images:
        if img.get("status") != "success":
            continue
        col = img.get("collection", "outfits")
        if col not in collections:
            collections[col] = []
        entry = {
            "outfit_label": img.get("outfit_label", img.get("product_name", "")),
            "top": img.get("top", ""),
            "bottom": img.get("bottom", ""),
            "shoes": img.get("shoes", ""),
            "local_path": img["local_path"],
            "type": "image",
        }
        # Check if there's a video version
        if generated_videos:
            for vid in generated_videos:
                if (vid.get("outfit_id") == img.get("outfit_id") and
                    vid.get("video_status") == "success"):
                    entry["video_path"] = vid["video_path"]
                    break
        collections[col].append(entry)

    manifest = {
        "date": today,
        "source": source_info,
        "creative_brief_summary": {
            "visual_style": creative_brief.get("visual_style"),
            "layout_type": creative_brief.get("layout_type"),
            "mood": creative_brief.get("mood"),
        },
        "collections": collections,
        "total_images": sum(len(v) for v in collections.values()),
        "drive_structure": {
            "root": "NEWGARMENTS Remakes",
            "date_folder": today,
            "collection_folders": list(collections.keys()),
        },
    }

    return manifest


def save_manifest(manifest: dict, output_dir: str) -> str:
    """Save delivery manifest to disk."""
    manifest_path = Path(output_dir) / manifest["date"] / "delivery_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Saved delivery manifest: {manifest_path}")
    return str(manifest_path)


def get_files_for_upload(manifest: dict) -> list[dict]:
    """Extract flat list of files to upload with their target Drive paths.

    Returns list of dicts with 'local_path', 'drive_folder', 'filename'.
    These can be used with Zapier Google Drive MCP upload_file tool.
    """
    files = []
    date_folder = manifest["date"]
    root = manifest["drive_structure"]["root"]

    for collection, items in manifest["collections"].items():
        drive_folder = f"{root}/{date_folder}/{collection}"
        for item in items:
            # Image
            local_path = item["local_path"]
            filename = Path(local_path).name
            files.append({
                "local_path": local_path,
                "drive_folder": drive_folder,
                "filename": filename,
                "type": "image",
                "product": item["product"],
                "colorway": item["colorway"],
            })
            # Video (if exists)
            if "video_path" in item:
                video_filename = Path(item["video_path"]).name
                files.append({
                    "local_path": item["video_path"],
                    "drive_folder": drive_folder,
                    "filename": video_filename,
                    "type": "video",
                    "product": item["product"],
                    "colorway": item["colorway"],
                })

    return files

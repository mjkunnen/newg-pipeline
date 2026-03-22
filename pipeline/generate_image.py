"""
Image generation module — uses Nano Banana 2 via fal.ai to generate
outfit creatives with text/copy baked directly into the image.

Generates full outfits (top + bottom + shoes) and iterates through
all combinations from the catalog.
"""
import os
import json
import logging
import requests
from itertools import product as itertools_product
from pathlib import Path
from datetime import date

logger = logging.getLogger("pipeline.generate_image")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

FAL_KEY = os.getenv("FAL_KEY")
FAL_GENERATE_URL = "https://queue.fal.run/fal-ai/nano-banana-2"
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"

BRAND_CAPTIONS = [
    "not made for everyone",
    "460 GSM. your hoodie weighs half this.",
    "built, not printed.",
    "50 made. archive when gone.",
    "stop dressing like a background character",
    "for the ones who know",
    "feel the difference.",
    "no restock. no exceptions.",
    "your outfit says everything before you even speak",
    "main character energy or nothing",
]


def extract_outfit_pieces(catalog: dict) -> dict:
    """Extract products by category: tops, bottoms, footwear."""
    tops = []
    bottoms = []
    footwear = []

    all_products = []
    if "collections" in catalog:
        for col_data in catalog["collections"].values():
            for p in col_data.get("products", []):
                all_products.append(p)
    else:
        all_products = catalog.get("products", [])

    for p in all_products:
        cat = p.get("category", "").lower()
        if cat == "tops":
            tops.append(p)
        elif cat == "bottoms":
            bottoms.append(p)
        elif cat == "footwear":
            footwear.append(p)

    return {"tops": tops, "bottoms": bottoms, "footwear": footwear}


def generate_outfit_combinations(pieces: dict) -> list[dict]:
    """Generate all outfit combinations (top × bottom × shoes).

    Returns list of outfit dicts, each with top, bottom, shoes keys.
    """
    tops = pieces.get("tops", [])
    bottoms = pieces.get("bottoms", [])
    footwear = pieces.get("footwear", [])

    if not tops:
        logger.warning("No tops found in catalog")
        return []

    outfits = []
    for top, bottom, shoes in itertools_product(tops, bottoms or [None], footwear or [None]):
        outfit = {"top": top}
        if bottom:
            outfit["bottom"] = bottom
        if shoes:
            outfit["shoes"] = shoes
        outfits.append(outfit)

    logger.info(f"Generated {len(outfits)} outfit combinations: "
                f"{len(tops)} tops × {len(bottoms)} bottoms × {len(footwear)} shoes")
    return outfits


def build_outfit_edit_prompt(outfit: dict, image_type: str = "outfit_image", caption_index: int = 0, num_product_images: int = 0) -> str:
    """Build an edit instruction for Nano Banana 2 Edit endpoint.

    The first image in image_urls is the source photo (Pinterest reference).
    The following images are product reference photos showing the actual items.
    The prompt tells the model which image is which.
    """
    # Build image reference descriptions
    img_refs = []
    img_idx = 2  # image 1 = source photo
    if num_product_images > 0:
        img_refs.append(f"Image {img_idx} shows the top: {outfit['top']['name']}")
        img_idx += 1
    if "bottom" in outfit and num_product_images > 1:
        img_refs.append(f"Image {img_idx} shows the bottom: {outfit['bottom']['name']}")
        img_idx += 1
    if "shoes" in outfit and num_product_images > 2:
        img_refs.append(f"Image {img_idx} shows the shoes: {outfit['shoes']['name']}")
        img_idx += 1

    ref_text = " ".join(img_refs) if img_refs else ""

    prompt = (
        f"Image 1 is the source photo. Keep everything in Image 1 exactly the same — "
        f"same person, same pose, same background, same lighting, same camera angle, "
        f"same composition. ONLY change the clothing/outfit. "
    )

    if ref_text:
        prompt += (
            f"{ref_text}. "
            f"Replace the outfit on the person in Image 1 with EXACTLY these product items "
            f"as shown in the reference images. Match the colors, patterns, textures, and details "
            f"of each product precisely. The outfit should look natural and photorealistic on the person."
        )
    else:
        outfit_parts = [outfit["top"]["name"]]
        if "bottom" in outfit:
            outfit_parts.append(outfit["bottom"]["name"])
        if "shoes" in outfit:
            outfit_parts.append(outfit["shoes"]["name"])
        outfit_desc = ", ".join(outfit_parts)
        prompt += (
            f"Replace the current outfit with: {outfit_desc}. "
            f"The outfit should look natural and photorealistic on the person."
        )

    # Add text overlay only for static ads
    if image_type == "static_ad":
        caption = BRAND_CAPTIONS[caption_index % len(BRAND_CAPTIONS)]
        prompt += (
            f' Add text overlay: "{caption}" in lowercase, clean sans-serif font. '
            f"Brand: NEWGARMENTS in small text."
        )

    return prompt


def outfit_id(outfit: dict) -> str:
    """Generate a short ID string for an outfit combination."""
    parts = [outfit["top"]["id"]]
    if "bottom" in outfit:
        parts.append(outfit["bottom"]["id"])
    if "shoes" in outfit:
        parts.append(outfit["shoes"]["id"])
    return "_x_".join(parts)


def outfit_label(outfit: dict) -> str:
    """Generate a human-readable label for an outfit."""
    parts = [outfit["top"]["name"]]
    if "bottom" in outfit:
        parts.append(outfit["bottom"]["name"])
    if "shoes" in outfit:
        parts.append(outfit["shoes"]["name"])
    return " + ".join(parts)


def _poll_fal_result(queue_response: dict, headers: dict) -> dict | None:
    """Poll fal.ai queue for a completed result.

    Uses status_url and response_url from the initial queue response.
    """
    import time
    status_url = queue_response["status_url"]
    result_url = queue_response["response_url"]

    for _ in range(60):  # max 5 minutes
        time.sleep(5)
        status_resp = requests.get(status_url, headers=headers, timeout=15)
        status_data = status_resp.json()
        if status_data.get("status") == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=15)
            return result_resp.json()
        elif status_data.get("status") in ("FAILED", "CANCELLED"):
            logger.error(f"Generation failed: {status_data}")
            return None
    logger.error("Generation timed out")
    return None


def _extract_image_url(result: dict) -> str | None:
    """Extract image URL from fal.ai response."""
    images = result.get("images", [])
    if images:
        return images[0].get("url")
    return None


def _encode_image(image_path: str) -> str:
    """Encode a local image file as a base64 data URL."""
    import base64
    image_data = Path(image_path).read_bytes()
    b64 = base64.b64encode(image_data).decode("utf-8")
    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return f"data:{mime};base64,{b64}"


PRODUCT_REFS_DIR = Path(__file__).parent.parent / "content-library" / "product-refs"


def _get_product_ref_path(product_id: str) -> str | None:
    """Find the local reference image for a product ID."""
    for ext in ("png", "jpg", "jpeg", "webp"):
        path = PRODUCT_REFS_DIR / f"{product_id}.{ext}"
        if path.exists():
            return str(path)
    return None


def edit_image_with_reference(source_image_path: str, edit_prompt: str, product_ref_paths: list[str] = None) -> str | None:
    """Edit an existing image using Nano Banana 2 Edit endpoint.

    Sends the source image (Pinterest) + product reference images so the model
    can see exactly what the products look like.
    Returns the generated image URL.
    """
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    # Image 1: source photo (Pinterest reference)
    image_urls = [_encode_image(source_image_path)]

    # Images 2+: product reference photos
    if product_ref_paths:
        for ref_path in product_ref_paths:
            image_urls.append(_encode_image(ref_path))

    logger.info(f"Editing image via Nano Banana 2 Edit — {len(image_urls)} images (1 source + {len(image_urls)-1} product refs)")

    payload = {
        "prompt": edit_prompt,
        "image_urls": image_urls,
    }

    resp = requests.post(FAL_EDIT_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        result = _poll_fal_result(result, headers)
        if not result:
            return None

    image_url = _extract_image_url(result)
    if image_url:
        logger.info(f"Edited image: {image_url[:80]}...")
    else:
        logger.error(f"No images in response: {result}")
    return image_url


def generate_single_image(prompt: str, aspect_ratio: str = "9:16") -> str | None:
    """Generate a new image from scratch (no reference). Returns image URL."""
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "num_images": 1,
    }

    logger.info("Generating image via Nano Banana 2 (fal.ai)...")

    resp = requests.post(FAL_GENERATE_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        result = _poll_fal_result(result, headers)
        if not result:
            return None

    image_url = _extract_image_url(result)
    if image_url:
        logger.info(f"Generated image: {image_url[:80]}...")
    else:
        logger.error(f"No images in response: {result}")
    return image_url


def download_image(image_url: str, save_path: str) -> str:
    """Download a generated image to local path."""
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    Path(save_path).write_bytes(resp.content)
    return save_path


def generate_for_catalog(
    creative_brief: dict,
    catalog: dict,
    source_image_path: str,
    output_base: str = None,
    outfit_list: list[dict] = None,
) -> list[dict]:
    """Generate outfit images by editing the source image with each outfit combo.

    Uses Nano Banana 2 Edit endpoint — keeps the source image exactly the same
    (person, pose, background, lighting) and only swaps the outfit.

    Args:
        creative_brief: Analysis of the source image
        catalog: Product catalog
        source_image_path: Path to the Pinterest source image (used as reference)
        output_base: Output directory
        outfit_list: Optional list of specific outfit dicts to generate.
                     If None, generates all combinations from catalog.

    Returns list of dicts with outfit info and generated image paths.
    """
    today = date.today().isoformat()
    if output_base is None:
        output_base = str(Path(__file__).parent / "output" / today / "generated")

    # Use provided outfits or generate all combinations
    if outfit_list is not None:
        outfits = outfit_list
    else:
        pieces = extract_outfit_pieces(catalog)
        outfits = generate_outfit_combinations(pieces)

    if not outfits:
        logger.error("No outfit combinations to generate")
        return []

    image_type = creative_brief.get("image_type", "outfit_image")
    logger.info(f"Editing source image with {len(outfits)} outfit variations...")
    logger.info(f"Source: {source_image_path}")
    logger.info(f"Image type: {image_type}")

    results = []
    outfit_dir = Path(output_base) / "outfits"
    outfit_dir.mkdir(parents=True, exist_ok=True)

    for i, outfit in enumerate(outfits):
        oid = outfit_id(outfit)
        label = outfit_label(outfit)
        logger.info(f"[{i+1}/{len(outfits)}] Outfit: {label}")

        # Collect product reference image paths
        product_refs = []
        top_ref = _get_product_ref_path(outfit["top"]["id"])
        if top_ref:
            product_refs.append(top_ref)
        if "bottom" in outfit:
            bottom_ref = _get_product_ref_path(outfit["bottom"]["id"])
            if bottom_ref:
                product_refs.append(bottom_ref)
        if "shoes" in outfit:
            shoes_ref = _get_product_ref_path(outfit["shoes"]["id"])
            if shoes_ref:
                product_refs.append(shoes_ref)

        edit_prompt = build_outfit_edit_prompt(outfit, image_type, i, len(product_refs))

        image_url = edit_image_with_reference(source_image_path, edit_prompt, product_refs)
        if not image_url:
            logger.error(f"Failed: {label}")
            results.append({
                "outfit_id": oid,
                "outfit_label": label,
                "top": outfit["top"]["name"],
                "bottom": outfit.get("bottom", {}).get("name", ""),
                "shoes": outfit.get("shoes", {}).get("name", ""),
                "collection": "outfits",
                "status": "failed",
                "prompt": edit_prompt,
            })
            continue

        filename = f"{oid}.png"
        local_path = str(outfit_dir / filename)
        download_image(image_url, local_path)

        results.append({
            "outfit_id": oid,
            "outfit_label": label,
            "top": outfit["top"]["name"],
            "bottom": outfit.get("bottom", {}).get("name", ""),
            "shoes": outfit.get("shoes", {}).get("name", ""),
            "collection": "outfits",
            "status": "success",
            "local_path": local_path,
            "image_url": image_url,
            "prompt": edit_prompt,
        })
        logger.info(f"Generated: {label} -> {local_path}")

    successful = [r for r in results if r["status"] == "success"]
    logger.info(f"Done: {len(successful)}/{len(results)} outfits generated successfully")
    return results

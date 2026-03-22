"""
Analyze module — uses OpenAI Vision (GPT-4o) to analyze source creatives
and produce a structured creative brief for image generation.
"""
import os
import json
import base64
import logging
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger("pipeline.analyze")

# Load API key from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ANALYSIS_PROMPT = """You are a creative director analyzing a competitor's ad/pin for a premium Gen Z streetwear brand (NEWGARMENTS).

First, determine what TYPE of image this is:
- "static_ad": Has text overlays, brand logos, pricing, call-to-action, or any marketing copy on the image
- "outfit_image": Just a person wearing an outfit — no text, no branding, no marketing elements. Could be a mirror selfie, street photo, or lifestyle shot.

Then analyze and return a JSON object with these exact fields:

{
  "image_type": "static_ad | outfit_image",
  "layout_type": "mirror-selfie | street-shot | studio | lifestyle-overlay | flat-lay | grid | editorial",
  "text_on_image": ["list", "of", "text", "visible", "on", "the", "image"],
  "has_text_overlay": true/false,
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "visual_style": "describe the overall visual aesthetic in 3-5 words",
  "mood": "describe the mood/feeling in 2-3 words",
  "background_description": "describe the background/setting in detail",
  "typography_style": "describe font style, weight, color, positioning — or 'none' if no text",
  "aspect_ratio": "9:16 | 2:3 | 1:1 | 4:5",
  "source_type": "image | video",
  "camera_angle": "straight-on | top-down | 45-degree | low-angle",
  "lighting": "describe the lighting setup",
  "prompt_reconstruction": "Write a detailed image generation prompt that would recreate this exact visual style but with [PRODUCT] as the outfit. Include background, lighting, composition, color grading, camera angle, and perspective. The prompt should be ready to use with an AI image generator — just replace [PRODUCT] with actual outfit details. Do NOT include any text overlay instructions if image_type is outfit_image."
}

CRITICAL RULES:
- If image_type is "outfit_image", the prompt_reconstruction must NOT mention any text overlays, brand names, prices, or marketing copy. Just describe the visual scene and where [PRODUCT] goes.
- If image_type is "static_ad", include text overlay instructions in the prompt_reconstruction.
- The prompt_reconstruction should be detailed enough to recreate the visual style exactly.

Return ONLY valid JSON, no markdown formatting."""


def analyze_creative(image_path: str, source_description: str = "") -> dict:
    """Analyze a source creative image using OpenAI Vision."""
    logger.info(f"Analyzing creative: {image_path}")

    # Read and encode image
    image_data = Path(image_path).read_bytes()
    base64_image = base64.b64encode(image_data).decode("utf-8")

    # Detect mime type
    ext = Path(image_path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext.lstrip("."), "image/jpeg")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": ANALYSIS_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{base64_image}",
                        "detail": "high"
                    }
                },
            ],
        }
    ]

    if source_description:
        messages[0]["content"].insert(1, {
            "type": "text",
            "text": f"Additional context — this pin/post had the following description: {source_description}"
        })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1500,
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    brief = json.loads(raw)
    logger.info(f"Creative brief: style={brief.get('visual_style')}, layout={brief.get('layout_type')}")
    return brief

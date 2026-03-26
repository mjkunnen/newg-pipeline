import { fal } from "@fal-ai/client";
import OpenAI from "openai";
import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import sharp from "sharp";
import type { TaobaoProduct } from "../scraper/taobao.js";

const OUTPUT_DIR = join(import.meta.dirname, "../../output/products");
const ASSETS_DIR = join(import.meta.dirname, "../../assets");

// Off-white background matching premium e-commerce style
const BG_COLOR = { r: 244, g: 244, b: 244, alpha: 1 };

// ---- Image analysis & selection ----

interface ImageAnalysis {
  index: number;
  type: "flat_lay" | "model_front" | "model_back" | "hanger" | "detail" | "lifestyle" | "duplicate" | "unusable";
  quality: number; // 1-10
  processing: "bg_removal_straighten" | "bg_removal_only" | "keep_original" | "skip";
  reason: string;
}

interface SelectionResult {
  selected: ImageAnalysis[];
  heroIndex: number;
}

async function selectBestImages(
  imagePaths: string[],
): Promise<SelectionResult> {
  if (!process.env.OPENAI_API_KEY) {
    console.log("[product-images] No OPENAI_API_KEY, processing all images with bg removal");
    return {
      selected: imagePaths.map((_, i) => ({
        index: i,
        type: "flat_lay" as const,
        quality: 5,
        processing: "bg_removal_only" as const,
        reason: "no API key, default processing",
      })),
      heroIndex: 0,
    };
  }

  const openai = new OpenAI();

  const imageContent: Array<{ type: "image_url"; image_url: { url: string } }> = [];
  for (const imgPath of imagePaths) {
    const buffer = await readFile(imgPath);
    const preview = await sharp(buffer)
      .resize(400, 400, { fit: "inside" })
      .jpeg({ quality: 70 })
      .toBuffer();
    imageContent.push({
      type: "image_url",
      image_url: { url: `data:image/jpeg;base64,${preview.toString("base64")}` },
    });
  }

  const response = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: `You are an e-commerce product image curator for a premium streetwear brand (NEWGARMENTS).

You receive multiple product images and must decide which to use for the Shopify listing and how to process each.

Image types:
- flat_lay: garment laid flat on surface, photographed from above
- model_front: model wearing the garment, front view (person visible)
- model_back: model wearing the garment, back view (person visible)
- hanger: garment displayed on a hanger, mannequin, or ghost mannequin
- detail: close-up of fabric, label, stitching, or specific feature
- lifestyle: styled outfit or lifestyle context shot
- duplicate: same angle/content as another image (skip these)
- unusable: too dark, blurry, or garment cut off badly (NOT watermarks/text — those get removed automatically)

Processing options:
- bg_removal_straighten: remove background + rotate to make garment vertical (for tilted flat lays)
- bg_removal_only: remove background only, no rotation needed (flat lay or hanger that is already straight)
- keep_original: keep the full photo as-is, just resize and pad (for model shots, lifestyle)
- skip: don't use this image

CRITICAL PROCESSING RULES:
- model_front / model_back → ALWAYS use "keep_original". Model photos look terrible with background removal.
- lifestyle → ALWAYS use "keep_original".
- hanger → use "bg_removal_only" (BiRefNet handles hangers well enough).
- flat_lay → use "bg_removal_straighten" or "bg_removal_only" depending on tilt.
- detail → use "bg_removal_only" or "keep_original" depending on context.

IMPORTANT: Chinese text, watermarks, or overlays on the image are NOT a reason to skip — background removal will strip them. Only skip for actual quality issues (blurry, too dark, garment cut off).

Selection rules:
- Pick 3-5 best images max for a Shopify listing
- Hero image (first) MUST be a flat-lay if one exists — NEVER use an on-model shot as hero
- Prefer: 1 hero flat lay → 1 back view → 1-2 detail/alternate angles → model shots last
- If ONLY model shots available, that's fine — use them
- If ONLY flat lays available, use the cleanest ones
- Skip duplicates (same garment, same angle, minor differences)
- Images with multiple garments: only use if the product is clearly the focus

Return JSON only:
{
  "images": [
    {"index": 0, "type": "...", "quality": 8, "processing": "...", "reason": "clean flat lay, slight tilt"},
    ...
  ],
  "heroIndex": 0,
  "explanation": "brief reasoning"
}`,
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: `Analyze these ${imagePaths.length} product images (numbered 0-${imagePaths.length - 1}). Select the best ones for a Shopify listing and specify processing for each:`,
          },
          ...imageContent,
        ],
      },
    ],
    max_tokens: 800,
    temperature: 0.1,
  });

  const content = response.choices[0]?.message?.content || "";
  console.log(`[product-images] Vision analysis:\n${content}`);

  try {
    const cleaned = content.replace(/```json?\n?|\n?```/g, "").trim();
    const parsed = JSON.parse(cleaned);

    const selected: ImageAnalysis[] = (parsed.images || [])
      .filter((img: ImageAnalysis) => img.processing !== "skip")
      .map((img: ImageAnalysis) => ({
        index: img.index,
        type: img.type,
        quality: img.quality,
        processing: img.processing,
        reason: img.reason,
      }));

    console.log(`[product-images] Selected ${selected.length}/${imagePaths.length} images`);
    for (const img of selected) {
      console.log(`  [${img.index}] ${img.type} (q:${img.quality}) → ${img.processing}: ${img.reason}`);
    }

    return {
      selected,
      heroIndex: parsed.heroIndex ?? selected[0]?.index ?? 0,
    };
  } catch {
    console.error("[product-images] Failed to parse Vision response, using all images");
    return {
      selected: imagePaths.map((_, i) => ({
        index: i,
        type: "flat_lay" as const,
        quality: 5,
        processing: "bg_removal_straighten" as const,
        reason: "parse failed, default",
      })),
      heroIndex: 0,
    };
  }
}

// ---- Background removal (BiRefNet via fal.ai) ----

async function removeBackground(imageUrl: string): Promise<Buffer> {
  const result = await fal.subscribe("fal-ai/birefnet", {
    input: { image_url: imageUrl },
  });

  const data = result.data as { image?: { url: string } };
  if (!data.image?.url) throw new Error("birefnet returned no image");

  const resp = await fetch(data.image.url);
  if (!resp.ok) throw new Error(`Failed to download birefnet result: ${resp.status}`);
  return Buffer.from(await resp.arrayBuffer());
}

// ---- Rotation detection ----

async function detectRotationAngle(transparentPng: Buffer): Promise<number> {
  if (!process.env.OPENAI_API_KEY) return 0;

  const openai = new OpenAI();
  const preview = await sharp(transparentPng)
    .resize(512, 512, { fit: "inside" })
    .jpeg({ quality: 80 })
    .toBuffer();
  const base64 = preview.toString("base64");

  const request = {
    model: "gpt-4o" as const,
    messages: [
      {
        role: "system" as const,
        content: `You analyze garment flat-lay photos to determine rotation correction.

Focus ONLY on the ZIPPER LINE or CENTER SEAM — it should run perfectly vertical.

Rules:
- Positive angle = rotate counter-clockwise (garment leans right)
- Negative angle = rotate clockwise (garment leans left)
- Most garments need -25° to +25° correction
- If already straight: 0
- Be precise to 1 decimal place
- Only return: {"angle": <number>}`,
      },
      {
        role: "user" as const,
        content: [
          { type: "text" as const, text: "Degrees to rotate counter-clockwise to make the garment's center seam/zipper perfectly vertical:" },
          { type: "image_url" as const, image_url: { url: `data:image/jpeg;base64,${base64}` } },
        ],
      },
    ],
    max_tokens: 50,
    temperature: 0.1,
  };

  const angles: number[] = [];
  for (let i = 0; i < 3; i++) {
    try {
      const response = await openai.chat.completions.create(request);
      const content = response.choices[0]?.message?.content || "";
      const cleaned = content.replace(/```json?\n?|\n?```/g, "").trim();
      const angle = JSON.parse(cleaned).angle;
      if (typeof angle === "number" && !isNaN(angle)) {
        angles.push(angle);
      }
    } catch {
      // skip failed attempt
    }
  }

  if (angles.length === 0) return 0;

  angles.sort((a, b) => a - b);
  const median = angles[Math.floor(angles.length / 2)];
  const spread = angles[angles.length - 1] - angles[0];
  console.log(`[product-images] Rotation angles: [${angles.join(", ")}] → median: ${median}°, spread: ${spread}°`);

  if (spread > 15) {
    console.log(`[product-images] Votes too inconsistent (spread ${spread}°), skipping rotation`);
    return 0;
  }

  return Math.max(-25, Math.min(25, median));
}

// ---- Model photo: keep original ----

async function resizeAndPadOriginal(imageBuffer: Buffer, size = 1024): Promise<Buffer> {
  const resized = await sharp(imageBuffer)
    .resize(size, size, { fit: "inside", withoutEnlargement: false })
    .jpeg({ quality: 95 })
    .toBuffer();

  const { width, height } = await sharp(resized).metadata();
  if (!width || !height) return resized;

  if (Math.abs(width - height) < 10) return resized;

  const left = Math.round((size - width) / 2);
  const top = Math.round((size - height) / 2);

  return sharp({
    create: { width: size, height: size, channels: 3, background: { r: 244, g: 244, b: 244 } },
  })
    .composite([{ input: resized, left, top }])
    .jpeg({ quality: 95 })
    .toBuffer();
}

// ---- Image compositing ----

async function placeOnWhiteBackground(
  transparentPng: Buffer,
  shouldStraighten: boolean,
  size = 1024,
  padding = 0.06,
): Promise<Buffer> {
  let corrected = transparentPng;

  if (shouldStraighten) {
    const angle = await detectRotationAngle(transparentPng);
    if (Math.abs(angle) > 0.5) {
      corrected = await sharp(transparentPng)
        .rotate(angle, { background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .toBuffer();
      console.log(`[product-images] Rotated by ${angle}°`);
    }
  }

  const trimmed = await sharp(corrected).trim().toBuffer();
  const innerSize = Math.round(size * (1 - padding * 2));
  const resized = await sharp(trimmed)
    .resize(innerSize, innerSize, { fit: "inside" })
    .png()
    .toBuffer();

  const { width, height } = await sharp(resized).metadata();
  const left = Math.round((size - (width || innerSize)) / 2);
  const top = Math.round((size - (height || innerSize)) / 2);

  return sharp({
    create: { width: size, height: size, channels: 4, background: BG_COLOR },
  })
    .composite([{ input: resized, left, top }])
    .jpeg({ quality: 95 })
    .toBuffer();
}

// ---- Label detection & replacement (v10 — pixel-level on transparent PNG) ----

interface LabelBox {
  x1: number; y1: number; x2: number; y2: number;
}

interface LabelResult {
  labelCenterX: number; // on nobg image
  labelCenterY: number;
  fabricBrightness: "light" | "dark";
}

/**
 * Detect label on transparent PNG using GPT-4o Vision with pixel coordinates.
 * Returns pixel bounding box on the original image, or null if no label found.
 */
async function detectLabelOnTransparent(
  transparentPng: Buffer,
  W: number,
  H: number,
): Promise<{ box: LabelBox; fabricColor: { r: number; g: number; b: number } } | null> {
  if (!process.env.OPENAI_API_KEY) return null;

  const openai = new OpenAI();

  // Create preview on white background for detection
  const tempOnWhite = await sharp({
    create: { width: W, height: H, channels: 4, background: { r: 244, g: 244, b: 244, alpha: 1 } },
  }).composite([{ input: transparentPng }]).jpeg({ quality: 90 }).toBuffer();

  const preview = await sharp(tempOnWhite).resize(768, 768, { fit: "inside" }).jpeg({ quality: 90 }).toBuffer();

  const detectResp = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: `You detect neck labels on garments. A neck label is a small rectangular tag (typically white) at the center-top of the collar with brand text printed on it.

CRITICAL RULES:
- ONLY detect the actual label TAG — the small rectangular sewn-in tag
- Do NOT include embroidery, flowers, patterns, or any design elements
- The label is usually 3-5% of image width, 2-3% of image height
- It sits at the very top center of the collar opening

Return pixel coordinates (not normalized), relative to the image size you're seeing (768x768):
{"found": true, "x1": 360, "y1": 120, "x2": 400, "y2": 145}

x1,y1 = top-left corner, x2,y2 = bottom-right corner of JUST the label tag.
If no label: {"found": false}`,
      },
      {
        role: "user",
        content: [
          { type: "text", text: "Find the exact pixel bounds of ONLY the neck label tag (not embroidery/flowers):" },
          { type: "image_url", image_url: { url: `data:image/jpeg;base64,${preview.toString("base64")}` } },
        ],
      },
    ],
    max_tokens: 80,
    temperature: 0.1,
  });

  const content = detectResp.choices[0]?.message?.content || "";
  console.log(`[product-images] Label detection: ${content}`);

  try {
    const det = JSON.parse(content.replace(/```json?\n?|\n?```/g, "").trim());
    if (!det.found) {
      console.log("[product-images] No label detected");
      return null;
    }

    // Scale from 768 preview back to original image size + expand
    const scale = W / 768;
    const expand = 8;
    const box: LabelBox = {
      x1: Math.max(0, Math.round(det.x1 * scale) - expand),
      y1: Math.max(0, Math.round(det.y1 * scale) - expand),
      x2: Math.min(W - 1, Math.round(det.x2 * scale) + expand),
      y2: Math.min(H - 1, Math.round(det.y2 * scale) + expand),
    };
    console.log(`[product-images] Label box: (${box.x1},${box.y1}) to (${box.x2},${box.y2}) — ${box.x2 - box.x1}x${box.y2 - box.y1}px`);

    // Sample fabric color from 60-140px below label, alpha-filtered
    const { data: rawData } = await sharp(transparentPng).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const labelCX = Math.round((box.x1 + box.x2) / 2);
    const fabricSamples: number[][] = [];
    for (let dy = 60; dy < 140; dy++) {
      for (let dx = -30; dx <= 30; dx++) {
        const px = labelCX + dx;
        const py = box.y2 + dy;
        if (px < 0 || px >= W || py < 0 || py >= H) continue;
        const idx = (py * W + px) * 4;
        if (rawData[idx + 3] < 128) continue;
        fabricSamples.push([rawData[idx], rawData[idx + 1], rawData[idx + 2]]);
      }
    }

    if (fabricSamples.length === 0) {
      console.warn("[product-images] No fabric samples found below label");
      return null;
    }

    const fabricColor = {
      r: Math.round(fabricSamples.reduce((s, p) => s + p[0], 0) / fabricSamples.length),
      g: Math.round(fabricSamples.reduce((s, p) => s + p[1], 0) / fabricSamples.length),
      b: Math.round(fabricSamples.reduce((s, p) => s + p[2], 0) / fabricSamples.length),
    };
    console.log(`[product-images] Fabric color: rgb(${fabricColor.r},${fabricColor.g},${fabricColor.b})`);

    return { box, fabricColor };
  } catch {
    console.warn("[product-images] Failed to parse label detection");
    return null;
  }
}

/**
 * Paint over label on transparent PNG using alpha-aware pixel painting.
 * Transparent pixels stay transparent, visible pixels get fabric color.
 */
async function removeLabelPixels(
  transparentPng: Buffer,
  W: number,
  H: number,
  box: LabelBox,
  fabricColor: { r: number; g: number; b: number },
): Promise<Buffer> {
  const { data: rawData } = await sharp(transparentPng).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const modifiedData = Buffer.from(rawData);
  const pad = 4;
  let painted = 0;

  for (let y = box.y1 - pad; y <= box.y2 + pad; y++) {
    for (let x = box.x1 - pad; x <= box.x2 + pad; x++) {
      if (x < 0 || x >= W || y < 0 || y >= H) continue;
      const idx = (y * W + x) * 4;
      const a = modifiedData[idx + 3];
      if (a < 30) {
        modifiedData[idx] = 0; modifiedData[idx + 1] = 0;
        modifiedData[idx + 2] = 0; modifiedData[idx + 3] = 0;
      } else {
        modifiedData[idx] = fabricColor.r;
        modifiedData[idx + 1] = fabricColor.g;
        modifiedData[idx + 2] = fabricColor.b;
      }
      painted++;
    }
  }

  console.log(`[product-images] Painted ${painted} label pixels`);
  return sharp(modifiedData, { raw: { width: W, height: H, channels: 4 } }).png().toBuffer();
}

/**
 * Place transparent PNG on white background WITH coordinate tracking,
 * then place NEWG logo at mapped label position.
 */
async function placeWithLabelReplacement(
  cleanedPng: Buffer,
  labelCenterXNobg: number,
  labelCenterYNobg: number,
  fabricBrightness: "light" | "dark",
  shouldStraighten: boolean,
  size = 1024,
  padding = 0.06,
): Promise<Buffer> {
  let corrected = cleanedPng;

  if (shouldStraighten) {
    const angle = await detectRotationAngle(cleanedPng);
    if (Math.abs(angle) > 0.5) {
      corrected = await sharp(cleanedPng)
        .rotate(angle, { background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .toBuffer();
      console.log(`[product-images] Rotated by ${angle}°`);
    }
  }

  const innerSize = Math.round(size * (1 - padding * 2));
  const { info: trimInfo } = await sharp(corrected).trim().toBuffer({ resolveWithObject: true });
  const trimmed = await sharp(corrected).trim().toBuffer();
  const trimOffsetX = trimInfo.trimOffsetLeft ? Math.abs(trimInfo.trimOffsetLeft) : 0;
  const trimOffsetY = trimInfo.trimOffsetTop ? Math.abs(trimInfo.trimOffsetTop) : 0;

  const resized = await sharp(trimmed).resize(innerSize, innerSize, { fit: "inside" }).png().toBuffer();
  const meta = await sharp(resized).metadata();
  const resizedW = meta.width || innerSize;
  const resizedH = meta.height || innerSize;
  const lp = Math.round((size - resizedW) / 2);
  const tp = Math.round((size - resizedH) / 2);

  const flatLay = await sharp({
    create: { width: size, height: size, channels: 4, background: BG_COLOR },
  }).composite([{ input: resized, left: lp, top: tp }]).jpeg({ quality: 95 }).toBuffer();

  // Map label center from nobg coords → final image coords
  const scaleResize = resizedW / trimInfo.width;
  const finalLabelX = lp + (labelCenterXNobg - trimOffsetX) * scaleResize;
  const finalLabelY = tp + (labelCenterYNobg - trimOffsetY) * scaleResize;
  console.log(`[product-images] Label mapped: nobg(${labelCenterXNobg},${labelCenterYNobg}) → final(${Math.round(finalLabelX)},${Math.round(finalLabelY)})`);

  // Place NEWG logo
  const logoFile = fabricBrightness === "dark" ? "logo_white_transparent.png" : "logo_black_transparent.png";
  const logoBuffer = await readFile(join(ASSETS_DIR, logoFile));
  const resizedLogo = await sharp(logoBuffer).resize(110, null, { fit: "inside" }).png().toBuffer();
  const logoMeta = await sharp(resizedLogo).metadata();
  const logoLeft = Math.round(finalLabelX - logoMeta.width! / 2);
  const logoTop = Math.round(finalLabelY - logoMeta.height! / 2);
  console.log(`[product-images] Logo: ${logoFile} ${logoMeta.width}x${logoMeta.height} at (${logoLeft}, ${logoTop})`);

  return sharp(flatLay)
    .composite([{ input: resizedLogo, left: logoLeft, top: logoTop }])
    .jpeg({ quality: 95 }).toBuffer();
}

// ---- fal.ai upload ----

async function uploadToFal(imagePath: string): Promise<string> {
  const buffer = await readFile(imagePath);
  const blob = new Blob([buffer], {
    type: imagePath.endsWith(".png") ? "image/png" : "image/jpeg",
  });
  return fal.storage.upload(blob);
}

// ---- Color grouping ----

interface ColorGroup {
  colorName: string;
  imageIndices: number[];
}

/**
 * Normalize garbled color names from Taobao scraper.
 * Common issue: characters get dropped during translation (e.g. "Bue"→"Blue", "Back"→"Black").
 */
function normalizeColorName(raw: string): string {
  // Known fixes from Taobao scraper garbling
  const fixes: Record<string, string> = {
    "bue": "Blue", "back": "Black", "oive": "Olive", "yeow": "Yellow",
    "ight bue": "Light Blue", "ky gray": "Sky Gray", "wahed": "Washed",
    "ight gray": "Light Gray", "ight green": "Light Green", "ight pink": "Light Pink",
    "avy bue": "Navy Blue", "ark bue": "Dark Blue", "ark gray": "Dark Gray",
    "deep bue": "Deep Blue", "ight": "Light", "ark": "Dark",
    "reen": "Green", "ray": "Gray", "rown": "Brown", "hite": "White",
    "urgundy": "Burgundy", "eige": "Beige", "ream": "Cream",
    "ink": "Pink", "range": "Orange", "ed": "Red",
  };

  let cleaned = raw.trim();

  // Remove size/variant junk (e.g. ", Size 1", ",ize 1", "m", "xl", "Drop Shoulder")
  cleaned = cleaned.replace(/[,\s]*(size\s*\d+|ize\s*\d+|drop\s*shoulder)/gi, "").trim();
  // Remove trailing size letters
  cleaned = cleaned.replace(/\s+(m|s|l|xl|xxl|xxxl)$/i, "").trim();
  // Remove bracketed junk
  cleaned = cleaned.replace(/\s*\[.*?\]\s*/g, "").trim();

  // Try exact match first (case-insensitive)
  const lower = cleaned.toLowerCase();
  if (fixes[lower]) return fixes[lower];

  // Try partial matches for compound names
  for (const [bad, good] of Object.entries(fixes)) {
    if (lower === bad) return good;
  }

  // If it looks garbled (starts lowercase, very short), try to fix
  if (cleaned.length > 0 && cleaned[0] === cleaned[0].toLowerCase()) {
    for (const [bad, good] of Object.entries(fixes)) {
      if (lower.includes(bad)) {
        cleaned = cleaned.replace(new RegExp(bad, "i"), good);
        break;
      }
    }
  }

  // Capitalize first letter
  if (cleaned.length > 0) {
    cleaned = cleaned[0].toUpperCase() + cleaned.slice(1);
  }

  return cleaned || raw;
}

/**
 * Use GPT-4o to group images by color/variant.
 * Returns groups like [{colorName: "Black", imageIndices: [0, 2]}, {colorName: "Brown", imageIndices: [1, 3]}]
 */
async function groupImagesByColor(
  imagePaths: string[],
  productColors: { name: string; imgUrl: string }[],
): Promise<ColorGroup[]> {
  if (!process.env.OPENAI_API_KEY || imagePaths.length <= 1) {
    return [{ colorName: "Default", imageIndices: imagePaths.map((_, i) => i) }];
  }

  // Extract unique color names from product data, normalized
  const colorNames = [...new Set(
    productColors
      .map(c => normalizeColorName(c.name))
      .filter(Boolean),
  )];

  if (colorNames.length <= 1) {
    return [{ colorName: colorNames[0] || "Default", imageIndices: imagePaths.map((_, i) => i) }];
  }

  const openai = new OpenAI();

  const imageContent: Array<{ type: "image_url"; image_url: { url: string } }> = [];
  for (const imgPath of imagePaths) {
    const buffer = await readFile(imgPath);
    const preview = await sharp(buffer)
      .resize(300, 300, { fit: "inside" })
      .jpeg({ quality: 60 })
      .toBuffer();
    imageContent.push({
      type: "image_url",
      image_url: { url: `data:image/jpeg;base64,${preview.toString("base64")}` },
    });
  }

  const response = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: `You group product images by color variant. Given multiple images of the same garment in different colors, assign each image to a color.

Available colors: ${JSON.stringify(colorNames)}

Return JSON only:
{"groups": [{"colorName": "Black", "imageIndices": [0, 2]}, {"colorName": "Brown", "imageIndices": [1, 3]}]}

Rules:
- Every image must be assigned to exactly one color
- If an image shows multiple garments or is ambiguous, assign to the closest color
- Use the exact color names provided`,
      },
      {
        role: "user",
        content: [
          { type: "text", text: `Group these ${imagePaths.length} images by color (${colorNames.join(", ")}):` },
          ...imageContent,
        ],
      },
    ],
    max_tokens: 300,
    temperature: 0.1,
  });

  const content = response.choices[0]?.message?.content || "";
  console.log(`[product-images] Color grouping: ${content}`);

  try {
    const cleaned = content.replace(/```json?\n?|\n?```/g, "").trim();
    const parsed = JSON.parse(cleaned);
    const groups: ColorGroup[] = parsed.groups || [];

    // Validate: every index should appear
    const allIndices = new Set(groups.flatMap(g => g.imageIndices));
    for (let i = 0; i < imagePaths.length; i++) {
      if (!allIndices.has(i)) {
        // Assign unassigned images to first group
        groups[0]?.imageIndices.push(i);
      }
    }

    console.log(`[product-images] Grouped into ${groups.length} colors: ${groups.map(g => `${g.colorName}(${g.imageIndices.length})`).join(", ")}`);
    return groups;
  } catch {
    console.warn("[product-images] Failed to parse color grouping, treating as single color");
    return [{ colorName: "Default", imageIndices: imagePaths.map((_, i) => i) }];
  }
}

// ---- Main export ----

export interface ColorProductImages {
  colorName: string;
  imagePaths: string[];
}

export async function remakeProductImages(
  product: TaobaoProduct,
  originalImagePaths: string[],
): Promise<ColorProductImages[]> {
  fal.config({ credentials: process.env.FAL_KEY });

  const productDir = join(OUTPUT_DIR, product.id, "remade");
  await mkdir(productDir, { recursive: true });

  // Step 1: AI selects best images and processing approach
  console.log(`[product-images] Analyzing ${originalImagePaths.length} images...`);
  const { selected, heroIndex } = await selectBestImages(originalImagePaths);

  if (selected.length === 0) {
    console.log("[product-images] No images selected, using originals");
    return [{ colorName: "Default", imagePaths: product.images }];
  }

  // Sort: flat-lays first (hero), then hangers, then model/lifestyle, by quality
  const typeOrder: Record<string, number> = { flat_lay: 0, hanger: 1, detail: 2, model_front: 3, model_back: 4, lifestyle: 5 };
  const sorted = [...selected].sort((a, b) => {
    const ta = typeOrder[a.type] ?? 9;
    const tb = typeOrder[b.type] ?? 9;
    if (ta !== tb) return ta - tb;
    return b.quality - a.quality;
  });

  // Step 1b: Group images by color
  const selectedPaths = sorted.map(img => originalImagePaths[img.index]);
  const colorGroups = await groupImagesByColor(selectedPaths, product.colors);

  // Step 2: Process each selected image
  const processedByIndex: Map<number, string> = new Map();

  for (const img of sorted) {
    const imgPath = originalImagePaths[img.index];
    const shouldStraighten = img.processing === "bg_removal_straighten";

    console.log(`[product-images] Processing [${img.index}] ${img.type} (${img.processing})...`);

    try {
      if (img.processing === "keep_original") {
        console.log(`[product-images] Keeping original (${img.type}), resizing to 1024x1024...`);
        const imageBuffer = await readFile(imgPath);
        const finalImage = await resizeAndPadOriginal(imageBuffer);
        const finalPath = join(productDir, `final_${img.index}.jpg`);
        await writeFile(finalPath, finalImage);
        console.log(`[product-images] Final: ${finalPath} (${(finalImage.length / 1024).toFixed(0)}KB)`);
        processedByIndex.set(img.index, finalPath);
        continue;
      }

      // Flat-lay, hanger, detail → BiRefNet background removal
      console.log(`[product-images] BiRefNet background removal for ${img.type}...`);
      const falUrl = await uploadToFal(imgPath);
      const transparentPng = await removeBackground(falUrl);
      console.log(`[product-images] Extracted (${(transparentPng.length / 1024).toFixed(0)}KB)`);

      const noBgPath = join(productDir, `nobg_${img.index}.png`);
      await writeFile(noBgPath, transparentPng);

      let finalImage: Buffer;

      // Label detection & replacement on transparent PNG (flat-lays/hangers only)
      if (img.type === "flat_lay" || img.type === "hanger") {
        try {
          const { width: pngW, height: pngH } = await sharp(transparentPng).metadata();
          const W = pngW || 1024;
          const H = pngH || 1024;

          const detection = await detectLabelOnTransparent(transparentPng, W, H);
          if (detection) {
            // Remove label pixels on transparent PNG, then place on white bg
            const cleanedPng = await removeLabelPixels(transparentPng, W, H, detection.box, detection.fabricColor);
            finalImage = await placeOnWhiteBackground(cleanedPng, shouldStraighten);
            console.log(`[product-images] Label removed on image ${img.index}`);
          } else {
            finalImage = await placeOnWhiteBackground(transparentPng, shouldStraighten);
          }
        } catch (err) {
          console.warn(`[product-images] Label replacement failed for image ${img.index}:`, err);
          finalImage = await placeOnWhiteBackground(transparentPng, shouldStraighten);
        }
      } else {
        finalImage = await placeOnWhiteBackground(transparentPng, shouldStraighten);
      }

      const finalPath = join(productDir, `final_${img.index}.jpg`);
      await writeFile(finalPath, finalImage);
      console.log(`[product-images] Final: ${finalPath} (${(finalImage.length / 1024).toFixed(0)}KB)`);

      processedByIndex.set(img.index, finalPath);
    } catch (err) {
      console.warn(`[product-images] Failed to process image ${img.index}:`, err);
      if (product.images[img.index]) {
        processedByIndex.set(img.index, product.images[img.index]);
        console.log(`[product-images] Using original image ${img.index} as fallback`);
      }
    }
  }

  if (processedByIndex.size === 0 && product.images.length > 0) {
    console.log("[product-images] All processing failed, using original images");
    return [{ colorName: "Default", imagePaths: product.images }];
  }

  // Map processed images back to color groups
  // The colorGroups indices refer to the sorted array position, map back to original indices
  const result: ColorProductImages[] = [];
  for (const group of colorGroups) {
    const paths: string[] = [];
    for (const sortedIdx of group.imageIndices) {
      const originalIdx = sorted[sortedIdx]?.index;
      if (originalIdx !== undefined && processedByIndex.has(originalIdx)) {
        paths.push(processedByIndex.get(originalIdx)!);
      }
    }
    if (paths.length > 0) {
      result.push({ colorName: normalizeColorName(group.colorName), imagePaths: paths });
    }
  }

  // If color grouping failed or only 1 group, return all as single
  if (result.length === 0) {
    return [{ colorName: "Default", imagePaths: [...processedByIndex.values()] }];
  }

  console.log(`[product-images] Final: ${result.map(r => `${r.colorName}(${r.imagePaths.length} imgs)`).join(", ")}`);
  return result;
}

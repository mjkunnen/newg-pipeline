import "dotenv/config";
import OpenAI from "openai";
import sharp from "sharp";
import { readFile, writeFile } from "fs/promises";
import { join } from "path";

const ASSETS_DIR = "assets";
const OUTPUT_DIR = "output/products/879455275040/remade";

async function main() {
  const openai = new OpenAI();

  const transparentPng = await readFile("output/products/879455275040/remade/nobg_0.png");
  const { data: rawData, info } = await sharp(transparentPng)
    .ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const W = info.width;
  const H = info.height;

  // Find garment top at center
  let garmentTopY = 0;
  for (let y = 0; y < H; y++) {
    const idx = (y * W + Math.round(W / 2)) * 4;
    if (rawData[idx + 3] > 128) { garmentTopY = y; break; }
  }
  console.log(`Garment top: y=${garmentTopY}`);

  // Use GPT-4o on the transparent-on-white image to get EXACT label bounding box
  const tempOnWhite = await sharp({
    create: { width: W, height: H, channels: 4, background: { r: 244, g: 244, b: 244, alpha: 1 } },
  }).composite([{ input: transparentPng }]).jpeg({ quality: 90 }).toBuffer();

  const preview = await sharp(tempOnWhite).resize(768, 768, { fit: "inside" }).jpeg({ quality: 90 }).toBuffer();

  console.log("Detecting label with GPT-4o (high-res)...");
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
  console.log("Detection:", content);
  const det = JSON.parse(content.replace(/```json?\n?|\n?```/g, "").trim());
  if (!det.found) { console.log("No label"); return; }

  // Scale from 768 preview back to original image size + expand slightly
  const scale = W / 768;
  const expand = 8; // expand detection box by 8px on each side to catch edges
  const lx1 = Math.max(0, Math.round(det.x1 * scale) - expand);
  const ly1 = Math.max(0, Math.round(det.y1 * scale) - expand);
  const lx2 = Math.min(W - 1, Math.round(det.x2 * scale) + expand);
  const ly2 = Math.min(H - 1, Math.round(det.y2 * scale) + expand);
  console.log(`Label on original: (${lx1},${ly1}) to (${lx2},${ly2}) — ${lx2 - lx1}x${ly2 - ly1}px`);

  // Sample fabric color
  const labelCX = Math.round((lx1 + lx2) / 2);
  const fabricSamples: number[][] = [];
  for (let dy = 60; dy < 140; dy++) {
    for (let dx = -30; dx <= 30; dx++) {
      const px = labelCX + dx;
      const py = ly2 + dy;
      if (px < 0 || px >= W || py < 0 || py >= H) continue;
      const idx = (py * W + px) * 4;
      if (rawData[idx + 3] < 128) continue;
      fabricSamples.push([rawData[idx], rawData[idx + 1], rawData[idx + 2]]);
    }
  }

  const fc = {
    r: Math.round(fabricSamples.reduce((s, p) => s + p[0], 0) / fabricSamples.length),
    g: Math.round(fabricSamples.reduce((s, p) => s + p[1], 0) / fabricSamples.length),
    b: Math.round(fabricSamples.reduce((s, p) => s + p[2], 0) / fabricSamples.length),
  };
  console.log(`Fabric: rgb(${fc.r},${fc.g},${fc.b})`);

  // Paint over label
  const pad = 4;
  const modifiedData = Buffer.from(rawData);
  let painted = 0;

  for (let y = ly1 - pad; y <= ly2 + pad; y++) {
    for (let x = lx1 - pad; x <= lx2 + pad; x++) {
      if (x < 0 || x >= W || y < 0 || y >= H) continue;
      const idx = (y * W + x) * 4;
      const a = modifiedData[idx + 3];
      if (a < 30) {
        modifiedData[idx] = 0; modifiedData[idx + 1] = 0;
        modifiedData[idx + 2] = 0; modifiedData[idx + 3] = 0;
      } else {
        modifiedData[idx] = fc.r; modifiedData[idx + 1] = fc.g;
        modifiedData[idx + 2] = fc.b;
      }
      painted++;
    }
  }
  console.log(`Painted ${painted} pixels`);

  const cleanedPng = await sharp(modifiedData, { raw: { width: W, height: H, channels: 4 } })
    .png().toBuffer();

  // Place on white background — track the coordinate transform
  const size = 1024;
  const innerSize = Math.round(size * 0.88);
  const trimmed = await sharp(cleanedPng).trim().toBuffer();
  const trimMeta = await sharp(cleanedPng).metadata();
  // Get trim offset: how many pixels were removed from top/left
  const { info: trimInfo } = await sharp(cleanedPng).trim().toBuffer({ resolveWithObject: true });
  const trimOffsetX = trimInfo.trimOffsetLeft ? Math.abs(trimInfo.trimOffsetLeft) : 0;
  const trimOffsetY = trimInfo.trimOffsetTop ? Math.abs(trimInfo.trimOffsetTop) : 0;
  console.log(`Trim offset: (${trimOffsetX}, ${trimOffsetY}), trimmed size: ${trimInfo.width}x${trimInfo.height}`);

  const resized = await sharp(trimmed).resize(innerSize, innerSize, { fit: "inside" }).png().toBuffer();
  const meta = await sharp(resized).metadata();
  const resizedW = meta.width || innerSize;
  const resizedH = meta.height || innerSize;
  const lp = Math.round((size - resizedW) / 2);
  const tp = Math.round((size - resizedH) / 2);

  const flatLay = await sharp({
    create: { width: size, height: size, channels: 4, background: { r: 244, g: 244, b: 244, alpha: 1 } },
  }).composite([{ input: resized, left: lp, top: tp }]).jpeg({ quality: 95 }).toBuffer();

  await writeFile(join(OUTPUT_DIR, "test_v10_no_label.jpg"), flatLay);

  // Map label center from nobg coords → final image coords
  const labelCenterXNobg = (lx1 + lx2) / 2;
  const labelCenterYNobg = (ly1 + ly2) / 2;

  // Transform: nobg → trimmed → resized → padded
  const scaleResize = resizedW / trimInfo.width;
  const finalLabelX = lp + (labelCenterXNobg - trimOffsetX) * scaleResize;
  const finalLabelY = tp + (labelCenterYNobg - trimOffsetY) * scaleResize;
  console.log(`Label center mapped: nobg(${labelCenterXNobg},${labelCenterYNobg}) → final(${Math.round(finalLabelX)},${Math.round(finalLabelY)})`);

  // Determine fabric brightness from the area
  const fabricBrightness = (fc.r + fc.g + fc.b) / 3 < 128 ? "dark" : "light";

  // Place NEWG logo exactly where the label was
  const logoFile = fabricBrightness === "dark" ? "logo_white_transparent.png" : "logo_black_transparent.png";
  const logoBuffer = await readFile(join(ASSETS_DIR, logoFile));
  const resizedLogo = await sharp(logoBuffer).resize(110, null, { fit: "inside" }).png().toBuffer();
  const logoMeta = await sharp(resizedLogo).metadata();
  const logoLeft = Math.round(finalLabelX - logoMeta.width! / 2);
  const logoTop = Math.round(finalLabelY - logoMeta.height! / 2);
  console.log(`Logo: ${logoMeta.width}x${logoMeta.height} at (${logoLeft}, ${logoTop})`);

  const final = await sharp(flatLay)
    .composite([{ input: resizedLogo, left: logoLeft, top: logoTop }])
    .jpeg({ quality: 95 }).toBuffer();

  await writeFile(join(OUTPUT_DIR, "test_v10_final.jpg"), final);
  console.log("DONE!");
}

main().catch(console.error);

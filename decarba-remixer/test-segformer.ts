import "dotenv/config";
import { readFile, writeFile } from "fs/promises";
import sharp from "sharp";

const SEGFORMER_URL = "https://router.huggingface.co/hf-inference/models/mattmdjaga/segformer_b2_clothes";
const CLOTHING_LABELS = ["Upper-clothes", "Skirt", "Pants", "Dress", "Belt", "Left-shoe", "Right-shoe", "Hat", "Scarf"];

interface Segment {
  label: string;
  mask: string;
  score: number;
}

async function test() {
  const hfToken = process.env.HF_TOKEN;
  if (!hfToken) throw new Error("HF_TOKEN missing");

  const imgPath = "output/products/910942203369/910942203369_0.jpg";
  const imageBuffer = await readFile(imgPath);

  // Resize for API
  const resized = await sharp(imageBuffer)
    .resize(1024, 1024, { fit: "inside", withoutEnlargement: true })
    .jpeg({ quality: 90 })
    .toBuffer();

  console.log(`Sending ${(resized.length / 1024).toFixed(0)}KB to SegFormer...`);

  const resp = await fetch(SEGFORMER_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${hfToken}`,
      "Content-Type": "image/jpeg",
    },
    body: new Blob([new Uint8Array(resized)], { type: "image/jpeg" }),
  });

  if (!resp.ok) {
    console.error(`Failed: ${resp.status} ${await resp.text()}`);
    return;
  }

  const segments: Segment[] = await resp.json();
  console.log(`\nFound ${segments.length} segments:`);
  for (const s of segments) {
    console.log(`  ${s.label} (score: ${s.score.toFixed(3)})`);
  }

  // Filter clothing only
  const clothing = segments.filter((s) => CLOTHING_LABELS.includes(s.label));
  console.log(`\nClothing segments: ${clothing.map((s) => s.label).join(", ")}`);

  // Get image dimensions
  const { width, height } = await sharp(resized).metadata();
  if (!width || !height) throw new Error("No dimensions");

  // Combine clothing masks
  const maskBuffers = await Promise.all(
    clothing.map(async (seg) => {
      const maskPng = Buffer.from(seg.mask, "base64");
      return sharp(maskPng).resize(width, height, { fit: "fill" }).greyscale().raw().toBuffer();
    }),
  );

  const combinedMask = Buffer.alloc(width * height);
  for (const mask of maskBuffers) {
    for (let i = 0; i < combinedMask.length; i++) {
      if (mask[i] > 127) combinedMask[i] = 255;
    }
  }

  // Apply mask to original
  const originalRgba = await sharp(resized).ensureAlpha().raw().toBuffer();
  const masked = Buffer.alloc(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    masked[i * 4] = originalRgba[i * 4];
    masked[i * 4 + 1] = originalRgba[i * 4 + 1];
    masked[i * 4 + 2] = originalRgba[i * 4 + 2];
    masked[i * 4 + 3] = combinedMask[i];
  }

  // Save result
  const result = await sharp(masked, { raw: { width, height, channels: 4 } }).png().toBuffer();
  await writeFile("output/products/910942203369/test_segformer_clothing.png", result);
  console.log(`\nSaved: test_segformer_clothing.png (${(result.length / 1024).toFixed(0)}KB)`);

  // Also save on white background
  const trimmed = await sharp(result).trim().toBuffer();
  const innerSize = Math.round(1024 * 0.88);
  const resizedResult = await sharp(trimmed).resize(innerSize, innerSize, { fit: "inside" }).png().toBuffer();
  const { width: rw, height: rh } = await sharp(resizedResult).metadata();
  const left = Math.round((1024 - (rw || innerSize)) / 2);
  const top = Math.round((1024 - (rh || innerSize)) / 2);

  const final = await sharp({
    create: { width: 1024, height: 1024, channels: 4, background: { r: 244, g: 244, b: 244, alpha: 1 } },
  })
    .composite([{ input: resizedResult, left, top }])
    .jpeg({ quality: 95 })
    .toBuffer();

  await writeFile("output/products/910942203369/test_segformer_final.jpg", final);
  console.log(`Saved: test_segformer_final.jpg (${(final.length / 1024).toFixed(0)}KB)`);
}

test().catch(console.error);

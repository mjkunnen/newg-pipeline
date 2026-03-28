import "dotenv/config";
import { fal } from "@fal-ai/client";
import { readFile } from "fs/promises";
import { join } from "path";
import { remakeProductImages } from "./src/converter/product-images.js";

fal.config({ credentials: process.env.FAL_KEY });

const OUTPUT_DIR = join(import.meta.dirname, "output/products");

async function main() {
  const productId = process.argv[2] || "843725957540";
  const productDir = join(OUTPUT_DIR, productId);

  // Load product data
  const productData = JSON.parse(await readFile(join(productDir, "product.json"), "utf-8"));
  console.log(`\nProcessing: ${productData.title} (${productId})`);

  // Get original image paths
  const { readdir } = await import("fs/promises");
  const files = (await readdir(productDir)).filter((f: string) => f.endsWith(".jpg") && f.startsWith(productId));
  const imagePaths = files.map((f: string) => join(productDir, f));
  console.log(`Found ${imagePaths.length} original images\n`);

  // Process
  const results = await remakeProductImages(productData, imagePaths);
  console.log(`\nDone! ${results.length} processed images:`);
  results.forEach((p) => console.log(`  ${p}`));
}

main().catch(console.error);

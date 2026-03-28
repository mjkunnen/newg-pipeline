import "dotenv/config";
import { fal } from "@fal-ai/client";
import { readFile, readdir } from "fs/promises";
import { join } from "path";

fal.config({ credentials: process.env.FAL_KEY });

const OUTPUT_DIR = join(import.meta.dirname, "output/products");

const PRODUCTS = [
  { id: "837561597310", name: "Rhinestone Jeans" },
  { id: "843725957540", name: "Souffle Knit Sweater" },
  { id: "919111571758", name: "Leopard Print Shorts" },
  { id: "1014227807952", name: "Lion Print Tee" },
  { id: "910942203369", name: "Camo Shorts" },
  { id: "970345104616", name: "Zip Hoodie" },
];

async function main() {
  const urls: { product: string; file: string; url: string }[] = [];

  for (const product of PRODUCTS) {
    const remadeDir = join(OUTPUT_DIR, product.id, "remade");
    let files: string[];
    try {
      files = (await readdir(remadeDir)).filter((f) => f.endsWith(".jpg"));
    } catch {
      console.log(`[skip] No remade folder for ${product.name}`);
      continue;
    }

    console.log(`\n[${product.name}] Uploading ${files.length} images...`);
    for (const file of files) {
      const buffer = await readFile(join(remadeDir, file));
      const blob = new Blob([buffer], { type: "image/jpeg" });
      const url = await fal.storage.upload(blob);
      urls.push({ product: product.name, file, url });
      console.log(`  ${file} → ${url}`);
    }
  }

  // Output as JSON for the upload step
  console.log("\n\n=== UPLOAD_DATA ===");
  console.log(JSON.stringify(urls, null, 2));
}

main().catch(console.error);

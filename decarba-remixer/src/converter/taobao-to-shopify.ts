import "dotenv/config";
import { existsSync } from "fs";
import { join } from "path";
import { scrapeTaobaoProduct, downloadProductImages, saveProductData } from "../scraper/taobao.js";
import { generateDescription } from "./description.js";
import { remakeProductImages, type ColorProductImages } from "./product-images.js";

const OUTPUT_DIR = join(import.meta.dirname, "../../output/products");

const PRODUCT_SHEET_ID =
  process.env.PRODUCT_SHEET_ID || "1-AIOqQSC5CgdtdppRlaLsXNFoP933esW5ZnYSrD6rkM";

// APPS_SCRIPT_URL removed — was posting to Submissions sheet and creating
// ghost rows in the Data tab. Status is now logged locally only.

interface SheetProduct {
  taobao_url: string;
  status: string;
}

function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let current: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') {
        inQuotes = false;
      } else {
        field += c;
      }
    } else {
      if (c === '"') {
        inQuotes = true;
      } else if (c === ",") {
        current.push(field);
        field = "";
      } else if (c === "\n" || (c === "\r" && text[i + 1] === "\n")) {
        if (c === "\r") i++;
        current.push(field);
        field = "";
        if (current.some((f) => f !== "")) rows.push(current);
        current = [];
      } else {
        field += c;
      }
    }
  }
  current.push(field);
  if (current.some((f) => f !== "")) rows.push(current);
  return rows;
}

async function fetchNewProducts(): Promise<SheetProduct[]> {
  const url = `https://docs.google.com/spreadsheets/d/${PRODUCT_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Products`;

  console.log("[products] Fetching products from Sheet...");
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Sheet fetch failed: ${resp.status}`);

  const csv = await resp.text();
  const rows = parseCSV(csv);
  if (rows.length < 2) return [];

  const headers = rows[0].map((h) => h.trim().toLowerCase().replace(/\s+/g, "_"));
  const products: SheetProduct[] = [];

  // Find the URL column — could be "taobao_url", "link", or first column
  const urlCol = headers.findIndex((h) => h === "taobao_url" || h === "link" || h === "url");
  const statusCol = headers.findIndex((h) => h === "status");

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const rawUrl = row[urlCol >= 0 ? urlCol : 0]?.trim() || "";
    const status = statusCol >= 0 ? row[statusCol]?.trim() || "" : "";

    // Skip rows without a taobao URL
    if (!rawUrl.includes("tb.cn") && !rawUrl.includes("taobao.com")) continue;
    // Skip already processed (empty or "new" = not processed yet)
    if (status !== "" && status !== "new") continue;

    // Extract the actual URL from the share text (e.g. "【淘宝】... https://e.tb.cn/xxx ...")
    const urlMatch = rawUrl.match(/(https?:\/\/[^\s]+tb\.cn[^\s]*)/);
    const cleanUrl = urlMatch ? urlMatch[1] : rawUrl;

    products.push({ taobao_url: cleanUrl, status });
  }

  console.log(`[products] Found ${products.length} new product(s)`);
  return products;
}

async function updateProductStatus(
  taobaoUrl: string,
  status: string,
  extra?: Record<string, string>,
): Promise<void> {
  // NOTE: Previously this posted to APPS_SCRIPT_URL (Submissions sheet) which
  // created ghost rows in the Data tab because that script doesn't handle
  // "update_product" actions. Now we just log locally — the Products sheet
  // is read-only for the pipeline (status tracked by presence of output files).
  console.log(`[products] Status: ${status}${extra ? ` (${JSON.stringify(extra)})` : ""}`);
}

function calculateSellingPrice(costEur: number): number {
  const multiplier = costEur < 20 ? 3 : 2.5;
  return Math.ceil(costEur * multiplier);
}

const MAKE_WEBHOOK_URL =
  process.env.MAKE_WEBHOOK_URL || "https://hook.eu1.make.com/zx6ojwbignyxvjqgcgp2pbj8hyluzx22";

async function uploadImages(imagePaths: string[]): Promise<string[]> {
  const { fal } = await import("@fal-ai/client");
  fal.config({ credentials: process.env.FAL_KEY });
  const urls: string[] = [];
  for (const imgPath of imagePaths) {
    if (imgPath.startsWith("http")) {
      urls.push(imgPath);
    } else {
      const { readFile } = await import("fs/promises");
      const buffer = await readFile(imgPath);
      const blob = new Blob([buffer], { type: "image/jpeg" });
      const url = await fal.storage.upload(blob);
      urls.push(url);
      console.log(`[products] Uploaded image: ${imgPath} → ${url}`);
    }
  }
  return urls;
}

async function createShopifyProduct(
  product: Awaited<ReturnType<typeof scrapeTaobaoProduct>>,
  description: Awaited<ReturnType<typeof generateDescription>>,
  imageUrls: string[],
  allColorNames: string[],
  colorSuffix?: string,
): Promise<{ productId: string; productUrl: string }> {
  const sizes = product.sizes.length > 0 ? product.sizes : ["S", "M", "L", "XL", "2XL"];
  const sellingPrice = calculateSellingPrice(product.priceEUR);
  const priceStr = sellingPrice.toFixed(2);

  const title = colorSuffix
    ? `${description.title} - ${colorSuffix}`
    : description.title;
  const escapedTitle = title.replace(/"/g, '\\"');
  const escapedHtml = description.descriptionHtml.replace(/"/g, '\\"').replace(/\n/g, "\\n");
  const tagsStr = description.tags.map((t) => `"${t.replace(/"/g, '\\"')}"`).join(", ");

  // Build Color + Size variant matrix
  let productOptions: string;
  let variantsStr: string;

  if (allColorNames.length > 1) {
    productOptions = `{ name: "Color", values: [${allColorNames.map((c) => `{ name: "${c.replace(/"/g, '\\"')}" }`).join(", ")}] }, { name: "Size", values: [${sizes.map((s) => `{ name: "${s}" }`).join(", ")}] }`;
    const variants: string[] = [];
    for (const color of allColorNames) {
      for (const size of sizes) {
        variants.push(`{ optionValues: [{ optionName: "Color", name: "${color.replace(/"/g, '\\"')}" }, { optionName: "Size", name: "${size}" }], price: ${priceStr} }`);
      }
    }
    variantsStr = variants.join(", ");
  } else {
    productOptions = `{ name: "Size", values: [${sizes.map((s) => `{ name: "${s}" }`).join(", ")}] }`;
    variantsStr = sizes
      .map((s) => `{ optionValues: [{ optionName: "Size", name: "${s}" }], price: ${priceStr} }`)
      .join(", ");
  }

  const productQuery = `mutation {
    productSet(input: {
      title: "${escapedTitle}",
      descriptionHtml: "${escapedHtml}",
      productOptions: [${productOptions}],
      variants: [${variantsStr}],
      tags: [${tagsStr}],
      vendor: "NEWGARMENTS",
      productType: "Clothing",
      status: ACTIVE
    }) {
      product { id title }
      userErrors { field message }
    }
  }`;

  const mediaInputStr = imageUrls
    .map((url) => `{ originalSource: "${url}", mediaContentType: IMAGE }`)
    .join(", ");

  const mediaQuery = `mutation {
    productCreateMedia(productId: "PRODUCT_ID", media: [${mediaInputStr}]) {
      media { id status }
      mediaUserErrors { field message }
    }
  }`;

  const payload = { productQuery, mediaQuery };

  console.log(`[products] Creating Shopify product via Make.com: ${escapedTitle} (€${sellingPrice})`);

  const resp = await fetch(MAKE_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Make webhook failed: ${resp.status} ${err}`);
  }

  const responseText = await resp.text();
  console.log(`[products] Make webhook response: ${responseText}`);

  return { productId: "make-webhook", productUrl: "" };
}

async function main() {
  console.log("[products] Starting Taobao → Shopify pipeline...\n");

  const products = await fetchNewProducts();

  if (products.length === 0) {
    console.log("[products] No new products. Done.");
    return;
  }

  for (const sheetProduct of products) {
    const url = sheetProduct.taobao_url;
    console.log(`\n[products] Processing: ${url}`);

    try {
      // Step 1: Scrape Taobao
      await updateProductStatus(url, "scraping");
      const product = await scrapeTaobaoProduct(url);

      // Skip if already processed (remade folder exists with final images)
      const remadeDir = join(OUTPUT_DIR, product.id, "remade");
      if (existsSync(remadeDir)) {
        console.log(`[products] Already processed: ${product.id}, skipping`);
        continue;
      }
      await saveProductData(product);
      const sellingPrice = calculateSellingPrice(product.priceEUR);
      console.log(`[products] Scraped: ${product.title}`);
      console.log(`[products] Cost: €${product.priceEUR} → Selling: €${sellingPrice} (${product.priceEUR < 20 ? "x3" : "x2.5"})`);

      // Step 2: Download original images
      const imagePaths = await downloadProductImages(product);
      if (imagePaths.length === 0) {
        throw new Error("No images downloaded");
      }

      // Step 3: Remake images (returns per-color groups)
      await updateProductStatus(url, "remaking");
      const colorGroups = await remakeProductImages(product, imagePaths);
      const totalImages = colorGroups.reduce((s, g) => s + g.imagePaths.length, 0);
      console.log(`[products] Remade ${totalImages} image(s) in ${colorGroups.length} color group(s)`);

      // Step 4: Generate description
      const description = await generateDescription(product, imagePaths);

      // Step 5: Create Shopify listing(s) — one per color group
      const allColorNames = colorGroups.length > 1
        ? colorGroups.map(g => g.colorName)
        : [];

      for (const group of colorGroups) {
        const imageUrls = await uploadImages(group.imagePaths);
        await createShopifyProduct(
          product,
          description,
          imageUrls,
          allColorNames,
          colorGroups.length > 1 ? group.colorName : undefined,
        );
      }

      // Step 6: Update sheet with all info
      await updateProductStatus(url, "listed", {
        title: description.title,
        cost_eur: product.priceEUR.toFixed(2),
        selling_price: sellingPrice.toString(),
        shopify_id: "make-webhook",
        shopify_url: "",
        images: totalImages.toString(),
      });

      console.log(`[products] Done: ${description.title} → €${sellingPrice} (${colorGroups.length} product(s))`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[products] ✗ Failed: ${msg}`);
      await updateProductStatus(url, "failed", { error: msg.slice(0, 200) });
    }
  }

  console.log("\n[products] Pipeline complete.");
}

main().catch(console.error);

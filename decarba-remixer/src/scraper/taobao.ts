import "dotenv/config";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";

function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    throw new Error(
      `Required env var ${key} is not set. ` +
      "Add it to .env (local) or GitHub Actions secrets (CI)."
    );
  }
  return val;
}

const APIFY_TOKEN = requireEnv("APIFY_TOKEN");
const APIFY_ACTOR = "pizani~taobao-product-scraper";
const OUTPUT_DIR = join(import.meta.dirname, "../../output/products");

export interface TaobaoProduct {
  id: string;
  url: string;
  title: string;
  titleOriginal?: string;
  priceCNY: number;
  priceEUR: number;
  images: string[];
  colors: { name: string; imgUrl: string; price: string }[];
  sizes: string[];
  shopName: string | null;
  shopId: string;
  scrapedAt: string;
}

/**
 * Resolve a short Taobao URL (e.tb.cn/...) to a full item.taobao.com URL.
 * Returns the product ID.
 */
export async function resolveShortUrl(shortUrl: string): Promise<string> {
  // If already a full URL, extract ID directly
  const directMatch = shortUrl.match(/[?&]id=(\d+)/);
  if (directMatch) return directMatch[1];

  // Follow redirects to get the real URL
  const resp = await fetch(shortUrl, { redirect: "follow" });
  const html = await resp.text();

  // Look for product ID in the final URL or page content
  const urlMatch = resp.url.match(/[?&]id=(\d+)/);
  if (urlMatch) return urlMatch[1];

  // Try to find it in the HTML (meta refresh, JS redirect, etc.)
  const htmlMatch = html.match(/item\.taobao\.com\/item\.htm[^"']*[?&]id=(\d+)/);
  if (htmlMatch) return htmlMatch[1];

  const idMatch = html.match(/"itemId"\s*:\s*"?(\d+)"?/);
  if (idMatch) return idMatch[1];

  throw new Error(`Could not resolve Taobao URL: ${shortUrl}`);
}

/**
 * Scrape a Taobao product using Apify actor.
 */
export async function scrapeTaobaoProduct(productUrl: string): Promise<TaobaoProduct> {
  // Resolve short URLs first
  let productId: string;
  let fullUrl: string;

  if (productUrl.includes("e.tb.cn") || !productUrl.includes("item.taobao.com")) {
    console.log(`[taobao] Resolving short URL: ${productUrl}`);
    productId = await resolveShortUrl(productUrl);
    fullUrl = `https://item.taobao.com/item.htm?id=${productId}`;
    console.log(`[taobao] Resolved to ID: ${productId}`);
  } else {
    const match = productUrl.match(/[?&]id=(\d+)/);
    if (!match) throw new Error(`Cannot extract product ID from: ${productUrl}`);
    productId = match[1];
    fullUrl = productUrl;
  }

  // Start Apify actor run
  console.log(`[taobao] Scraping product ${productId}...`);
  const startResp = await fetch(
    `https://api.apify.com/v2/acts/${APIFY_ACTOR}/runs?token=${APIFY_TOKEN}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_url: fullUrl }),
    },
  );

  if (!startResp.ok) {
    throw new Error(`Apify start failed: ${startResp.status} ${await startResp.text()}`);
  }

  const runData = await startResp.json();
  const runId = runData.data.id;
  const datasetId = runData.data.defaultDatasetId;
  console.log(`[taobao] Run started: ${runId}`);

  // Poll for completion (max 2 minutes)
  for (let i = 0; i < 24; i++) {
    await new Promise((r) => setTimeout(r, 5000));

    const statusResp = await fetch(
      `https://api.apify.com/v2/actor-runs/${runId}?token=${APIFY_TOKEN}`,
    );
    const statusData = await statusResp.json();
    const status = statusData.data.status;

    if (status === "SUCCEEDED") {
      console.log(`[taobao] Scrape succeeded`);
      break;
    } else if (status === "FAILED" || status === "ABORTED" || status === "TIMED-OUT") {
      throw new Error(`Apify run ${status} for product ${productId}`);
    }
    // RUNNING or READY — keep waiting
  }

  // Fetch results
  const itemsResp = await fetch(
    `https://api.apify.com/v2/datasets/${datasetId}/items?token=${APIFY_TOKEN}`,
  );
  const items = await itemsResp.json();

  if (!items.length || !items[0].productInfo) {
    throw new Error(`No product data returned for ${productId}`);
  }

  const raw = items[0];
  const info = raw.productInfo;
  const seller = raw.sellerInfo || {};

  // Parse price (Apify returns USD string)
  const priceUSD = parseFloat(info.price) || 0;
  const priceCNY = priceUSD * 7.2; // approximate USD to CNY
  const priceEUR = priceUSD * 0.92; // approximate USD to EUR

  // Extract unique colors/options
  const colors = (info.options || []).map((opt: Record<string, string>) => ({
    name: opt.name || "Default",
    imgUrl: opt.imgUrl || "",
    price: opt.price || info.price,
  }));

  // Deduplicate colors by name
  const uniqueColors = colors.filter(
    (c: { name: string }, i: number, arr: { name: string }[]) =>
      arr.findIndex((x: { name: string }) => x.name === c.name) === i,
  );

  // Extract sizes from attributes if available
  const sizes: string[] = [];
  if (info.atributtes) {
    for (const [key, val] of Object.entries(info.atributtes)) {
      if (key.toLowerCase().includes("size") || key.toLowerCase().includes("尺码")) {
        if (Array.isArray(val)) sizes.push(...val);
        else if (typeof val === "string") sizes.push(val);
      }
    }
  }

  const product: TaobaoProduct = {
    id: productId,
    url: fullUrl,
    title: info.title || "",
    priceCNY,
    priceEUR: Math.round(priceEUR * 100) / 100,
    images: info.imgList || [],
    colors: uniqueColors,
    sizes: sizes.length > 0 ? sizes : ["S", "M", "L", "XL", "2XL"],
    shopName: seller.shopTitle || null,
    shopId: seller.shopID || "",
    scrapedAt: new Date().toISOString(),
  };

  return product;
}

/**
 * Download product images locally.
 */
export async function downloadProductImages(
  product: TaobaoProduct,
): Promise<string[]> {
  const dir = join(OUTPUT_DIR, product.id);
  await mkdir(dir, { recursive: true });

  const localPaths: string[] = [];

  for (let i = 0; i < product.images.length; i++) {
    const imgUrl = product.images[i];
    const ext = imgUrl.includes(".png") ? ".png" : ".jpg";
    const filename = `${product.id}_${i}${ext}`;
    const filePath = join(dir, filename);

    try {
      const resp = await fetch(imgUrl);
      if (!resp.ok) {
        console.warn(`[taobao] Failed to download image ${i}: ${resp.status}`);
        continue;
      }
      const buffer = Buffer.from(await resp.arrayBuffer());
      await writeFile(filePath, buffer);
      localPaths.push(filePath);
      console.log(`[taobao] Downloaded image ${i}: ${filename} (${(buffer.length / 1024).toFixed(0)}KB)`);
    } catch (err) {
      console.warn(`[taobao] Error downloading image ${i}:`, err);
    }
  }

  // Also download color variant images
  for (const color of product.colors) {
    if (color.imgUrl && !product.images.includes(color.imgUrl)) {
      const filename = `${product.id}_color_${color.name.replace(/\s+/g, "_")}.jpg`;
      const filePath = join(dir, filename);
      try {
        const resp = await fetch(color.imgUrl);
        if (resp.ok) {
          const buffer = Buffer.from(await resp.arrayBuffer());
          await writeFile(filePath, buffer);
          localPaths.push(filePath);
        }
      } catch { /* skip */ }
    }
  }

  return localPaths;
}

/**
 * Save product data as JSON.
 */
export async function saveProductData(product: TaobaoProduct): Promise<string> {
  const dir = join(OUTPUT_DIR, product.id);
  await mkdir(dir, { recursive: true });
  const path = join(dir, "product.json");
  await writeFile(path, JSON.stringify(product, null, 2));
  console.log(`[taobao] Saved product data: ${path}`);
  return path;
}

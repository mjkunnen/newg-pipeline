import { readFile } from "fs/promises";
import { join } from "path";
import YAML from "yaml";
import type { AdAnalysis, Product } from "../scraper/types.js";

let productsCache: Product[] | null = null;

async function loadProducts(): Promise<Product[]> {
  if (productsCache) return productsCache;

  const configPath = join(import.meta.dirname, "../../config/products.yaml");
  const raw = await readFile(configPath, "utf-8");
  productsCache = YAML.parse(raw) as Product[];
  return productsCache;
}

export async function matchProducts(
  analysis: AdAnalysis,
  collection?: string
): Promise<Product[]> {
  const allProducts = await loadProducts();

  // Filter by collection if specified
  let candidates = collection
    ? allProducts.filter(
        (p) => p.collection.toLowerCase() === collection.toLowerCase()
      )
    : allProducts;

  if (candidates.length === 0) candidates = allProducts;

  // Score by keyword matches against analysis
  const searchText =
    `${analysis.product_type} ${analysis.vibe} ${analysis.model_description} ${analysis.colors.join(" ")}`.toLowerCase();

  const scored = candidates.map((product) => {
    let score = 0;
    for (const keyword of product.keywords) {
      if (searchText.includes(keyword.toLowerCase())) score++;
    }
    return { product, score };
  });

  // Sort by score desc, return top matches
  scored.sort((a, b) => b.score - a.score);
  const matches = scored.filter((s) => s.score > 0).map((s) => s.product);

  // If no keyword matches, return first 2 from collection by vibe
  if (matches.length === 0) {
    const vibe = analysis.vibe.toLowerCase();
    if (vibe.includes("cozy") || vibe.includes("comfort") || vibe.includes("relax")) {
      return candidates.filter((p) => p.collection === "comfy-vibe").slice(0, 2);
    } else if (vibe.includes("clean") || vibe.includes("minimal")) {
      return candidates.filter((p) => p.collection === "minimalistic").slice(0, 2);
    } else if (vibe.includes("bold") || vibe.includes("graphic") || vibe.includes("statement")) {
      return candidates.filter((p) => p.collection === "graphic-items").slice(0, 2);
    }
    return candidates.slice(0, 2);
  }

  console.log(`[matcher] Matched ${matches.length} products: ${matches.map((m) => m.name).join(", ")}`);
  return matches.slice(0, 3);
}

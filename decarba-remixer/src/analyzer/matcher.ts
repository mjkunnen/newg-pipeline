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

  // Score by keyword matches against analysis, with sales_rank bonus
  const searchText =
    `${analysis.product_type} ${analysis.vibe} ${analysis.model_description} ${analysis.colors.join(" ")}`.toLowerCase();

  const scored = candidates.map((product) => {
    let score = 0;
    for (const keyword of product.keywords) {
      if (searchText.includes(keyword.toLowerCase())) score++;
    }
    // Boost bestsellers: lower sales_rank = higher bonus
    if (product.sales_rank && score > 0) {
      score += Math.max(0, (15 - product.sales_rank) * 0.5);
    }
    return { product, score };
  });

  // Sort by score desc, return top matches
  scored.sort((a, b) => b.score - a.score);
  const matches = scored.filter((s) => s.score > 0).map((s) => s.product);

  // If no keyword matches, return top sellers from relevant category by vibe
  if (matches.length === 0) {
    const vibe = analysis.vibe.toLowerCase();
    const productType = analysis.product_type.toLowerCase();
    if (productType.includes("jean") || productType.includes("pant") || productType.includes("trouser")) {
      return candidates.filter((p) => p.collection === "bestseller-bottoms").slice(0, 2);
    } else if (productType.includes("sneaker") || productType.includes("shoe")) {
      return candidates.filter((p) => p.collection === "bestseller-shoes").slice(0, 2);
    } else if (vibe.includes("cozy") || vibe.includes("comfort") || productType.includes("hoodie") || productType.includes("knit") || productType.includes("sweater")) {
      return candidates.filter((p) => p.collection === "bestseller-tops").slice(0, 2);
    }
    // Default: return highest-selling products
    return [...candidates].sort((a, b) => (a.sales_rank || 99) - (b.sales_rank || 99)).slice(0, 2);
  }

  console.log(`[matcher] Matched ${matches.length} products: ${matches.map((m) => m.name).join(", ")}`);
  return matches.slice(0, 3);
}

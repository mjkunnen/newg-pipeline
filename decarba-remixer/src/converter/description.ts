import "dotenv/config";
import OpenAI from "openai";
import { readFile } from "fs/promises";
import type { TaobaoProduct } from "../scraper/taobao.js";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export interface ProductDescription {
  title: string;
  descriptionHtml: string;
  tags: string[];
  seoTitle: string;
  seoDescription: string;
}

/**
 * Generate an English product description for Shopify using GPT-4o Vision.
 * Sends product images + title for context.
 */
export async function generateDescription(
  product: TaobaoProduct,
  imagePaths: string[],
): Promise<ProductDescription> {
  console.log(`[description] Generating description for: ${product.title}`);

  // Build image content from local files (max 3 images)
  const imageContent: OpenAI.ChatCompletionContentPart[] = [];
  for (const imgPath of imagePaths.slice(0, 3)) {
    try {
      const buffer = await readFile(imgPath);
      const base64 = buffer.toString("base64");
      const mimeType = imgPath.endsWith(".png") ? "image/png" : "image/jpeg";
      imageContent.push({
        type: "image_url",
        image_url: { url: `data:${mimeType};base64,${base64}`, detail: "low" },
      });
    } catch {
      // skip unreadable images
    }
  }

  const response = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: `You are a copywriter for NEWGARMENTS, a European streetwear brand targeting 18-30 year olds.
Write product descriptions in English. Tone: confident, minimal, streetwear-native. No cringe, no hype-beast language.
Keep it clean and authentic. Use simple words. Max 3 sentences for description.`,
      },
      {
        role: "user",
        content: [
          {
            type: "text",
            text: `Write a Shopify product listing for this item.

Original title (Chinese): ${product.title}
Price: €${product.priceEUR}
Colors available: ${product.colors.map((c) => c.name).join(", ") || "Black"}

Return a JSON object with these exact fields:
- title: English product title (short, no brand name, max 8 words)
- descriptionHtml: HTML description (2-3 short paragraphs, use <p> tags, mention fit and style)
- tags: array of relevant tags (streetwear, y2k, oversized, etc.)
- seoTitle: SEO-friendly title with "NEWGARMENTS" brand
- seoDescription: 1 sentence meta description (max 155 chars)

Return ONLY the JSON object, no markdown fences.`,
          },
          ...imageContent,
        ],
      },
    ],
    max_tokens: 800,
    temperature: 0.7,
  });

  const text = response.choices[0].message.content?.trim() || "";

  try {
    // Strip markdown fences if present
    const cleaned = text.replace(/^```json?\s*/i, "").replace(/\s*```$/, "");
    const parsed = JSON.parse(cleaned) as ProductDescription;
    console.log(`[description] Generated: "${parsed.title}"`);
    return parsed;
  } catch {
    console.error(`[description] Failed to parse GPT response:`, text);
    // Fallback
    return {
      title: product.title.slice(0, 60),
      descriptionHtml: `<p>Premium streetwear piece. Oversized fit, quality materials.</p>`,
      tags: ["streetwear", "oversized"],
      seoTitle: `${product.title.slice(0, 40)} | NEWGARMENTS`,
      seoDescription: "Premium streetwear from NEWGARMENTS. Free shipping across Europe.",
    };
  }
}

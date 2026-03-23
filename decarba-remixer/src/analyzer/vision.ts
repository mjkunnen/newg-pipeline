import OpenAI from "openai";
import { readFile } from "fs/promises";
import type { AdAnalysis } from "../scraper/types.js";

const client = new OpenAI();

export async function analyzeAd(imagePath: string): Promise<AdAnalysis> {
  const imageData = await readFile(imagePath);
  const base64 = imageData.toString("base64");
  const mediaType = imagePath.endsWith(".png") ? "image/png" : "image/jpeg";

  console.log(`[vision] Analyzing ${imagePath}...`);

  const response = await client.chat.completions.create({
    model: "gpt-4o",
    max_tokens: 2000,
    messages: [
      {
        role: "user",
        content: [
          {
            type: "image_url",
            image_url: {
              url: `data:${mediaType};base64,${base64}`,
            },
          },
          {
            type: "text",
            text: `Analyze this fashion/streetwear ad image. Return JSON only, no other text:
{
  "layout": "description of composition and layout",
  "text_overlays": ["list of text visible in the ad"],
  "colors": ["dominant colors"],
  "model_description": "what the model is wearing, pose, setting",
  "product_type": "type of clothing shown",
  "vibe": "overall aesthetic/mood",
  "remake_prompt": "A detailed fal.ai image generation prompt to recreate this ad style with different streetwear items. Include: composition, lighting, model pose, setting, camera angle, mood. Do NOT include specific brand names."
}`,
          },
        ],
      },
    ],
  });

  const text = response.choices[0]?.message?.content || "";

  // Parse JSON — handle potential markdown wrapping
  const jsonStr = text.replace(/```json?\n?/g, "").replace(/```/g, "").trim();
  const analysis: AdAnalysis = JSON.parse(jsonStr);

  console.log(`[vision] Vibe: ${analysis.vibe}`);
  console.log(`[vision] Product: ${analysis.product_type}`);
  console.log(`[vision] Text overlays: ${analysis.text_overlays.length}`);

  return analysis;
}

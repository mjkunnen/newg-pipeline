---
name: check-board
description: Check Pinterest board for new pins and automatically remake them with NEWGARMENTS outfits
disable-model-invocation: true
---

# Check Pinterest Board & Auto-Remake

Run the full NEWGARMENTS remake pipeline:

## Step 1: Read the remake workflow from memory
Read `~/.claude/projects/C--Users-maxku-OneDrive-Bureaublad-competitor-creative-research--NEWG-/memory/feedback_remake_workflow.md` FIRST. Follow it exactly.

## Step 2: Fetch pins from Pinterest board
- Board ID: `1003176954437607618`
- Use Zapier Pinterest MCP or the Pinterest API to get all pins
- Download each pin image

## Step 3: Check what's already been remade
- Look in Google Drive folder `remakes-new` (ID: `1crvIaZtrMmuXslneAkX_q4rgcb1J5-FU`) inside `2026-03-22/` (ID: `1aDYVm5Q-ss1ULR-o7ICOp6tjNsfLB_4B`)
- Also check local `board_remakes_proper/` folder
- Only process NEW pins that haven't been remade yet

## Step 4: Remake new pins using the CORRECT workflow
For each new pin:
1. **Source image** = the Pinterest pin (Image 1)
2. **Product refs** = top + bottom + shoes from `content-library/product-refs/` (Images 2, 3, 4)
3. **Endpoint** = `https://queue.fal.run/fal-ai/nano-banana-2/edit` (EDIT endpoint, NOT generate)
4. **Payload** = `{"prompt": "...", "image_urls": [source, top, bottom, shoes]}`
5. **Prompt MUST include**: "wearing a plain white t-shirt underneath the zip hoodie, visible at the chest/neckline"
6. **Prompt MUST say**: keep same person, face, skin tone, pose, background, lighting — ONLY change clothing

### Outfit combos (cycle through these):
1. checkered-zipper-gray + embroidered-striped-jeans + fur-graphic-sneakers
2. zip-hoodie-y2k-dark-green + graphic-lining-jeans + ocean-stars-sneaker
3. checkered-zipper-black + embroidered-striped-jeans + ocean-stars-sneaker
4. zip-hoodie-y2k-pink + graphic-lining-jeans + fur-graphic-sneakers
5. zip-hoodie-y2k-black + embroidered-striped-jeans + fur-graphic-sneakers
6. checkered-zipper-red + graphic-lining-jeans + ocean-stars-sneaker

### Catalog location:
- `config/clothing-catalog.json` — product data
- `content-library/product-refs/` — product reference images

## Step 5: Upload to Google Drive
- Upload remakes to the `remakes-new` subfolder inside today's date folder
- Create the date folder if it doesn't exist yet
- Use 0x0.st as bridge for uploading local files to Drive

## Step 6: Report results
Tell the user:
- How many new pins were found
- How many remakes were generated
- Show 2-3 sample images for review

## CRITICAL RULES (DO NOT BREAK):
- NEVER use the regular generate endpoint — ALWAYS use `/edit`
- NEVER swap only the hoodie — ALWAYS include full outfit (top + bottom + shoes)
- NEVER forget the white t-shirt underneath
- NEVER use `fal_client.subscribe()` — use direct HTTP requests
- Use FAL_KEY from `.env` file

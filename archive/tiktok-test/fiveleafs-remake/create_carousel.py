"""
Create a 3-slide TikTok carousel remake inspired by Five Leafs format:
  Slide 1: 2x2 grid of outfit photos + "You want this style?"
  Slide 2: 2x2 grid of outfit photos + "But it's too expensive?"
  Slide 3: NEWGARMENTS product collage with items, prices, and copywriting
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys

BASE = Path(__file__).parent
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

# TikTok carousel dimensions (9:16)
W, H = 1080, 1920

# ---------- FONTS ----------
# Try common Windows fonts
FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",   # Arial Bold
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]

def load_font(size, bold=True):
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()

font_big = load_font(72)
font_medium = load_font(42)
font_small = load_font(32)
font_price = load_font(36)
font_price_old = load_font(28, bold=False)
font_brand = load_font(56)
font_copy = load_font(52)


def fit_image(img, target_w, target_h):
    """Crop-fit an image to target dimensions (center crop)."""
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Image is wider — crop sides
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        # Image is taller — crop top/bottom
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


def draw_text_with_outline(draw, pos, text, font, fill="white", outline_color="black", outline_width=3):
    """Draw text with outline for visibility."""
    x, y = pos
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((x+dx, y+dy), text, font=font, fill=outline_color)
    draw.text(pos, text, font=font, fill=fill)


def create_grid_slide(pin_images, text_line, output_path):
    """Create a 2x2 grid slide with text overlay."""
    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    gap = 6
    cell_w = (W - gap) // 2
    cell_h = (H - gap) // 2

    positions = [
        (0, 0),
        (cell_w + gap, 0),
        (0, cell_h + gap),
        (cell_w + gap, cell_h + gap),
    ]

    for i, (px, py) in enumerate(positions):
        if i < len(pin_images):
            img = Image.open(pin_images[i]).convert("RGB")
            img = fit_image(img, cell_w, cell_h)
            canvas.paste(img, (px, py))

    # Add text overlay in the center
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), text_line, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2
    ty = (H - th) // 2

    draw_text_with_outline(draw, (tx, ty), text_line, font_big, fill="white", outline_width=4)

    canvas.save(output_path, quality=95)
    print(f"Saved: {output_path}")


def create_product_collage(product_data, output_path):
    """Create NEWGARMENTS product collage — matching the user's own TikTok last slide style.

    Layout: white bg, bold header text at top, layered/scattered product images
    (hoodies clustered top, jeans + accessories bottom), "NEWGRMTNS GOT YOU!" overlay,
    bottom warning text.
    """
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # --- Header: "ARCHIVE SALE" + subtitle ---
    font_header = load_font(72)
    font_sub = load_font(36)

    header = "ARCHIVE SALE"
    bbox_h = draw.textbbox((0, 0), header, font=font_header)
    hw = bbox_h[2] - bbox_h[0]
    draw.text(((W - hw) // 2, 30), header, font=font_header, fill=(0, 0, 0))

    sub_lines = [
        "UP TO 88% OFF + FREE WORLDWIDE",
        "SHIPPING + FREE GIFTS"
    ]
    sy = 115
    for line in sub_lines:
        bbox_s = draw.textbbox((0, 0), line, font=font_sub)
        sw = bbox_s[2] - bbox_s[0]
        draw.text(((W - sw) // 2, sy), line, font=font_sub, fill=(0, 0, 0))
        sy += 44

    # --- Top section: hoodies/tops layered/overlapping (y ~ 260-750) ---
    # Group products: tops first, then bottoms, then shoes/accessories
    tops = [p for p in product_data if any(k in p["name"].lower() for k in ["hoodie", "zipper", "jacket"])]
    bottoms = [p for p in product_data if any(k in p["name"].lower() for k in ["jeans", "pants"])]
    shoes = [p for p in product_data if any(k in p["name"].lower() for k in ["sneaker", "shoe", "clog"])]

    def paste_product(img_path, x, y, size, rotation=0):
        """Paste a product image at position with optional rotation."""
        try:
            pimg = Image.open(img_path).convert("RGBA")
            pimg.thumbnail((size, size), Image.LANCZOS)
            if rotation:
                pimg = pimg.rotate(rotation, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
            paste_x = x - pimg.width // 2
            paste_y = y - pimg.height // 2
            canvas.paste(pimg, (paste_x, paste_y), pimg)
        except Exception as e:
            print(f"Warning: Could not load {img_path}: {e}")

    # Place tops — large, dense, overlapping, filling the upper section
    # Back layer first (will be partially covered by front layer)
    top_back = [
        (130, 520, 520, -12),   # far left back
        (950, 540, 480, 10),    # far right back
    ]
    top_front = [
        (320, 500, 560, 5),     # center-left (big, front)
        (580, 480, 580, -3),    # center (biggest)
        (800, 510, 540, -6),    # center-right
    ]

    # Paste back layer first
    for i, top in enumerate(tops):
        if i < len(top_back):
            px, py, sz, rot = top_back[i]
            paste_product(top["image"], px, py, sz, rot)

    # Paste front layer on top (overlapping)
    for i in range(len(top_back), len(tops)):
        idx = i - len(top_back)
        if idx < len(top_front):
            px, py, sz, rot = top_front[idx]
            paste_product(tops[i]["image"], px, py, sz, rot)

    # Any remaining tops
    extra_top_pos = [(540, 540, 460, -5)]
    for i in range(len(top_back) + len(top_front), len(tops)):
        idx = i - len(top_back) - len(top_front)
        if idx < len(extra_top_pos):
            px, py, sz, rot = extra_top_pos[idx]
            paste_product(tops[i]["image"], px, py, sz, rot)

    # --- Middle: "NEWGRMTNS GOT YOU!" overlay text ---
    font_cta = load_font(68)
    cta_text = "NEWGRMTNS GOT YOU!"
    bbox_cta = draw.textbbox((0, 0), cta_text, font=font_cta)
    cta_w = bbox_cta[2] - bbox_cta[0]
    cta_y = 800
    draw_text_with_outline(draw, ((W - cta_w) // 2, cta_y), cta_text, font_cta,
                           fill=(255, 220, 0), outline_color=(0, 0, 0), outline_width=5)

    # --- Bottom section: jeans large and spread, shoes between ---
    bottom_positions = [
        (280, 1220, 620, -4),   # left jeans — big
        (800, 1220, 620, 4),    # right jeans — big
    ]
    for i, bot in enumerate(bottoms):
        if i < len(bottom_positions):
            px, py, sz, rot = bottom_positions[i]
            paste_product(bot["image"], px, py, sz, rot)

    # Shoes between and below jeans
    shoe_positions = [
        (540, 1480, 400, 0),    # center sneakers
        (160, 1450, 300, -8),   # left shoe
    ]
    for i, shoe in enumerate(shoes):
        if i < len(shoe_positions):
            px, py, sz, rot = shoe_positions[i]
            paste_product(shoe["image"], px, py, sz, rot)

    # --- Bottom warning text ---
    font_warn = load_font(34)
    warn_text = "⚠ Website closes when stock is gone ⚠"
    bbox_w = draw.textbbox((0, 0), warn_text, font=font_warn)
    ww = bbox_w[2] - bbox_w[0]
    # Yellow/gold underlined text at bottom
    warn_y = H - 100
    draw.text(((W - ww) // 2, warn_y), warn_text, font=font_warn, fill=(200, 160, 0))
    # Underline
    bbox_wu = draw.textbbox(((W - ww) // 2, warn_y), warn_text, font=font_warn)
    draw.line([(bbox_wu[0], bbox_wu[3] + 2), (bbox_wu[2], bbox_wu[3] + 2)], fill=(200, 160, 0), width=2)

    canvas.save(output_path, quality=95)
    print(f"Saved: {output_path}")


def main():
    # Paths to AI-generated remakes (people wearing NEWGARMENTS clothing)
    remakes_dir = BASE / "remakes"
    pipeline_dir = Path(__file__).parent.parent.parent / "pipeline" / "output" / "2026-03-21" / "generated" / "outfits"
    product_refs = Path(__file__).parent.parent.parent / "content-library" / "product-refs"

    # Slide 1: 4 unique remakes — "You want this style?"
    slide1_imgs = [
        remakes_dir / "remake_pin1_gray.png",    # pin1: gray checkered
        remakes_dir / "remake_pin3_green.png",   # pin3: green Y2K
        remakes_dir / "remake_pin5_pink.png",    # pin5: pink Y2K
        remakes_dir / "remake_pin7_black.png",   # pin7: black checkered
    ]
    create_grid_slide(slide1_imgs, "You want this style?", OUTPUT / "slide1.png")

    # Slide 2: 4 different remakes — "But it's too expensive?"
    slide2_imgs = [
        remakes_dir / "remake_pin2_green.png",   # pin2: green Y2K
        remakes_dir / "remake_pin8_gray.png",    # pin8: gray checkered
        remakes_dir / "remake_pin6_pink.png",    # pin6: pink Y2K
        remakes_dir / "remake_1_2.png",          # pin4: black checkered
    ]
    create_grid_slide(slide2_imgs, "But it's too expensive?", OUTPUT / "slide2.png")

    # Slide 3: NEWGARMENTS product collage — 3 columns like Five Leafs
    products = [
        {
            "name": "Checkered Zipper Gray",
            "price": "€45,00",
            "original_price": "€90,00",
            "image": str(product_refs / "checkered-zipper-gray.png"),
        },
        {
            "name": "Checkered Zipper Black",
            "price": "€45,00",
            "original_price": "€90,00",
            "image": str(product_refs / "checkered-zipper-black.png"),
        },
        {
            "name": "Checkered Zipper Red",
            "price": "€45,00",
            "original_price": "€90,00",
            "image": str(product_refs / "checkered-zipper-red.png"),
        },
        {
            "name": "Zip Hoodie Y2K Green",
            "price": "€42,00",
            "original_price": "€85,00",
            "image": str(product_refs / "zip-hoodie-y2k-dark-green.png"),
        },
        {
            "name": "Zip Hoodie Y2K Black",
            "price": "€42,00",
            "original_price": "€85,00",
            "image": str(product_refs / "zip-hoodie-y2k-black.png"),
        },
        {
            "name": "Zip Hoodie Y2K Pink",
            "price": "€42,00",
            "original_price": "€85,00",
            "image": str(product_refs / "zip-hoodie-y2k-pink.png"),
        },
        {
            "name": "Embroidered Jeans",
            "price": "€48,00",
            "original_price": "€95,00",
            "image": str(product_refs / "embroidered-striped-jeans.png"),
        },
        {
            "name": "Graphic Lining Jeans",
            "price": "€48,00",
            "original_price": "€95,00",
            "image": str(product_refs / "graphic-lining-jeans.png"),
        },
        {
            "name": "Fur Graphic Sneakers",
            "price": "€55,00",
            "original_price": "€110,00",
            "image": str(product_refs / "fur-graphic-sneakers.webp"),
        },
    ]
    create_product_collage(products, OUTPUT / "slide3.png")

    print(f"\nAll 3 slides saved to: {OUTPUT}")


if __name__ == "__main__":
    main()

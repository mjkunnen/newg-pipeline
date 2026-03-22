"""Add all color x size variants to Shopify products via REST API."""
import json
import urllib.request
import ssl
import itertools

# Shopify store details (from Zapier error message)
SHOP = "2fgppd-7k.myshopify.com"
# We'll use Zapier's API request for auth, but let's try the product update approach
# Actually - let's just use the Zapier approach by building all variants at once via product update

# Product configs
PRODUCTS = {
    "cargo_pants": {
        "id": 15415007576441,
        "price": "44.95",
        "colors": ["Black", "Light Gray", "Army Green", "Dark Gray"],
        "sizes": ["S", "M", "L", "XL", "2XL"],
    },
}

# Generate variant combinations we still need to add
# (Black/S and Black/M already exist)
existing = [("Black", "S"), ("Black", "M")]

for name, prod in PRODUCTS.items():
    combos = list(itertools.product(prod["colors"], prod["sizes"]))
    needed = [c for c in combos if c not in existing]
    print(f"\n{name} (ID: {prod['id']})")
    print(f"  Total combos: {len(combos)}")
    print(f"  Already exist: {len(existing)}")
    print(f"  Need to add: {len(needed)}")
    for color, size in needed:
        print(f"    - {color} / {size}")

from datetime import datetime
import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from supabase import create_client

# Steam Top Sellers page
url = "https://store.steampowered.com/search/?filter=topsellers"

# Browser headers
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# Request page
response = requests.get(url, headers=headers, timeout=20)
response.raise_for_status()

# Parse HTML
soup = BeautifulSoup(response.text, "html.parser")

rows = []

# Get top 10 games
games = soup.select("a.search_result_row")[:10]

scrape_time = datetime.now().isoformat()

for game in games:

    # Title
    title_tag = game.select_one(".title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Price
    price_tag = game.select_one(".discount_final_price")

    if not price_tag:
        price_tag = game.select_one(".search_price")

    price_usd = (
        price_tag.get_text(" ", strip=True)
        if price_tag else None
    )

    # Discount
    discount_tag = game.select_one(".discount_pct")
    discount = (
        discount_tag.get_text(strip=True)
        if discount_tag else "0%"
    )

    # Release date
    release_tag = game.select_one(".search_released")
    release_date = (
        release_tag.get_text(strip=True)
        if release_tag else ""
    )

    # Platforms
    platform_icons = game.select(".platform_img")

    platforms = [
        icon["class"][-1]
        for icon in platform_icons
        if len(icon.get("class", [])) > 1
    ]

    rows.append({
        "title": title,
        "price_usd": price_usd,
        "discount": discount,
        "release_date": release_date,
        "platforms": ", ".join(platforms),
        "scraped_at": scrape_time,
    })

# Create DataFrame
df = pd.DataFrame(rows)

# Clean price column
df["price_usd"] = (
    df["price_usd"]
    .astype(str)
    .str.replace("$", "", regex=False)
    .str.replace(",", "", regex=False)
    .str.strip()
)

# Convert to number
df["price_usd"] = pd.to_numeric(
    df["price_usd"],
    errors="coerce"
)

# Fill missing prices with 0
df["price_usd"] = df["price_usd"].fillna(0)

# Create price tiers
df["price_tier"] = df["price_usd"].apply(
    lambda p:
        "Budget" if p < 20
        else (
            "Mid-range" if p < 40
            else "Premium"
        )
)

# Debug output
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print(df.head())

# Save CSV
df.to_csv(
    "steam_top_10_bestsellers.csv",
    index=False
)

# =========================
# SUPABASE
# =========================

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

insert_rows = []

for _, row in df.iterrows():

    insert_rows.append({
        "title": str(row["title"]),
        "price_usd": float(row["price_usd"]),
        "discount": str(row["discount"]),
        "release_date": str(row["release_date"]),
        "platforms": str(row["platforms"]),
        "price_tier": str(row["price_tier"]),
        "scraped_at": str(row["scraped_at"]),
    })

# Insert into Supabase table
result = (
    supabase
    .table("steam")
    .insert(insert_rows)
    .execute()
)

print(f"✅ Inserted {len(insert_rows)} rows into Supabase")

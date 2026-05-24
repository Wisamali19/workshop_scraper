from datetime import datetime
import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from supabase import create_client

# =========================
# CONFIG
# =========================
URL = "https://store.steampowered.com/search/?filter=topsellers"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# =========================
# SCRAPE
# =========================
response = requests.get(URL, headers=HEADERS, timeout=20)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
games = soup.select("a.search_result_row")[:10]

rows = []
scraped_at = datetime.utcnow()

for game in games:

    title = game.select_one(".title")
    title = title.get_text(strip=True) if title else None

    price_tag = game.select_one(".discount_final_price") or game.select_one(".search_price")
    price_text = price_tag.get_text(" ", strip=True) if price_tag else None

    discount_tag = game.select_one(".discount_pct")
    discount = discount_tag.get_text(strip=True) if discount_tag else "0%"

    release_tag = game.select_one(".search_released")
    release_date = release_tag.get_text(strip=True) if release_tag else ""

    platforms = [
        icon["class"][-1]
        for icon in game.select(".platform_img")
        if len(icon.get("class", [])) > 1
    ]

    rows.append({
        "title": title,
        "price_raw": price_text,
        "discount": discount,
        "release_date": release_date,
        "platforms": ", ".join(platforms),
        "scraped_at": scraped_at
    })

# =========================
# DATA CLEANING
# =========================
df = pd.DataFrame(rows)

# clean price → numeric
df["price_usd"] = (
    df["price_raw"]
    .astype(str)
    .str.replace("$", "", regex=False)
    .str.replace("€", "", regex=False)
    .str.strip()
)

df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce").fillna(0)

# price tier logic
df["price_tier"] = df["price_usd"].apply(
    lambda p: "Budget" if p < 20 else ("Mid-range" if p < 40 else "Premium")
)

# =========================
# SUPABASE
# =========================
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

insert_rows = []

for _, row in df.iterrows():
    insert_rows.append({
        "title": str(row["title"]),
        "price_usd": float(row["price_usd"]),
        "discount": str(row["discount"]),
        "release_date": str(row["release_date"]),
        "platforms": str(row["platforms"]),
        "price_tier": str(row["price_tier"]),
        "scraped_at": str(row["scraped_at"])
    })

# insert
supabase.table("steam").insert(insert_rows).execute()

print(f"✅ Inserted {len(insert_rows)} rows into Supabase")

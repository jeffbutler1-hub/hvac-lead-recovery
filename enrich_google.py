# ==========================
# GOOGLE ENRICHER V3 (IMPROVED MATCHING)
# ==========================

import requests
import pandas as pd
import time
import os
from dotenv import load_dotenv

# --------------------------
# Load API key
# --------------------------
load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

if not API_KEY:
    raise ValueError("Missing GOOGLE_PLACES_API_KEY")

INPUT_FILE = "results.csv"
OUTPUT_FILE = "results_with_google.csv"

DEFAULT_LOCATION = "Austin TX"


# --------------------------
# Google API calls
# --------------------------

def find_place(query):
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"

    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name",
        "key": API_KEY
    }

    try:
        r = requests.get(url, params=params)
        data = r.json()

        if data.get("candidates"):
            return data["candidates"][0]["place_id"]

    except Exception as e:
        print(f"[ERROR] find_place failed for {query}: {e}")

    return None


def get_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"

    params = {
        "place_id": place_id,
        "fields": "rating,user_ratings_total",
        "key": API_KEY
    }

    try:
        r = requests.get(url, params=params)
        data = r.json()

        if "result" in data:
            result = data["result"]
            return (
                result.get("rating"),
                result.get("user_ratings_total")
            )

    except Exception as e:
        print(f"[ERROR] details failed for {place_id}: {e}")

    return None, None


# --------------------------
# Build query variations
# --------------------------

def build_queries(domain):
    clean = domain.replace(".com", "").replace("-", " ")

    return [
        domain,                                   # exact domain
        clean,                                    # cleaned name
        f"{clean} HVAC",                          # + category
        f"{clean} HVAC {DEFAULT_LOCATION}",       # + location
    ]


# --------------------------
# Main enrichment logic
# --------------------------

def get_place_id(domain):
    queries = build_queries(domain)

    for q in queries:
        place_id = find_place(q)

        if place_id:
            print(f"[MATCH] {domain} → {q}")
            return place_id

    print(f"[NO MATCH] {domain}")
    return None


# --------------------------
# Main run
# --------------------------

def main():
    df = pd.read_csv(INPUT_FILE)

    ratings = []
    review_counts = []

    for i, row in df.iterrows():
        domain = row["Domain"]

        print(f"\n[{i+1}/{len(df)}] Processing: {domain}")

        place_id = get_place_id(domain)

        if place_id:
            rating, count = get_details(place_id)
        else:
            rating, count = None, None

        ratings.append(rating)
        review_counts.append(count)

        # avoid rate limits
        time.sleep(0.3)

    df["GoogleRating"] = ratings
    df["GoogleReviewCount"] = review_counts

    df.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ Done. Saved to results_with_google.csv")


# --------------------------
# Run
# --------------------------

if __name__ == "__main__":
    main()
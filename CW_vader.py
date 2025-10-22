import json
import pandas as pd
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

# Ensure VADER is available
nltk.download("vader_lexicon")

# Input and output files
INPUT_FILE = "chemist_warehouse_reviews_20250925_194924"   # <-- change if needed
OUTPUT_JSON = "cw_reviews_sentiment1.json"
OUTPUT_CSV = "cw_product_vader_scores1.csv"

# Load Chemist Warehouse JSON
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

analyzer = SentimentIntensityAnalyzer()
processed_reviews = []
summary_records = []

# Iterate over each product
for product in data:
    product_name = product.get("title") or product.get("link")

    # Extract reviews from "Reviewer Details"
    for key, rev in product.get("Reviewer Details", {}).items():
        review_text = rev.get("review", "")
        stars = rev.get("review_stars", "")

        # Run VADER sentiment
        scores = analyzer.polarity_scores(review_text)

        # Classify sentiment
        if scores["compound"] >= 0.05:
            sentiment = "Positive"
        elif scores["compound"] <= -0.05:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        # Enrich review with VADER scores
        rev["vader_sentiment"] = sentiment
        rev["compound"] = scores["compound"]
        rev["pos"] = scores["pos"]
        rev["neg"] = scores["neg"]
        rev["neu"] = scores["neu"]

        # Flatten for DataFrame
        processed_reviews.append({
            "product": product_name,
            "category": product.get("category"),
            "review": review_text,
            "rating_text": stars,
            "vader_sentiment": sentiment,
            "compound": scores["compound"],
            "pos": scores["pos"],
            "neg": scores["neg"],
            "neu": scores["neu"],
        })

# Save enriched JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

# Convert to DataFrame
df = pd.DataFrame(processed_reviews)

# Group by product for summary
summary_df = (
    df.groupby(["product", "category"])
    .agg(
        avg_compound=("compound", "mean"),
        avg_pos=("pos", "mean"),
        avg_neg=("neg", "mean"),
        avg_neu=("neu", "mean"),
        positive_reviews=("vader_sentiment", lambda x: (x == "Positive").sum()),
        negative_reviews=("vader_sentiment", lambda x: (x == "Negative").sum()),
        neutral_reviews=("vader_sentiment", lambda x: (x == "Neutral").sum()),
        total_reviews=("vader_sentiment", "count")
    )
    .reset_index()
)

# Add overall sentiment
def overall_sentiment(row):
    if row["avg_compound"] >= 0.05:
        return "Positive"
    elif row["avg_compound"] <= -0.05:
        return "Negative"
    else:
        return "Neutral"

summary_df["overall_sentiment"] = summary_df.apply(overall_sentiment, axis=1)

# Save summary CSV
summary_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

print(f"✅ VADER-processed JSON saved: {OUTPUT_JSON}")
print(f"✅ Summary CSV saved: {OUTPUT_CSV}")

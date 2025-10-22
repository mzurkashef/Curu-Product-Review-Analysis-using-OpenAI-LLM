import json
import pandas as pd
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

# Ensure VADER is available
nltk.download("vader_lexicon")

# File paths
INPUT_FILE = "myer_skin_care_reviews.json"
OUTPUT_JSON = "myer_skin_care_reviews_vader.json"
OUTPUT_CSV = "myer_skin_care_reviews_vader.csv"

# Load Myer JSON
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

analyzer = SentimentIntensityAnalyzer()
processed_reviews = []
summary_records = []

for product in data.get("products", []):
    product_name = product.get("product_name") or product.get("product_url")
    for rev in product.get("reviews", []):
        review_text = rev.get("body", "")
        scores = analyzer.polarity_scores(review_text)
        
        # classify sentiment
        if scores["compound"] >= 0.05:
            sentiment = "Positive"
        elif scores["compound"] <= -0.05:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
        
        # enrich review
        rev["vader_sentiment"] = sentiment
        rev["compound"] = scores["compound"]
        rev["pos"] = scores["pos"]
        rev["neg"] = scores["neg"]
        rev["neu"] = scores["neu"]

        processed_reviews.append({
            "product": product_name,
            "review": review_text,
            "rating": rev.get("rating"),
            "vader_sentiment": sentiment,
            "compound": scores["compound"],
            "pos": scores["pos"],
            "neg": scores["neg"],
            "neu": scores["neu"],
        })

# Save enriched JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

# Convert to DataFrame for CSV summary
df = pd.DataFrame(processed_reviews)

summary_df = (
    df.groupby("product")
    .agg(
        avg_compound=("compound", "mean"),
        avg_pos=("pos", "mean"),
        avg_neg=("neg", "mean"),
        avg_neu=("neu", "mean"),
        positive_reviews=("vader_sentiment", lambda x: (x == "Positive").sum()),
        negative_reviews=("vader_sentiment", lambda x: (x == "Negative").sum()),
        neutral_reviews=("vader_sentiment", lambda x: (x == "Neutral").sum()),
    )
    .reset_index()
)

# Add overall sentiment label
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

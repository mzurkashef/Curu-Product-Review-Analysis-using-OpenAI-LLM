import pandas as pd
import matplotlib.pyplot as plt

# Input file (generated from cw_vader.py)
INPUT_CSV = "cw_product_vader_scores1.csv"

# Load summary
df = pd.read_csv(INPUT_CSV)

# =========================
# 1. Overall Sentiment Distribution
# =========================
sentiment_counts = df["overall_sentiment"].value_counts()

plt.figure(figsize=(6, 6))
sentiment_counts.plot(kind="pie", autopct="%1.1f%%", colors=["green", "red", "gray"])
plt.title("Overall Sentiment Distribution (Chemist Warehouse Products)")
plt.ylabel("")
plt.savefig("cw_overall_sentiment_pie.png")
plt.close()

# =========================
# 2. Review Sentiment by Category
# =========================
plt.figure(figsize=(10, 6))
df.groupby("category")["overall_sentiment"].value_counts(normalize=True).unstack().plot(
    kind="bar", stacked=True, figsize=(10, 6), color=["green", "red", "gray"]
)
plt.title("Sentiment Distribution by Product Category")
plt.xlabel("Category")
plt.ylabel("Proportion of Reviews")
plt.legend(title="Sentiment")
plt.tight_layout()
plt.savefig("cw_sentiment_by_category.png")
plt.close()

# =========================
# 3. Top Products by Average Compound Score
# =========================
top_products = df.sort_values("avg_compound", ascending=False).head(10)

plt.figure(figsize=(10, 6))
plt.barh(top_products["product"], top_products["avg_compound"], color="green")
plt.title("Top 10 Products by Sentiment Score")
plt.xlabel("Average Compound Score")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("cw_top_products.png")
plt.close()

# =========================
# 4. Negative Reviews Analysis
# =========================
neg_products = df.sort_values("negative_reviews", ascending=False).head(10)

plt.figure(figsize=(10, 6))
plt.barh(neg_products["product"], neg_products["negative_reviews"], color="red")
plt.title("Products with Most Negative Reviews")
plt.xlabel("Count of Negative Reviews")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("cw_most_negative_products.png")
plt.close()

print("✅ Visualizations generated:")
print(" - cw_overall_sentiment_pie.png")
print(" - cw_sentiment_by_category.png")
print(" - cw_top_products.png")
print(" - cw_most_negative_products.png")

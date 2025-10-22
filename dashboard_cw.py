import streamlit as st 
import pandas as pd
import json
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
import re
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# Load environment variables for OpenAI
load_dotenv()

# -------------------------------
# Load JSON + CSV per website
# -------------------------------
@st.cache_data
def load_data(site):
    if site == "Amazon":
        reviews_file = "amazon_search_results_1.json"   # after sentiment
        csv_file = "product_vader_scores.csv"
        with open(reviews_file, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        summary_df = pd.read_csv(csv_file, encoding="utf-8")
        return reviews, summary_df

    elif site == "Myer":
        reviews_file = "myer_skin_care_reviews_vader.json"
        csv_file = "myer_skin_care_reviews_vader.csv"
        with open(reviews_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        reviews = []
        for product in raw.get("products", []):
            product_name = product.get("name") or product.get("product_url")
            for r in product.get("reviews", []):
                reviews.append({
                    "product": product_name,
                    "review": r.get("body"),
                    "vader_sentiment": r.get("vader_sentiment", "Neutral")
                })

        summary_df = pd.read_csv(csv_file, encoding="utf-8")
        return reviews, summary_df

    elif site == "Mecca":
        reviews_file = "mecca_skin_care_reviews_vader.json"
        csv_file = "mecca_skin_care_reviews_vader.csv"
        with open(reviews_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        reviews = []
        for product in raw.get("products", []):
            product_name = product.get("name") or product.get("product_url")
            for r in product.get("reviews", []):
                reviews.append({
                    "product": product_name,
                    "review": r.get("body"),
                    "vader_sentiment": r.get("vader_sentiment", "Neutral")
                })

        summary_df = pd.read_csv(csv_file, encoding="utf-8")
        return reviews, summary_df
    
    elif site == "Chemist Warehouse":
        reviews_file = "cw_reviews_sentiment1.json"
        csv_file = "cw_product_vader_scores1.csv"

        with open(reviews_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        reviews = []

        if isinstance(raw, dict) and "products" in raw:
            products = raw["products"]
        elif isinstance(raw, list):
            products = raw
        else:
            products = []

        for product in products:
            product_name = product.get("name") or product.get("product_url")
            for r in product.get("reviews", []):
                reviews.append({
                    "product": product_name,
                    "review": r.get("body"),
                    "vader_sentiment": r.get("vader_sentiment", "Neutral")
                })

        summary_df = pd.read_csv(csv_file, encoding="utf-8")
        if "product" not in summary_df.columns:
            summary_df = summary_df.rename(columns={summary_df.columns[0]: "product"})

        return reviews, summary_df

    else:
        raise ValueError("Unknown site")

# -------------------------------
# Sidebar selections
# -------------------------------

st.title("🧴 Product Review Analysis (Amazon, Myer, Mecca & Chemist Warehouse)")

site = st.selectbox("🌍 Select a Website", ["Amazon", "Myer", "Mecca", "Chemist Warehouse"])

reviews, summary_df = load_data(site)

# --- Add helper function for categories ---
def assign_category(product_name: str) -> str:
    product_name = str(product_name).lower()
    if "cleanser" in product_name or "cleanse" in product_name:
        return "cleanser"
    elif "toner" in product_name:
        return "toner"
    elif "serum" in product_name:
        return "serum"
    elif "moisturizer" in product_name or "cream" in product_name or "lotion" in product_name:
        return "moisturizer"
    elif "sunscreen" in product_name or "spf" in product_name:
        return "sunscreen"
    else:
        return "other"

# --- Myer, Mecca & Chemist Warehouse: use category + product sub-dropdowns ---
if site in ["Myer", "Mecca", "Chemist Warehouse"]:
    summary_df["category"] = summary_df["product"].apply(assign_category)

    categories = summary_df["category"].dropna().unique().tolist()
    selected_category = st.selectbox("📂 Select a Category", categories)

    category_products = summary_df[summary_df["category"] == selected_category]["product"].tolist()
    selected_product = st.selectbox("🧴 Select a Product", category_products)
else:
    product_list = summary_df["product"].tolist()
    selected_product = st.selectbox("🛍 Select a Product", product_list)

# 🔎 Filter reviews for selected product
product_reviews = [r for r in reviews if r.get("product") == selected_product]
positive_reviews = [r["review"] for r in product_reviews if r.get("vader_sentiment") == "Positive"]
negative_reviews = [r["review"] for r in product_reviews if r.get("vader_sentiment") == "Negative"]

# Balance positive/negative (max 50 each)
positive_reviews = positive_reviews[:50]
negative_reviews = negative_reviews[:50]
bal_reviews = positive_reviews + negative_reviews

# Get summary row
product_stats = summary_df[summary_df["product"] == selected_product].iloc[0]

# -------------------------------
# Sentiment Overview
# -------------------------------
st.subheader("📊 Sentiment Overview")

sentiment_color = {"Positive": "green", "Negative": "red", "Neutral": "gray"}
overall = product_stats["overall_sentiment"]

st.markdown(
    f"**Overall Sentiment:** "
    f"<span style='color:{sentiment_color[overall]}; font-size:20px;'>{overall}</span>",
    unsafe_allow_html=True,
)

# Gauge chart for compound sentiment
compound_score = product_stats["avg_compound"]

gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=compound_score,
    title={'text': "Compound Sentiment Score"},
    gauge={
        'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': "darkgray"},
        'bar': {'color': "blue"},
        'steps': [
            {'range': [-1, -0.5], 'color': "red"},
            {'range': [-0.5, 0], 'color': "orange"},
            {'range': [0, 0.5], 'color': "lightgreen"},
            {'range': [0.5, 1], 'color': "green"},
        ],
        'threshold': {
            'line': {'color': "black", 'width': 4},
            'thickness': 0.75,
            'value': compound_score
        }
    }
))
gauge.update_layout(height=150, margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(gauge, use_container_width=True)

# Bar chart for sentiment counts
sentiment_counts = {
    "Positive": product_stats["positive_reviews"],
    "Negative": product_stats["negative_reviews"],
    "Neutral": product_stats["neutral_reviews"],
}
bar_df = pd.DataFrame(list(sentiment_counts.items()), columns=["Sentiment", "Count"])
sentiment_order = ["Positive", "Neutral", "Negative"]
bar_df["Sentiment"] = pd.Categorical(bar_df["Sentiment"], categories=sentiment_order, ordered=True)
bar_df = bar_df.sort_values("Sentiment", ascending=True)

fig = px.bar(
    bar_df,
    x="Count",
    y="Sentiment",
    orientation="h",
    color="Sentiment",
    color_discrete_map={"Positive": "green", "Negative": "red", "Neutral": "gray"},
    text="Count",
)
fig.update_traces(textposition="outside", textfont_size=16, marker_line_width=1.2)
fig.update_layout(
    title="Review Sentiment Distribution",
    title_font_size=16,
    xaxis_title="Number of Reviews",
    yaxis_title="Sentiment",
    height=300,
    margin=dict(t=30, b=20, l=10, r=10),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# # -------------------------------
# # LLM Insights (Skin Segmentation Focus)
# # -------------------------------
# review_analysis_prompt = PromptTemplate(
#     input_variables=["reviews"],
#     template="""
#     You are an expert skincare analyst evaluating customer reviews.

#     Analyze the following customer reviews (mix of positive and negative) and provide a structured analysis segmented by **skin type**, **sensitivity**, and **skin concerns**.

#     ---  
#     ### Skin Profile Segmentation
#     **Skin Types:**
#     - Dry  
#     - Oily  
#     - Combination  
#     - Normal  

#     **Sensitivity:**
#     - Sensitive  
#     - Not Sensitive  

#     **Skin Concerns:**
#     - Acne  
#     - Pigmentation & Scarring  
#     - Ageing  
#     - Blackheads  
#     - Large pores  
#     - Dullness  
#     - Redness  
#     - Eczema, Psoriasis, Rosacea  
#     - Dark circles  
#     - Uneven texture  
#     ---  

#     Using this segmentation, perform the following:

#     1. Identify the **top 5 positive insights** customers appreciated — grouped by relevant skin type, sensitivity, or concern.
#     2. Identify the **top 5 negative insights** customers complained about — grouped similarly.
#     3. Extract up to **10 important keywords or ingredients** mentioned in reviews, including:
#        - Number of **positive mentions**
#        - Number of **negative mentions**
#        - The most relevant **skin profile segment(s)**

#     Reviews:
#     {reviews}

#     Output Format (Markdown):

#     ### 🟩 Positive Insights (by Skin Profile)
#     - **Dry Skin:** ...
#     - **Oily Skin:** ...
#     - **Sensitive Skin:** ...
#     - **Acne-Prone Skin:** ...
#     - ...

#     ### 🟥 Negative Insights (by Skin Profile)
#     - **Dry Skin:** ...
#     - **Oily Skin:** ...
#     - **Sensitive Skin:** ...
#     - **Acne-Prone Skin:** ...
#     - ...

#     ### 🔑 Top Keywords and Mentions
#     - keyword1: X positive mentions, Y negative mentions — relevant for {{skin profile(s)}}
#     - keyword2: ...
#     """
# )

# llm = ChatOpenAI(temperature=0.5, model="gpt-3.5-turbo")
# chain = LLMChain(llm=llm, prompt=review_analysis_prompt)

# with st.spinner("Analyzing reviews by skin profile segmentation..."):
#     response = chain.run({"reviews": " ".join(bal_reviews)})

# st.subheader("📈 Review Analysis Summary")

# positive_section = re.search(r"### 🟩 Positive Insights.*?\n(.*?)\n###", response, re.DOTALL)
# negative_section = re.search(r"### 🟥 Negative Insights.*?\n(.*?)\n###", response, re.DOTALL)
# keywords_section = re.search(r"### 🔑 Top Keywords.*?\n(.*)", response, re.DOTALL)

# st.subheader("✨ Positive Insights (by Skin Profile)")
# st.success(positive_section.group(1).strip() if positive_section else "Not found.")

# st.subheader("⚠️ Negative Insights (by Skin Profile)")
# st.error(negative_section.group(1).strip() if negative_section else "Not found.")

# st.subheader("🔑 Top Keywords (by Skin Profile)")
# st.markdown(keywords_section.group(1).strip() if keywords_section else "Not found.")
# -------------------------------
# LLM Insights
# -------------------------------

# === 1️⃣ Existing Overall Prompt ===
review_analysis_prompt = PromptTemplate(
    input_variables=["reviews"],
    template="""
    You are an expert assistant analyzing customer reviews for a skincare product.

    Given the following customer reviews (mixed positive and negative), do the following:
    1. Identify the **top 5 positive key points** customers appreciated.
    2. Identify the **top 5 negative key points** customers complained about.
    3. Extract up to **8 important keywords** (relevant to skincare concerns, ingredients, 
    skin types, product effects, or common themes) mentioned in the reviews that customers look for. For each keyword, include:
    - Total number of **positive mentions**
    - Total number of **negative mentions**
    - Ensure that similar keywords (like "oily skin" and "greasy") are considered together.
    
    Reviews:
    {reviews}

    Output format:
    ### Positive Insights:
    - ...
    - ...

    ### Negative Insights:
    - ...
    - ...

    ### Top Keywords and Mentions:
    - keyword1: X positive mentions, Y negative mentions  
    - keyword2: A positive mentions, B negative mentions  
    ... up to 8
    """
)

# === 2️⃣ NEW Skin-Segmented Prompt ===
skin_segmentation_prompt = PromptTemplate(
    input_variables=["reviews"],
    template="""
    You are an advanced skincare expert analyzing customer reviews.  
    Classify and summarize feedback **by skin profile segments**.

    Use the following segmentation criteria:

    **Skin Type:**
    - Dry  
    - Oily  
    - Combination  
    - Normal  

    **Sensitivity:**
    - Sensitive  
    - Not Sensitive  

    **Skin Concerns:**
    - Acne  
    - Pigmentation & Scarring  
    - Ageing  
    - Blackheads  
    - Large pores  
    - Dullness  
    - Redness  
    - Eczema, Psoriasis, Rosacea  
    - Dark circles  
    - Uneven texture  

    Analyze the reviews below and:
    1. Group feedback by **skin profile segment** (skin type, sensitivity, and concern).  
      

    Reviews:
    {reviews}

    Output Format:
    ### 🧬 Skin Profile–Segmented Insights
    #### Dry Skin
    - 1: ...
    - 2: ...

    #### Oily Skin
    - 1: ...
    - 2: ...

    #### Sensitive Skin
    - 1: ...
    - 2: ...

    #### Acne-Prone Skin
    - 1: ...
    - 2: ...

    (Continue for any relevant segments)
    """
)

# === 3️⃣ Run both LLM analyses ===
llm = ChatOpenAI(temperature=0.5, model="gpt-3.5-turbo")

chain_general = LLMChain(llm=llm, prompt=review_analysis_prompt)
chain_skin = LLMChain(llm=llm, prompt=skin_segmentation_prompt)

with st.spinner("Analyzing reviews (general insights)..."):
    response_general = chain_general.run({"reviews": " ".join(bal_reviews)})

with st.spinner("Analyzing reviews (skin profile segmentation)..."):
    response_skin = chain_skin.run({"reviews": " ".join(bal_reviews)})

# === 4️⃣ Display General Insights ===
st.subheader("📈 Review Analysis Summary")

positive_section = re.search(r"### Positive Insights:\n(.*?)\n###", response_general, re.DOTALL)
negative_section = re.search(r"### Negative Insights:\n(.*?)\n###", response_general, re.DOTALL)
keywords_section = re.search(r"### Top Keywords and Mentions:\n(.*)", response_general, re.DOTALL)

st.subheader("✨ Positive Insights")
st.success(positive_section.group(1).strip() if positive_section else "Not found.")

st.subheader("⚠️ Negative Insights")
st.error(negative_section.group(1).strip() if negative_section else "Not found.")

st.subheader("🔑 Top Keywords")
st.markdown(keywords_section.group(1).strip() if keywords_section else "Not found.")

# === 5️⃣ NEW Subsection: Skin Profile–Segmented Analysis ===
st.markdown("---")
#st.subheader("🧬 Skin Profile–Segmented Insights")
st.markdown(response_skin)

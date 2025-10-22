# Curu-Product-Review-Analysis-using-OpenAI-LLM
# CURU Skincare Analytics Dashboard  

A multi-source skincare review analytics app that aggregates, analyzes, and visualizes customer sentiments from **Amazon**, **Myer**, **Mecca**, and **Chemist Warehouse**.  
Built using **Streamlit**, **VADER sentiment analysis**, and **OpenAI GPT models**, Curu provides deep insights into customer opinions, ingredients, and skincare needs across multiple platforms.

---

## Features  

- **Multi-Website Review Integration**  
  Supports data ingestion and processing from:
  - Amazon  
  - Myer  
  - Mecca  
  - Chemist Warehouse  

- **Sentiment Analysis (VADER)**  
  Each review is automatically scored and labeled as Positive, Neutral, or Negative.

- **AI-Powered Insights (OpenAI)**  
  The app uses GPT to generate:  
  - Top positive and negative customer insights  
  - Key product keywords and themes  
  - Skin-type segmented insights (Dry, Oily, Combination, Sensitive, etc.)

- **Interactive Streamlit Dashboard**  
  - Dynamic product & category selection  
  - Sentiment distribution charts  
  - Gauge visualization of compound sentiment  
  - Summarized AI-generated insights  

- **Skin Profile Segmentation**  
  Additional layer of insight segmented by:  
  - Skin Type (Dry, Oily, Combination, Normal)  
  - Sensitivity (Sensitive / Not Sensitive)  
  - Concerns (Acne, Pigmentation, Ageing, Dullness, Redness, etc.)

---

## Tech Stack  

| Component | Technology |
|------------|-------------|
| **Frontend / Dashboard** | Streamlit |
| **Language** | Python 3.9+ |
| **AI / NLP** | OpenAI GPT API, VADER Sentiment Analyzer |
| **Data Handling** | Pandas, JSON |
| **Visualization** | Plotly, Streamlit Charts |
| **Environment** | `.env` for API keys |
| **Version Control** | Git + GitHub |

---

## Project Structure  
CURU-Skincare-Analytics
├── amazon_search_results_1.json
├── myer_skin_care_reviews_vader.json
├── mecca_skin_care_reviews_vader.json
├── cw_reviews_sentiment1.json
├── product_vader_scores.csv
├── myer_skin_care_reviews_vader.csv
├── mecca_skin_care_reviews_vader.csv
├── cw_product_vader_scores1.csv
├── dashboard_curu.py
├── requirements.txt
├── .env
└── README.md


---

## Setup Instructions  

### 1. Clone the Repository  
git clone https://github.com/<your-username>/curu-skincare-analytics.git
cd curu-skincare-analytics

### 2. Create and Activate a Virtual Environment
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS / Linux

### 3. Install Dependencies
pip install -r requirements.txt

Add Your OpenAI API Key

### 4. Create a .env file in the root directory:
OPENAI_API_KEY=your_openai_api_key_here

### 5. Run the Streamlit App
streamlit run dashboard_cw.py

| Section                           | Description                                                 |
| --------------------------------- | ----------------------------------------------------------- |
| 🌍 **Website Selector**           | Choose data source (Amazon, Myer, Mecca, Chemist Warehouse) |
| 🧴 **Category & Product Filters** | Filter by product category (cleanser, serum, toner, etc.)   |
| 📊 **Sentiment Overview**         | Gauge meter showing average compound sentiment              |
| 📈 **Sentiment Distribution**     | Bar chart for positive/neutral/negative review counts       |
| 🤖 **AI Insights**                | GPT-powered summary of customer opinions                    |
| 💆 **Skin Type Segmentation**     | Detailed breakdown by skin type, sensitivity, and concerns  |

## 🧩 Example Insights
### ✨ Positive Insights

Hydrates well for dry and combination skin
Lightweight formula absorbs quickly without residue
Works effectively for acne-prone and sensitive skin

### ⚠️ Negative Insights

Fragrance too strong for sensitive users
May leave oily finish for combination skin types

### 🔑 Top Keywords

Hydration, Vitamin C, Non-greasy, Lightweight, SPF protection

### Testing

Verify JSON files for correct structure (products, reviews, vader_sentiment)
Ensure VADER pre-processing is completed before dashboard load
Use streamlit run for live testing with sample datasets

### Future Enhancements

Add user-uploaded review data for custom sentiment analysis
Include brand-wise comparison and trend visualization
Deploy on Streamlit Cloud or Render
Expand AI analysis to multilingual reviews

## License:
This project is released under the MIT License.
Feel free to use, modify, and distribute for academic or research purposes.

import os
import random
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse

# ============= GLOBAL VARIABLES =============
df = None
tfidf = None
tfidf_matrix = None
indices = None

# ============= MODEL BUILDER ============
def load_and_build_model():
    global df, tfidf, tfidf_matrix, indices

    app_dir = os.path.join(settings.BASE_DIR, "rec_app")
    products_path = os.path.join(app_dir, "amazon_sample_products.csv")
    categories_path = os.path.join(app_dir, "amazon_sample_category.csv")

    if not os.path.exists(products_path) or not os.path.exists(categories_path):
        print("❌ ERROR: CSV files not found")
        return False

    products = pd.read_csv(products_path)
    categories = pd.read_csv(categories_path)

    merged = products.merge(categories, left_on='category_id', right_on='id', how='inner')
    merged = merged[['asin', 'title', 'category_name', 'price', 'imgUrl']].dropna().reset_index(drop=True)
    
    # Use only top 50k rows (safe)
    df_ = merged.head(50000).copy()
    df = df_

    # Build TF-IDF
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(df['title'])

    # Create ASIN -> index mapping
    indices = pd.Series(df.index, index=df['asin']).drop_duplicates()

    print(f"✅ Model loaded successfully: {len(df)} products")
    return True

# Auto-load model
load_and_build_model()


# ============= RECOMMENDATION FUNCTIONS =============
def find_best_match_asin(user_input, N=1):
    if df is None:
        return []

    user_vec = tfidf.transform([user_input])
    sim_scores = cosine_similarity(user_vec, tfidf_matrix)[0]
    top_indices = sim_scores.argsort()[::-1][:N]
    return df['asin'].iloc[top_indices].tolist()


def get_recommendations_by_name(asin, k=5):
    idx = indices.get(asin)
    if idx is None:
        return []

    prod_vec = tfidf_matrix[idx]
    sim_scores = cosine_similarity(prod_vec, tfidf_matrix)[0]
    top_indices = sim_scores.argsort()[::-1][1:k+1]  # skip itself
    return df['asin'].iloc[top_indices].tolist()


def get_recommendations_by_category(asin, k=5):
    category = df.loc[df['asin'] == asin, 'category_name'].iloc[0]
    same_cat = df[(df['category_name'] == category) & (df['asin'] != asin)]
    if same_cat.empty:
        return []
    return same_cat.sample(n=min(k, len(same_cat)))['asin'].tolist()


def recommend_products(asin, k=5):
    if asin not in df['asin'].values:
        return None, []

    strategy = "Category Based" if random.randint(0, 1) else "Name Similarity"
    rec_list = get_recommendations_by_category(asin, k) if strategy == "Category Based" else get_recommendations_by_name(asin, k)

    result = []
    for r in rec_list:
        p = df[df['asin'] == r].iloc[0]
        result.append({
            "asin": p['asin'],
            "title": p['title'],
            "category": p['category_name'],
            "price": f"{p['price']:.2f}",
            "imgUrl": p['imgUrl']
        })

    return strategy, result


# ============= VIEWS =============
def home(request):
    global df
    if df is None:
        load_and_build_model()

    trending = df.sample(min(50, len(df))).to_dict('records')
    return render(request, "index.html", {"trending_products": trending})


def search_view(request):
    return render(request, "search.html")


def ajax_search(request):
    query = request.GET.get("query", "").strip()
    if not query:
        return JsonResponse({"results": []})

    matches = find_best_match_asin(query, N=1)
    results = []

    if matches:
        asin = matches[0]
        p = df[df['asin'] == asin].iloc[0]
        results.append({
            "asin": p['asin'],
            "title": p['title'],
            "category": p['category_name'],
            "price": f"{p['price']:.2f}",
            "imgUrl": p['imgUrl']
        })

        _, recs = recommend_products(asin, k=5)
        results.extend(recs)

    return JsonResponse({"results": results})

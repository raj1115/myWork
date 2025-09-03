import os
import json
import re
import numpy as np
import pandas as pd
import joblib
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ——————————————
# 1. SERVE ROOT-LEVEL STATIC FILES
# ——————————————

@app.route("/")
def home():
    # serve index.html from project root
    return send_from_directory(os.getcwd(), "index.html")

@app.route("/style.css")
def css():
    return send_from_directory(os.getcwd(), "style.css", mimetype="text/css")

@app.route("/script.js")
def js():
    return send_from_directory(os.getcwd(), "script.js", mimetype="application/javascript")


# ——————————————
# 2. LOAD DATA & PREPROCESSOR
# ——————————————

with open("Final Dataset 320 json.json", "r", encoding="utf-8") as f:
    data = json.load(f)
df = pd.DataFrame(data)

def parse_quantity(q):
    if not isinstance(q, str):
        return np.nan
    m = re.search(r'~\s*(\d+)\s*g', q)
    if m:
        return float(m.group(1))
    m2 = re.search(r'(\d+)\s*g', q)
    return float(m2.group(1)) if m2 else np.nan

df["QuantityGrams"]   = df["Quantity"].apply(parse_quantity)
df["fiber_to_sugar"]  = df["Fiber"] / (df["Sugar"] + 1e-3)
df["protein_density"] = df["Protein"] / (df["Calories"] + 1e-3)

NUM_COLS = [
    "Calories","Sugar","Fat","Protein","Sodium","Fiber","Vitamin C",
    "QuantityGrams","fiber_to_sugar","protein_density"
]
CAT_COLS = ["Allergy"]

preprocessor = joblib.load("preprocessor_hyper_pr.pkl")
X_all = preprocessor.transform(df[NUM_COLS + CAT_COLS])


# ——————————————
# 3. LOAD ENSEMBLE MODELS + THRESHOLDS
# ——————————————

ensembles = {}
for lbl in df["Label"].unique():
    ensembles[lbl] = joblib.load(f"ensemble_{lbl}.pkl")


# ——————————————
# 4. CATEGORY MAPPING & FILTERS
# ——————————————

def map_categories(profile):
    cats = []
    if profile.get("high_bp"):     cats.append("heartKidneySafe")
    if profile.get("weight_loss"): cats.append("metabolicHealth")
    if profile.get("pregnant"):    cats.append("immunityPregnancySafe")
    if profile.get("child"):       cats.append("childFamilySafe")
    if profile.get("diet") in ("vegetarian","vegan"):
                                    cats.append("plantBasedDiet")
    if profile.get("allergy") in ("dairy","gluten","both"):
                                    cats.append("digestiveBoneSupport")
    return list(dict.fromkeys(cats))


def get_filters(extra):
    flt = []
    flt.append((
        "rank_by",
        "protein_density" if extra.get("activity") in ("moderate","high")
                         else "fiber_to_sugar"
    ))
    if extra.get("spicy") == "hot":
        flt.append(("exclude_cat", "childFamilySafe"))
    if extra.get("macro") == "low_sugar":
        flt.append(("max_sugar", 5))
    if extra.get("cook_time") == "under_15":
        flt.append(("exclude_kw", ["Bhaja","Roast","Fry"]))
    if extra.get("budget"):
        flt.append(("exclude_kw", ["Hilsa","Shrimp","Duck","Beef"]))
    return flt


def apply_filters(df_temp, flt, cats):
    d = df_temp.copy()
    for t, arg in flt:
        if t == "max_sugar":
            d = d[d["Sugar"] <= arg]
        if t == "exclude_kw":
            pat = "|".join(arg)
            d = d[~d["Food"].str.contains(pat)]
        if t == "exclude_cat" and arg in cats:
            cats.remove(arg)
    return d, cats


# ——————————————
# 5. SUGGESTION ENGINE
# ——————————————

def get_suggestions(cats, top_n, flt=None):
    used, final = set(), []
    for cat in cats:
        ens = ensembles[cat]
        thr = ens["threshold"]

        probas = [
            m.predict_proba(X_all)[:,1]
            for key,m in ens.items() if key.endswith("_model")
        ]
        probs = np.vstack(probas).mean(axis=0)

        temp = pd.DataFrame({
            "Food": df["Food"],
            "prob": probs,
            "Sugar": df["Sugar"],
            "protein_density": df["protein_density"],
            "fiber_to_sugar": df["fiber_to_sugar"]
        }).drop_duplicates("Food")

        cats_copy = cats[:]
        if flt:
            temp, cats_copy = apply_filters(temp, flt, cats_copy)
            rk = next((v for k,v in flt if k=="rank_by"), "prob")
        else:
            rk = "prob"

        temp = temp.sort_values(rk, ascending=False)
        candidates = temp[temp["prob"] >= thr]
        if len(candidates) < top_n:
            candidates = temp

        for f in candidates["Food"]:
            if f not in used:
                final.append(f)
                used.add(f)
            if len(final) >= top_n:
                return final
    return final


# ——————————————
# 6. JSON API ENDPOINT
# ——————————————

@app.route("/recommend", methods=["POST"])
def recommend():
    data      = request.get_json()
    basic     = data.get("basic_profile", {})
    main_goal = data.get("main_goal")
    extra     = data.get("extra_profile")
    top_n     = max(2, min(10, int(data.get("top_n", 5))))

    cats = map_categories(basic)
    if not cats:
        if main_goal in ensembles:
            cats = [main_goal]
        else:
            return jsonify({"error":"no categories detected"}), 400

    response = {"initial": get_suggestions(cats, top_n)}

    if extra:
        flt = get_filters(extra)
        response["refined"] = get_suggestions(cats, top_n, flt)

    return jsonify(response)


# ——————————————
# 7. RUN
# ——————————————

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

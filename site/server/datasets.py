import csv, io, hashlib, math
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error


def train_private_csv(csv_text, platform):
    if len(csv_text.encode()) > 5 * 1024 * 1024:
        raise ValueError("Dataset must be under 5 MB.")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    records = []
    for i, r in enumerate(reader):
        if i >= 5000:
            raise ValueError("Use at most 5,000 rows per private dataset.")
        r = {k.strip().lower().replace(" ", "_"): v for k, v in r.items() if k}
        text = r.get("caption") or r.get("title") or r.get("text")
        den = (
            r.get("impressions")
            if platform == "Instagram"
            else r.get("views") or r.get("view_count")
        )
        if not text or not den:
            continue
        try:
            exposure = float(den)
            interactions = sum(
                float(r.get(k, "0") or "0")
                for k in (
                    ["likes", "comments", "shares", "saves"]
                    if platform == "Instagram"
                    else ["likes", "comments"]
                )
            )
            if r.get("comment_count") and not r.get("comments"):
                interactions += float(r["comment_count"])
        except ValueError:
            continue
        if not math.isfinite(exposure) or not math.isfinite(interactions):
            continue
        if not 0 < exposure or interactions < 0:
            continue
        rate = interactions / exposure * 100
        if rate > 100:
            continue
        records.append(
            {
                "text": text[:5000],
                "rate": rate,
                "group": r.get("channel_id")
                or hashlib.sha256(text.strip().lower().encode()).hexdigest(),
                "title": text[:100],
            }
        )
    if len(records) < 20 or len(set(r["group"] for r in records)) < 8:
        raise ValueError(
            "Add at least 20 valid records and 8 distinct captions or channels. Required: caption/title/text, impressions (Instagram) or views (YouTube), and likes/comments."
        )
    texts = [r["text"] for r in records]
    groups = [r["group"] for r in records]
    rates = np.array([r["rate"] for r in records])
    labels = np.log1p(rates)
    train, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(
            texts, labels, groups
        )
    )

    def vectorizer():
        return TfidfVectorizer(
            max_features=12000, ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )

    vector = vectorizer()
    matrix = vector.fit_transform([texts[i] for i in train])
    reg = Ridge(alpha=8).fit(matrix, labels[train])
    pred = np.maximum(
        0, np.expm1(reg.predict(vector.transform([texts[i] for i in test])))
    )
    mae = float(mean_absolute_error(rates[test], pred))
    baseline = float(
        mean_absolute_error(rates[test], np.full(len(test), np.median(rates[train])))
    )
    vector = vectorizer()
    matrix = vector.fit_transform(texts)
    reg = Ridge(alpha=8).fit(matrix, labels)
    info = {
        "platform": platform,
        "rows": len(records),
        "testRows": len(test),
        "testGroups": len(set(groups[i] for i in test)),
        "holdoutMAE": round(mae, 3),
        "baselineMAE": round(baseline, 3),
        "beatsBaseline": mae < baseline * 0.98,
        "medianRate": round(float(np.median(rates)), 3),
        "rateDefinition": (
            "interactions / impressions"
            if platform == "Instagram"
            else "(likes + comments) / views"
        ),
        "label": "Your private uploaded dataset",
        "method": "Private TF-IDF + ridge regression; grouped holdout; similarity retrieval",
        "limitations": "User-supplied observational data. Quality, permission and relevance are the uploader’s responsibility. No causation or future performance is guaranteed.",
    }
    return {
        "vector": vector,
        "reg": reg,
        "matrix": matrix,
        "rows": records,
        "info": info,
    }

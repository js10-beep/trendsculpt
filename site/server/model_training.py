"""Train on content features; post-publication metrics are targets only."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit


def train_text_reference(records, info, min_df=2, max_features=16000, temporal=False):
    texts = [r["text"] for r in records]
    rates = np.array([r["rate"] for r in records])
    groups = [r["group"] for r in records]
    ceiling = info.get("ceiling", 100)

    def vectorizer():
        return TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            min_df=min_df,
        )

    def evaluate(train, test):
        vector = vectorizer()
        matrix = vector.fit_transform([texts[i] for i in train])
        reg = Ridge(alpha=8).fit(matrix, np.log1p(rates[train]))
        pred = np.clip(
            np.expm1(reg.predict(vector.transform([texts[i] for i in test]))),
            0,
            ceiling,
        )
        error = float(mean_absolute_error(rates[test], pred))
        baseline = float(
            mean_absolute_error(
                rates[test], np.full(len(test), np.median(rates[train]))
            )
        )
        return {
            "trainRows": len(train),
            "testRows": len(test),
            "testGroups": len(set(groups[i] for i in test)),
            "holdoutMAE": round(error, 3),
            "baselineMAE": round(baseline, 3),
            "beatsBaseline": error < baseline * 0.98,
        }

    train, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(
            texts, rates, groups
        )
    )
    validation = evaluate(train, test)
    info = {
        **info,
        **validation,
        "rows": len(records),
        "medianRate": round(float(np.median(rates)), 3),
        "metricUnit": "percentage points",
        "validationSplit": "Grouped by channel or content identity",
        "featureInputs": "Caption/title/tags or supplied transcript only; outcome metrics are labels",
    }
    if temporal:
        train = np.array(
            [i for i, r in enumerate(records) if r["published_at"] < "2024-01-01"]
        )
        known = set(groups[i] for i in train)
        test = np.array(
            [
                i
                for i, r in enumerate(records)
                if r["published_at"] >= "2024-01-01" and groups[i] not in known
            ]
        )
        chronological = evaluate(train, test)
        info["temporalValidation"] = {
            **chronological,
            "cutoff": "2024-01-01",
            "definition": "Later-published videos from channels absent before the cutoff",
        }
        info["beatsBaseline"] = info["beatsBaseline"] and chronological["beatsBaseline"]
    vector = vectorizer()
    matrix = vector.fit_transform(texts)
    reg = Ridge(alpha=8).fit(matrix, np.log1p(rates))
    return {
        "vector": vector,
        "reg": reg,
        "matrix": matrix,
        "rows": records,
        "info": info,
    }

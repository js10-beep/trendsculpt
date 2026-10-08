"""Download checksum-pinned public observations and train reproducible local models."""

import csv, hashlib, io, json, pathlib, urllib.request, sys
import numpy as np, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / ".data"
SOURCE = DATA / "sources"
SOURCE.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ROOT / "server/source-manifest.json").read_text())
rows = {"Instagram": [], "YouTube": []}
seen = set()
for entry in manifest:
    path = SOURCE / entry["file"]
    if not path.exists():
        with urllib.request.urlopen(entry["source"], timeout=45) as response:
            raw = response.read()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise RuntimeError("Source integrity mismatch: " + entry["file"])
        path.write_bytes(raw)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise RuntimeError("Source integrity mismatch: " + entry["file"])
    for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))):
        if entry["platform"] == "Instagram":
            text = (r["Caption"] + " " + r["Hashtags"]).strip()
            den = float(r["Impressions"])
            rate = (
                sum(float(r[k]) for k in ["Likes", "Comments", "Shares", "Saves"])
                / max(den, 1)
                * 100
            )
            group = r["Caption"].strip().lower()
            platform = "Instagram"
        else:
            if r["video_id"] in seen:
                continue
            seen.add(r["video_id"])
            text = r["title"] + " " + r["tags"].replace("|", " ")
            den = float(r["view_count"])
            rate = (float(r["likes"]) + float(r["comment_count"])) / max(den, 1) * 100
            group = r["channelId"]
            platform = "YouTube"
        if den <= 0 or rate > 100:
            continue
        rows[platform].append(
            {
                "text": text,
                "rate": rate,
                "group": group,
                "title": r.get("title", r.get("Caption", "")).split("\n")[0][:100],
            }
        )
models = {}
summary = []
for platform, observations in rows.items():
    texts = [r["text"] for r in observations]
    y = np.log1p([r["rate"] for r in observations])
    groups = [r["group"] for r in observations]
    train, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(
            texts, y, groups
        )
    )
    vector = TfidfVectorizer(
        max_features=12000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=2,
    )
    x = vector.fit_transform([texts[i] for i in train])
    reg = Ridge(alpha=8)
    reg.fit(x, y[train])
    prediction = np.maximum(
        0, np.expm1(reg.predict(vector.transform([texts[i] for i in test])))
    )
    actual = np.expm1(y[test])
    mae = float(mean_absolute_error(actual, prediction))
    baseline = float(
        mean_absolute_error(actual, np.full(len(test), np.median(np.expm1(y[train]))))
    )
    vector = TfidfVectorizer(
        max_features=12000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=2,
    )
    matrix = vector.fit_transform(texts)
    reg = Ridge(alpha=8).fit(matrix, y)
    info = {
        "platform": platform,
        "rows": len(texts),
        "testRows": len(test),
        "testGroups": len(set(groups[i] for i in test)),
        "holdoutMAE": round(mae, 3),
        "baselineMAE": round(baseline, 3),
        "beatsBaseline": mae < baseline * 0.98,
        "medianRate": round(float(np.median(np.expm1(y))), 3),
        "rateDefinition": (
            "(likes + comments + shares + saves) / impressions"
            if platform == "Instagram"
            else "(likes + comments) / views"
        ),
        "label": (
            "Instagram sample"
            if platform == "Instagram"
            else "2018 YouTube trending archive; not a Shorts dataset"
        ),
        "method": "TF-IDF + ridge regression; grouped 25% holdout; similarity retrieval",
        "limitations": "Small, biased observational sample. Correlation is not causation. Historical mixed-format YouTube observations do not validate modern Shorts predictions.",
    }
    models[platform] = {
        "vector": vector,
        "reg": reg,
        "matrix": matrix,
        "rows": observations,
        "info": info,
    }
    summary.append(info)
    print(platform, json.dumps(info))
MODEL_DIR = ROOT / ".models"
MODEL_DIR.mkdir(exist_ok=True)
joblib.dump(models, MODEL_DIR / "models.joblib", compress=3)
if "--skip-metadata" not in sys.argv and (ROOT / "src").exists():
    (ROOT / "src/model-data.json").write_text(
        json.dumps(
            {
                "models": summary,
                "sources": manifest,
                "trainedAt": "2026-10-08",
                "provider": "Local scikit-learn models",
            },
            indent=2,
        )
    )
print("Local models prepared with verified source checksums.")

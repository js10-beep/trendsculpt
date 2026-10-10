"""Offline reproducible training. Deployment loads checksum-verified artifacts."""

import csv, gzip, hashlib, io, json, pathlib, sys
import joblib, numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.model_training import train_text_reference

manifest = json.loads((ROOT / "server/source-manifest.json").read_text())
records = {}
for source in manifest:
    raw = (ROOT / source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise RuntimeError("Source checksum mismatch: " + source["file"])
    records[source["platform"]] = list(
        csv.DictReader(io.StringIO(gzip.decompress(raw).decode("utf-8-sig")))
    )

models = {}
for platform in ("Instagram", "YouTube"):
    source = next(s for s in manifest if s["platform"] == platform)
    rows = []
    for r in records[platform]:
        if platform == "Instagram":
            text = (r["Caption"] + " " + r["Hashtags"]).strip()
            exposure = float(r["Impressions"])
            rate = (
                sum(float(r[k]) for k in ["Likes", "Comments", "Shares", "Saves"])
                / exposure
                * 100
            )
            group, title = (
                r["Caption"].strip().lower(),
                r["Caption"].split("\n")[0][:100],
            )
        else:
            text = r["title"] + " " + r["tags"].replace("|", " ")
            exposure = float(r["views"])
            rate = (float(r["likes"]) + float(r["comments"])) / exposure * 100
            group, title = r["channel_id"], r["title"][:100]
        rows.append(
            {
                "text": text,
                "rate": rate,
                "group": group,
                "title": title,
                "published_at": r.get("published_at", ""),
                "video_id": r.get("video_id", ""),
            }
        )
    info = {
        "platform": platform,
        "label": source["label"],
        "source": source["source"],
        "method": "TF-IDF + ridge regression; grouped 25% holdout; similarity retrieval",
        "rateDefinition": (
            "(likes + comments + shares + saves) / impressions"
            if platform == "Instagram"
            else "(likes + comments) / views"
        ),
        "limitations": (
            "Small, biased observational Instagram sample; no causal or audience-wide guarantee."
            if platform == "Instagram"
            else "2020–2024 India/US trending selection, sampled and deduplicated. Not representative of all videos. No duration, verified Shorts labels, transcript or retention ground truth. The later unseen-channel test is only 281 records; transfer to a new audience remains uncertain."
        ),
    }
    models[platform] = train_text_reference(
        rows,
        info,
        max_features=12000 if platform == "Instagram" else 16000,
        temporal=platform == "YouTube",
    )
    print(platform, json.dumps(models[platform]["info"]), flush=True)

rows = records["Kuaishou reference"]
x = np.array([[np.log1p(float(r["duration_seconds"]))] for r in rows])
y = np.array([float(r["mean_watch_fraction"]) * 100 for r in rows])
weights = np.array([int(r["exposures"]) for r in rows])
train, test = next(
    GroupShuffleSplit(test_size=0.25, random_state=42).split(
        x, y, [r["video_group"] for r in rows]
    )
)


def watch_model():
    return make_pipeline(
        PolynomialFeatures(2, include_bias=False), StandardScaler(), Ridge(alpha=8)
    )


model = watch_model().fit(x[train], y[train], ridge__sample_weight=weights[train])
pred = np.clip(model.predict(x[test]), 0, 300)
mae = float(mean_absolute_error(y[test], pred))
baseline = float(mean_absolute_error(y[test], np.full(len(test), np.median(y[train]))))
info = {
    "platform": "Kuaishou reference",
    "label": "KuaiRand-1K random-exposure watch reference",
    "rows": len(rows),
    "testRows": len(test),
    "testGroups": len(test),
    "interactions": int(weights.sum()),
    "holdoutMAE": round(mae, 3),
    "baselineMAE": round(baseline, 3),
    "beatsBaseline": mae < baseline * 0.98,
    "metricUnit": "percentage points of video length",
    "medianRate": round(float(np.median(y)), 3),
    "rateDefinition": "Mean watched percentage per random exposure, capped at 300% per exposure",
    "method": "Duration-only polynomial ridge regression; video-separated 25% holdout; exposure-weighted training",
    "source": manifest[2]["source"],
    "license": "CC BY-SA 4.0",
    "limitations": "Kuaishou random-exposure sample from 1,000 users, 5–180 second videos, at least 3 exposures per video. Includes skips and replays. Duration-only reference: does not examine video meaning, prove shorter is better, or predict Instagram/YouTube retention. Completion predictor failed its baseline and was excluded.",
}
models["Kuaishou reference"] = {
    "reg": watch_model().fit(x, y, ridge__sample_weight=weights),
    "rows": rows,
    "info": info,
}
print("Kuaishou reference", json.dumps(info), flush=True)
assets = ROOT / "server/reference-data"
artifact = assets / "models.joblib"
joblib.dump(models, artifact, compress=3)
metadata = {
    "artifact": "server/reference-data/models.joblib",
    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    "models": [m["info"] for m in models.values()],
    "sources": manifest,
    "version": "public-2020-2024-kuairand-v1",
    "training": "Offline; no full datasets downloaded or models trained on Render",
}
(assets / "artifact-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
(ROOT / "src/model-data.json").write_text(json.dumps(metadata, indent=2) + "\n")
print("Artifact bytes:", artifact.stat().st_size, flush=True)

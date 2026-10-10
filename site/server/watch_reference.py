"""Separate cross-platform duration references from account-private content evidence."""

import numpy as np


def public_watch_reference(media, platform, models):
    length = media.get("duration") if media else None
    if (
        platform not in {"Instagram", "YouTube Shorts", "TikTok"}
        or not length
        or not 5 <= length <= 180
    ):
        return None
    model = models["Kuaishou reference"]
    boundaries = [(5, 15), (15, 30), (30, 60), (60, 90), (90, 180)]
    low, high = next(
        (a, b)
        for a, b in boundaries
        if (a <= length <= b if a == 5 else a < length <= b)
    )
    peers = [
        r
        for r in model["rows"]
        if (
            low <= float(r["duration_seconds"]) <= high
            if low == 5
            else low < float(r["duration_seconds"]) <= high
        )
    ]
    exposures = sum(int(r["exposures"]) for r in peers)
    estimate = float(np.clip(model["reg"].predict([[np.log1p(length)]])[0], 0, 300))
    average = (
        sum(float(r["mean_watch_fraction"]) * int(r["exposures"]) for r in peers)
        / exposures
        * 100
    )
    return {
        "sourcePlatform": "Kuaishou",
        "label": model["info"]["label"],
        "measuredDuration": round(length, 2),
        "durationBand": [low, high],
        "referenceEstimate": round(estimate, 2),
        "observedWatchPercent": round(average, 2),
        "referenceVideos": len(peers),
        "referenceExposures": exposures,
        "modelUsedForScore": False,
        "validation": model["info"],
        "note": "Cross-platform context only. Includes skips and replays; each exposure is capped at 3× video length. No transcript/scene features or actual viewer retention are measured by this reference. It does not change your score.",
    }


def private_watch_evidence(text, model):
    child = model.get("watchModel") if model else None
    if not child or not text:
        return None
    query = child["vector"].transform([text[:16000]])
    similarities = (child["matrix"] @ query.T).toarray().ravel()
    indices = np.argsort(similarities)[::-1][:5]
    similarity = float(similarities[indices[0]])
    relevant = similarity >= 0.15 and child["info"]["beatsBaseline"]
    estimate = (
        float(np.clip(np.expm1(child["reg"].predict(query)[0]), 0, 300))
        if relevant
        else None
    )
    return {
        "datasetRows": child["info"]["rows"],
        "historicalEstimate": round(estimate, 2) if estimate is not None else None,
        "similarity": round(similarity, 3),
        "usableReference": relevant,
        "validation": child["info"],
        "modelUsedForScore": False,
        "neighbors": [
            {
                "title": child["rows"][int(i)]["title"],
                "observedWatchPercent": round(child["rows"][int(i)]["rate"], 2),
            }
            for i in indices
            if similarities[i] >= 0.06
        ][:3],
        "note": "Account-private content comparison. Watched percentage is an uploaded historical outcome, not measured retention for this new video. Replays can exceed 100%. Estimates are hidden when holdout validation or text relevance is insufficient.",
    }

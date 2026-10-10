"""Bounded private CSV training, including optional creator watch-time targets."""

import csv, io, hashlib, math, re
from .model_training import train_text_reference

ALIASES = {
    "video_title": "title",
    "video_publish_time": "published_at",
    "comment_count": "comments",
    "view_count": "views",
    "average_percentage_viewed_%": "average_percentage_viewed",
    "average_view_duration": "average_view_duration_seconds",
    "avg_view_duration_seconds": "average_view_duration_seconds",
    "watch_time_hours": "watch_time_hours",
    "video_duration": "duration_seconds",
    "duration": "duration_seconds",
    "channelid": "channel_id",
}


def key(value):
    normalized = re.sub(r"[^a-z0-9%]+", "_", value.strip().lower()).strip("_")
    return ALIASES.get(normalized, normalized)


def number(value):
    n = float((value or "0").replace(",", ""))
    if not math.isfinite(n) or n < 0:
        raise ValueError("Metrics must be finite and nonnegative.")
    return n


def duration(value):
    if ":" in value:
        return sum(number(p) * 60**i for i, p in enumerate(reversed(value.split(":"))))
    return number(value)


def train_private_csv(csv_text, platform):
    if len(csv_text.encode()) > 5 * 1024 * 1024:
        raise ValueError("Dataset must be under 5 MB.")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    headers = {key(h) for h in reader.fieldnames or []}
    required = "impressions" if platform == "Instagram" else "views"
    interaction_headers = (
        {"likes", "comments", "shares", "saves"}
        if platform == "Instagram"
        else {"likes", "comments"}
    )
    if required not in headers or not (interaction_headers & headers):
        raise ValueError(
            f"Include {required} and at least one measured interaction column: likes/comments/shares/saves."
        )
    records = []
    seen = set()
    duplicates = 0
    skipped = 0
    watch_skipped = 0
    for i, source in enumerate(reader):
        if i >= 5000:
            raise ValueError("Use at most 5,000 rows per private dataset.")
        r = {
            key(k): (v or "").strip()
            for k, v in source.items()
            if k and isinstance(v, str)
        }
        base = r.get("caption") or r.get("title") or r.get("text") or ""
        transcript = r.get("transcript", "")
        text = (base + "\n" + transcript).strip()[:16000]
        if not text or not r.get(required):
            skipped += 1
            continue
        try:
            exposure = number(r[required])
            interactions = sum(
                number(r.get(k))
                for k in (
                    ["likes", "comments", "shares", "saves"]
                    if platform == "Instagram"
                    else ["likes", "comments"]
                )
            )
        except ValueError:
            skipped += 1
            continue
        if exposure <= 0 or interactions > exposure:
            skipped += 1
            continue
        identity = (
            r.get("video_id")
            or r.get("post_id")
            or hashlib.sha256(
                (text.lower() + str(exposure) + str(interactions)).encode()
            ).hexdigest()
        )
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        record = {
            "text": text,
            "rate": interactions / exposure * 100,
            "group": hashlib.sha256(text.lower().encode()).hexdigest(),
            "channel": r.get("channel_id", ""),
            "title": (base or transcript)[:100],
            "watch": None,
        }
        try:
            watched = None
            if r.get("average_percentage_viewed"):
                watched = number(r["average_percentage_viewed"])
            elif r.get("duration_seconds"):
                length = duration(r["duration_seconds"])
                average = (
                    duration(r["average_view_duration_seconds"])
                    if r.get("average_view_duration_seconds")
                    else (
                        number(r["watch_time_hours"]) * 3600 / exposure
                        if r.get("watch_time_hours")
                        else None
                    )
                )
                if length > 0 and average is not None:
                    watched = average / length * 100
            if watched is not None:
                if watched > 300:
                    raise ValueError("Watch target outside 0–300%.")
                record["watch"] = watched
        except ValueError:
            watch_skipped += 1
        records.append(record)
    channels = {r["channel"] for r in records if r["channel"]}
    channel_split = len(channels) >= 8 and all(r["channel"] for r in records)
    if channel_split:
        for r in records:
            r["group"] = r["channel"]
    if len(records) < 20 or len({r["group"] for r in records}) < 8:
        raise ValueError(
            "Add at least 20 valid records and 8 distinct captions or channels. Duplicate post/video IDs are counted once."
        )
    info = {
        "platform": platform,
        "label": "Your private uploaded dataset",
        "rateDefinition": (
            "(likes + comments + shares + saves) / impressions"
            if platform == "Instagram"
            else "(likes + comments) / views"
        ),
        "method": "Private TF-IDF + ridge regression; grouped holdout; similarity retrieval",
        "limitations": "Account-private observational data. Only content is used as a feature; outcomes are labels. No causal or future-performance guarantee.",
        "duplicatesSkipped": duplicates,
        "invalidRowsSkipped": skipped,
        "watchRowsSkipped": watch_skipped,
        "hasTranscripts": "transcript" in headers,
        "grouping": (
            "Channel-separated"
            if channel_split
            else "Content-separated within the supplied audience"
        ),
    }
    model = train_text_reference(records, info, min_df=1, max_features=12000)
    watch = [{**r, "rate": r["watch"]} for r in records if r["watch"] is not None]
    if len(watch) >= 20 and len({r["group"] for r in watch}) >= 8:
        child = train_text_reference(
            watch,
            {
                **info,
                "label": "Your private creator watch-time observations",
                "rateDefinition": "Average watched percentage of video length (0–300%; replays can exceed 100%)",
                "ceiling": 300,
            },
            min_df=1,
            max_features=12000,
        )
        model["watchModel"] = child
        model["info"]["watchValidation"] = child["info"]
    else:
        model["info"]["watchValidation"] = None
    model["info"]["watchRows"] = len(watch)
    return model

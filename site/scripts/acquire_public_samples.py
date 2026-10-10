"""Offline audit/reproduction; writes only to an explicit temporary cache."""

import csv, io, zipfile, pathlib, collections, json, hashlib, gzip, datetime
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--cache", default="/tmp/trendsculpt-public-datasets")
args = parser.parse_args()
root = pathlib.Path(args.cache)
manifest = json.loads(
    (
        pathlib.Path(__file__).resolve().parents[1] / "server/source-manifest.json"
    ).read_text()
)
for entry in manifest:
    for upstream in entry.get("upstreamFiles", []):
        path = root / upstream["file"]
        if not path.exists():
            import urllib.request

            partial = path.with_suffix(path.suffix + ".part")
            partial.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(
                upstream["url"], timeout=45
            ) as response, partial.open("wb") as target:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    target.write(chunk)
            partial.replace(path)
        h = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != upstream["sha256"]:
            raise RuntimeError("Upstream checksum mismatch: " + upstream["file"])
seen = {}
counts = {}
invalid = 0
for region in ["us", "in"]:
    p = root / f"youtube-{region}-v1346.zip"
    with zipfile.ZipFile(p) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            print(region, "columns", reader.fieldnames, flush=True)
            n = 0
            for r in reader:
                n += 1
                try:
                    views = int(r["view_count"])
                    likes = int(r["likes"])
                    comments = int(r["comment_count"])
                    vid = r["video_id"]
                    day = r["trending_date"][:10]
                    if (
                        views < 1000
                        or min(likes, comments) < 0
                        or (likes + comments) > views
                        or r.get("comments_disabled") == "True"
                        or r.get("ratings_disabled") == "True"
                    ):
                        invalid += 1
                        continue
                    if not vid or not r["title"] or not r.get("channelId"):
                        invalid += 1
                        continue
                except (ValueError, KeyError):
                    invalid += 1
                    continue
                if vid in seen and (seen[vid]["observed_at"], seen[vid]["region"]) <= (
                    day,
                    region.upper(),
                ):
                    continue
                seen[vid] = {
                    "video_id": vid,
                    "title": r["title"][:250],
                    "tags": r.get("tags", "")[:700],
                    "channel_id": r["channelId"],
                    "published_at": r["publishedAt"][:10],
                    "observed_at": day,
                    "region": region.upper(),
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                }
    counts[region] = n
    print(region, "read", n, "global_unique", len(seen), flush=True)
rows = sorted(
    seen.values(), key=lambda r: hashlib.sha256(r["video_id"].encode()).hexdigest()
)[:30000]
rows.sort(key=lambda r: (r["published_at"], r["video_id"]))
with (root / "youtube-sample.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(
    "source counts",
    counts,
    "dedup",
    len(seen),
    "invalid",
    invalid,
    "sample",
    len(rows),
    "channels",
    len(set(r["channel_id"] for r in rows)),
    "published range",
    rows[0]["published_at"],
    rows[-1]["published_at"],
    flush=True,
)
print(
    "years", dict(collections.Counter(r["published_at"][:4] for r in rows)), flush=True
)
logs = list(csv.DictReader((root / "kuairand-random-1k.csv").open()))
items = collections.defaultdict(list)
for r in logs:
    d = float(r["duration_ms"]) / 1000
    p = float(r["play_time_ms"]) / 1000
    if not (0 < d <= 180 and p >= 0 and r["is_rand"] == "1"):
        continue
    items[r["video_id"]].append(
        {
            "duration": d,
            "fraction": min(3, p / d),
            "completed": int(p >= d),
            "liked": int(r["is_like"]),
            "commented": int(r["is_comment"]),
            "shared": int(r["is_forward"]),
            "played": int(r["is_click"]),
        }
    )
agg = []
for vid, v in items.items():
    if len(v) < 3:
        continue
    n = len(v)
    duration = sorted(r["duration"] for r in v)[n // 2]
    agg.append(
        {
            "video_group": hashlib.sha256(vid.encode()).hexdigest()[:20],
            "duration_seconds": duration,
            "exposures": n,
            "mean_watch_fraction": sum(r["fraction"] for r in v) / n,
            "completion_rate": sum(r["completed"] for r in v) / n,
            "like_rate": sum(r["liked"] for r in v) / n,
            "comment_rate": sum(r["commented"] for r in v) / n,
            "share_rate": sum(r["shared"] for r in v) / n,
        }
    )
agg.sort(key=lambda r: r["video_group"])
with (root / "kuairand-aggregated.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=list(agg[0]))
    w.writeheader()
    w.writerows(agg)
print(
    "KuaiRand aggregates",
    len(agg),
    "exposures",
    sum(r["exposures"] for r in agg),
    "duration minmax",
    min(r["duration_seconds"] for r in agg),
    max(r["duration_seconds"] for r in agg),
    flush=True,
)
(root / "audit.json").write_text(
    json.dumps(
        {
            "youtubeSourceRows": counts,
            "youtubeUnique": len(seen),
            "youtubeFiltered": invalid,
            "youtubeSample": len(rows),
            "kuairandInteractions": len(logs),
            "kuairandVideos": len(agg),
            "kuairandIncludedInteractions": sum(r["exposures"] for r in agg),
        },
        indent=2,
    )
)

for input_name, output_name in [
    ("youtube-sample.csv", "youtube-2020-2024.csv.gz"),
    ("kuairand-aggregated.csv", "kuairand-1k-aggregates.csv.gz"),
]:
    payload = gzip.compress((root / input_name).read_bytes(), mtime=0)
    expected = next(entry for entry in manifest if entry["file"] == output_name)
    if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
        raise RuntimeError(
            "Derived sample differs from pinned snapshot: " + output_name
        )
    (root / output_name).write_bytes(payload)
print("Reproduced derived snapshots and verified their recorded SHA-256 digests.")

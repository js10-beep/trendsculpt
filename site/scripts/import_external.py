"""Fetch permitted dataset/API observations into a CSV for private model import.
Uses normal TLS verification. Credentials come only from environment variables.
"""

import argparse, base64, csv, io, json, os, pathlib, re, sys, urllib.error, urllib.parse, urllib.request, zipfile


def download(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(100 * 1024 * 1024 + 1)
            if len(data) > 100 * 1024 * 1024:
                raise ValueError("Download exceeds the 100 MB import limit.")
            return data
    except urllib.error.HTTPError as error:
        raise ValueError(
            f"Service returned HTTP {error.code}. Check access, credentials, and network settings."
        ) from None
    except urllib.error.URLError:
        raise ValueError(
            "Network request failed. Check environment allowlists and service availability."
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="kind", required=True)
    kaggle = sub.add_parser("kaggle")
    kaggle.add_argument("dataset", help="owner/dataset")
    kaggle.add_argument("--file", help="CSV filename inside the archive")
    hf = sub.add_parser("huggingface")
    hf.add_argument("dataset", help="owner/dataset")
    hf.add_argument("file", help="CSV file path in the dataset repository")
    hf.add_argument("--revision", default="main")
    yt = sub.add_parser("youtube")
    yt.add_argument("--region", default="US")
    yt.add_argument("--pages", type=int, default=1)
    for p in [kaggle, hf, yt]:
        p.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    if args.kind in ["kaggle", "huggingface"] and not re.fullmatch(
        r"[\w.-]+/[\w.-]+", args.dataset
    ):
        raise ValueError("Use an owner/dataset identifier.")
    if args.kind == "kaggle":
        headers = {}
        username = os.getenv("KAGGLE_USERNAME")
        key = os.getenv("KAGGLE_KEY")
        if username and key:
            headers["Authorization"] = (
                "Basic " + base64.b64encode((username + ":" + key).encode()).decode()
            )
        raw = download(
            "https://www.kaggle.com/api/v1/datasets/download/" + args.dataset, headers
        )
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = [
                f for f in archive.infolist() if f.filename.lower().endswith(".csv")
            ]
            selected = (
                next((f for f in files if f.filename == args.file), None)
                if args.file
                else files[0] if len(files) == 1 else None
            )
            if not selected:
                raise ValueError(
                    "Specify --file for the CSV to import. Available CSVs: "
                    + ", ".join(f.filename for f in files[:30])
                )
            if selected.file_size > 100 * 1024 * 1024:
                raise ValueError("The selected CSV is too large.")
            output = archive.read(selected)
    elif args.kind == "huggingface":
        if ".." in pathlib.PurePosixPath(args.file).parts or args.file.startswith("/"):
            raise ValueError("Use a relative dataset CSV path.")
        if not args.file.lower().endswith(".csv"):
            raise ValueError("This importer supports CSV files.")
        headers = (
            {"Authorization": "Bearer " + os.environ["HF_TOKEN"]}
            if os.getenv("HF_TOKEN")
            else {}
        )
        output = download(
            "https://huggingface.co/datasets/"
            + args.dataset
            + "/resolve/"
            + urllib.parse.quote(args.revision, safe="")
            + "/"
            + urllib.parse.quote(args.file, safe="/"),
            headers,
        )
    else:
        key = os.getenv("YOUTUBE_API_KEY")
        if not key:
            raise ValueError(
                "Set YOUTUBE_API_KEY securely before using the YouTube Data API."
            )
        if not re.fullmatch("[A-Z]{2}", args.region) or not 1 <= args.pages <= 10:
            raise ValueError("Use a two-letter region and 1–10 pages.")
        rows = []
        token = None
        for page in range(args.pages):
            params = {
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "maxResults": 50,
                "regionCode": args.region,
                "key": key,
            }
            if token:
                params["pageToken"] = token
            result = json.loads(
                download(
                    "https://www.googleapis.com/youtube/v3/videos?"
                    + urllib.parse.urlencode(params)
                )
            )
            for item in result.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                rows.append(
                    {
                        "title": snippet["title"],
                        "views": stats.get("viewCount", 0),
                        "likes": stats.get("likeCount", 0),
                        "comments": stats.get("commentCount", 0),
                        "channel_id": snippet["channelId"],
                    }
                )
            token = result.get("nextPageToken")
            if not token:
                break
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=["title", "views", "likes", "comments", "channel_id"]
        )
        writer.writeheader()
        writer.writerows(rows)
        output = buffer.getvalue().encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError(
            "Output already exists. Choose another path to preserve existing data."
        )
    args.output.write_bytes(output)
    print(
        "CSV saved. Check its license, columns, and permission, then upload it in Data & models."
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

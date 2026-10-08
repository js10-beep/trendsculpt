"""Bounded local video sampling, frame OCR and audio measurements."""

import base64
import csv
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import numpy as np
from PIL import Image, ImageFilter


def inspect_frame(image):
    image = image.convert("RGB")
    width, height = image.size
    image.thumbnail((320, 320))
    gray = image.convert("L")
    pixels = np.asarray(gray, dtype=float)
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=float)
    return {
        "width": width,
        "height": height,
        "brightness": round(float(pixels.mean()), 1),
        "contrast": round(float(pixels.std()), 1),
        "edgeDetail": round(
            float(edges[1:-1, 1:-1].mean()) if min(edges.shape) > 2 else 0, 1
        ),
        "clippedPercent": round(
            float(((pixels < 12) | (pixels > 243)).mean() * 100), 1
        ),
        "fingerprint": np.asarray(gray.resize((32, 32)), dtype=float),
    }


def inspect_media(raw, mime, long_form=False, path=None):
    with tempfile.TemporaryDirectory(prefix="trendsculpt-video-") as directory:
        return _inspect(raw, mime, long_form, path, pathlib.Path(directory))


def _inspect(raw, mime, long_form, path, directory):
    frames, timeline, audio = [], [], []
    duration, has_audio = None, False
    deadline = time.monotonic() + (75 if long_form else 55)

    def run(args, cap=20):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError(
                "Video processing exceeded its time budget. Try a more compressed MP4 export or analyze the full transcript instead."
            )
        return subprocess.run(
            args, capture_output=True, check=True, timeout=max(0.1, min(cap, remaining))
        )

    if mime.startswith("image/"):
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 30_000_000:
                raise ValueError(
                    "Image dimensions are too large. Use an image under 30 megapixels."
                )
            frames = [inspect_frame(image)]
    else:
        if path is None:
            path = directory / "upload.mp4"
            path.write_bytes(raw)
        probe = run(
            [
                "ffprobe",
                "-protocol_whitelist",
                "file,pipe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
        meta = json.loads(probe.stdout)
        stream = next(
            (s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None
        )
        if not stream:
            raise ValueError("This video has no readable video stream.")
        duration = float(meta.get("format", {}).get("duration", 0))
        maximum = 3600 if long_form else 180
        if not 0 < duration <= maximum:
            raise ValueError(
                "Long-form video must be 60 minutes or less."
                if long_form
                else "Video must be 3 minutes or less. Select YouTube (long-form) for longer videos."
            )
        width, height = int(stream["width"]), int(stream["height"])
        if width * height > 9_000_000:
            raise ValueError("Use an export of 4K or lower for video analysis.")
        has_audio = any(s.get("codec_type") == "audio" for s in meta.get("streams", []))
        points = [
            0,
            min(0.5, duration / 3),
            min(1.5, duration * 0.5),
            min(3, duration * 0.7),
            min(6, duration * 0.85),
        ]
        points += [
            duration * f
            for f in (
                [0.2, 0.4, 0.6, 0.8, 0.95] if long_form else [0.25, 0.5, 0.75, 0.95]
            )
        ]
        if long_form:
            points += [min(15, duration * 0.3), min(30, duration * 0.5)]
        points.append(max(0, duration - 0.1))
        timestamps = sorted({round(min(t, max(0, duration - 0.05)), 3) for t in points})
        for index, point in enumerate(timestamps):
            output = run(
                [
                    "ffmpeg",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-v",
                    "error",
                    "-ss",
                    str(point),
                    "-threads",
                    "1",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:640:force_original_aspect_ratio=decrease",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "png",
                    "-threads",
                    "1",
                    "pipe:1",
                ]
            )
            if not output.stdout:
                continue
            with Image.open(io.BytesIO(output.stdout)) as image:
                measurement = inspect_frame(image)
                measurement.update(width=width, height=height)
                frames.append(measurement)
                preview = image.convert("RGB")
                preview.thumbnail((320, 240))
                buffer = io.BytesIO()
                preview.save(buffer, "JPEG", quality=65)
                entry = {
                    k: measurement[k]
                    for k in ["brightness", "contrast", "clippedPercent"]
                }
                entry.update(
                    timestamp=point,
                    thumbnail="data:image/jpeg;base64,"
                    + base64.b64encode(buffer.getvalue()).decode(),
                    overlayText="",
                    ocrStatus=(
                        "not sampled" if shutil.which("tesseract") else "unavailable"
                    ),
                )
            # OCR selected frames only; English text, independently inspectable in the preview.
            if (
                shutil.which("tesseract")
                and index in {0, 1, 3, len(timestamps) // 2, len(timestamps) - 2}
                and deadline - time.monotonic() > 8
            ):
                try:
                    result = subprocess.run(
                        [
                            "tesseract",
                            "stdin",
                            "stdout",
                            "-l",
                            "eng",
                            "--psm",
                            "11",
                            "tsv",
                        ],
                        input=output.stdout,
                        capture_output=True,
                        check=True,
                        timeout=4,
                        env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                    )
                    rows = csv.DictReader(
                        io.StringIO(result.stdout.decode(errors="replace")),
                        delimiter="\t",
                    )
                    words = [
                        r["text"]
                        for r in rows
                        if float(r.get("conf", -1)) >= 60 and r.get("text", "").strip()
                    ]
                    entry["overlayText"] = " ".join(words)[:500]
                    entry["ocrStatus"] = "completed"
                except (subprocess.SubprocessError, ValueError, KeyError):
                    entry["ocrStatus"] = "not completed"
            timeline.append(entry)
        if not frames:
            raise ValueError("This video has no readable frames.")
        if has_audio:
            for point in sorted(
                {0, round(duration * 0.5, 2), round(max(0, duration - 5), 2)}
            ):
                if deadline - time.monotonic() < 5:
                    break
                try:
                    result = run(
                        [
                            "ffmpeg",
                            "-protocol_whitelist",
                            "file,pipe",
                            "-hide_banner",
                            "-ss",
                            str(point),
                            "-threads",
                            "1",
                            "-i",
                            str(path),
                            "-t",
                            str(min(5, duration - point)),
                            "-vn",
                            "-af",
                            "volumedetect",
                            "-f",
                            "null",
                            "-",
                        ],
                        cap=8,
                    )
                    values = result.stderr.decode(errors="replace")
                    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", values)
                    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", values)
                    audio.append(
                        {
                            "timestamp": point,
                            "duration": min(5, duration - point),
                            "meanDb": float(mean[1]) if mean else None,
                            "peakDb": float(peak[1]) if peak else None,
                        }
                    )
                except subprocess.SubprocessError:
                    pass
    changes = [
        float(np.abs(a["fingerprint"] - b["fingerprint"]).mean())
        for a, b in zip(frames, frames[1:])
    ]
    result = {
        k: frames[0][k]
        for k in [
            "width",
            "height",
            "brightness",
            "contrast",
            "edgeDetail",
            "clippedPercent",
        ]
    }
    result.update(
        framesSampled=len(frames),
        duration=duration,
        hasAudio=has_audio,
        meanFrameChange=round(float(np.mean(changes)), 1) if changes else 0,
        timeline=timeline,
        audioWindows=audio,
        ocrAvailable=bool(shutil.which("tesseract")),
        method=(
            "Pillow pixel measurements"
            if mime.startswith("image/")
            else "FFmpeg timeline samples + English frame OCR + sampled audio levels"
        ),
        limits="Sparse samples measure pixels and audio levels. OCR estimates English on-screen words. Spoken words use your supplied transcript; visual subjects and audience retention are not inferred.",
    )
    return result

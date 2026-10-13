"""Turn browser-reported object detections into inspectable, bounded edit ideas.

The server validates labels, geometry and membership of real sample timestamps.
It does not independently attest a client's model execution or infer actions.
"""

import copy
import json
import pathlib
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .content_review import parse_transcript, timestamp

MODEL = "coco-ssdlite-mobilenet-v2-v1"
CLASSES = set(
    json.loads(pathlib.Path(__file__).with_name("visual-classes.json").read_text())
)
SOURCE = "Browser visual recognition"
NOTE = (
    "COCO-SSD / SSDLite MobileNet V2 ran on sampled previews in your browser. "
    "Detections are model estimates, not verified facts; confidence is a model score. "
    "Only 80 common object classes are supported. A missed detection does not prove absence. "
    "Small previews and sparse frames can miss details. Actions, identities, emotions, "
    "story quality and actual engagement are not inferred. Visual suggestions are edit "
    "experiments and do not change the engagement score."
)


class VisualObject(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    label: str = Field(max_length=30)
    confidence: float = Field(ge=0.6, le=1)
    box: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_object(self):
        x, y, w, h = self.box
        if self.label not in CLASSES or not (
            0 <= x < 1
            and 0 <= y < 1
            and 0 < w <= 1
            and 0 < h <= 1
            and x + w <= 1.00001
            and y + h <= 1.00001
        ):
            raise ValueError("Unsupported label or invalid object geometry.")
        return self


class VisualFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    timestamp: float = Field(ge=0, le=3600)
    objects: list[VisualObject] = Field(max_length=8)


class VisualPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    frames: list[VisualFrame] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def valid_model(self):
        if self.model != MODEL:
            raise ValueError("Unsupported visual model version.")
        return self


def object_mentioned(label, text):
    # Whole-word matches only. No mapping a frying pan to a detected bowl, or
    # treating a detected person as proof of an exercise, emotion or identity.
    return bool(re.search(r"\b" + re.escape(label) + r"(?:s|es)?\b", text, re.I))


def attach_visual_review(report, payload):
    payload = VisualPayload.model_validate(payload).model_dump()
    timeline = (report.get("mediaAnalysis") or {}).get("timeline", [])
    times = {f["timestamp"] for f in timeline}
    frames = sorted(payload["frames"], key=lambda f: f["timestamp"])
    if (
        not times
        or len({f["timestamp"] for f in frames}) != len(frames)
        or any(f["timestamp"] not in times for f in frames)
    ):
        raise ValueError("Visual detections must match distinct frames in this report.")
    report = copy.deepcopy(report)
    segments = (
        parse_transcript(report.get("transcript", ""))[0]
        if report.get("transcript")
        else []
    )
    context = " ".join(report.get(k, "") or "" for k in ["videoTitle", "topic", "text"])
    recs = []

    def passage_at(t):
        # Only match a timed cue that covers the sample. Untimed text has no
        # alleged alignment; a pasted caption isn't called spoken dialogue.
        for i, passage in enumerate(segments):
            start = passage["start"]
            if start is None:
                continue
            end = passage["end"]
            if end is None:
                following = segments[i + 1]["start"] if i + 1 < len(segments) else None
                end = min(start + 8, following) if following is not None else start + 8
            if start <= t < end:
                return passage["text"]
        return ""

    def add(title, reason, suggestion, frame, quote=""):
        if len(recs) < 3:
            recs.append(
                {
                    "title": title,
                    "reason": reason,
                    "suggestion": suggestion,
                    "timestamp": frame["timestamp"],
                    "quote": quote[:220] or None,
                    "source": SOURCE,
                    "priority": "Medium",
                }
            )

    labels = sorted({o["label"] for f in frames for o in f["objects"]})
    candidates = []
    for frame in frames:
        quote = passage_at(frame["timestamp"])
        for obj in frame["objects"]:
            spoken = object_mentioned(obj["label"], quote)
            relevant = spoken or object_mentioned(obj["label"], context)
            candidates.append((not relevant, frame, obj, quote if spoken else ""))
    candidates.sort(key=lambda c: (c[0], c[1]["timestamp"], -c[2]["confidence"]))
    used = set()
    for _, frame, obj, quote in candidates:
        label = obj["label"]
        if label in used:
            continue
        x, y, w, h = obj["box"]
        area = w * h
        location = timestamp(frame["timestamp"])
        evidence = f"At {location}, the browser model estimates a {label} ({obj['confidence']:.0%} confidence), with its box covering {area:.1%} of the sampled frame."
        if quote:
            evidence += f" The supplied subtitle at this moment says: “{quote[:180]}”."
        if area < 0.10 and (quote or object_mentioned(label, context)):
            add(
                f"Try a closer view of the {label}",
                evidence,
                f"Test a tighter shot of the {label} at {location}, keeping the relevant details in view. Compare the crop on a phone before replacing this shot.",
                frame,
                quote,
            )
        elif min(x, y, 1 - x - w, 1 - y - h) < 0.025:
            add(
                f"Check space around the {label}",
                evidence + " Its estimated box meets an edge of the preview.",
                f"Inspect the {label} at {location} before applying a vertical crop or adding platform overlays. Try leaving extra space around the subject if this edit would cut off useful details.",
                frame,
                quote,
            )
        elif quote:
            add(
                f"Keep the {label} visible during this explanation",
                evidence,
                f"Use the detected {label} shot at {location} as an edit reference for “{quote[:140]}”. Keep the detail you describe visible; add a closer insert only if the phone preview makes it hard to follow.",
                frame,
                quote,
            )
        else:
            add(
                f"Make the {label} shot purposeful",
                evidence,
                f"Review the {label} shot at {location} alongside your intended message. Keep it when it explains the point; if you mention this subject elsewhere, test this shot beside that line. The detector cannot judge what the subject is doing.",
                frame,
            )
        used.add(label)
        if len(recs) == 3:
            break
    report["visualReview"] = {
        **payload,
        "frames": frames,
        "subjects": labels,
        "note": NOTE,
    }
    # Idempotent retries replace earlier visual suggestions without changing
    # the report, private dataset evidence, score or account usage count.
    report["recommendations"] = [
        r for r in report["recommendations"] if r.get("source") != SOURCE
    ] + recs
    return report

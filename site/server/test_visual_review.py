import copy
import hashlib
import json
import pathlib
import unittest
from pydantic import ValidationError
from .visual_review import MODEL, CLASSES, VisualPayload, attach_visual_review


class VisualReviewTests(unittest.TestCase):
    def report(self):
        return {
            "transcript": "WEBVTT\n\n00:00.000 --> 00:03.000\nKeep the dog visible while you explain this step.",
            "text": "A dog demonstration",
            "topic": "dogs",
            "videoTitle": "",
            "overallScore": 72,
            "recommendations": [{"title": "Existing feedback"}],
            "mediaAnalysis": {"timeline": [{"timestamp": 0}, {"timestamp": 3}]},
        }

    def payload(self):
        return {
            "model": MODEL,
            "frames": [
                {
                    "timestamp": 0,
                    "objects": [
                        {
                            "label": "dog",
                            "confidence": 0.91,
                            "box": [0.4, 0.3, 0.15, 0.2],
                        }
                    ],
                }
            ],
        }

    def test_real_model_assets_have_verified_digests(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "public/vision/coco-ssd-v1"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["version"], MODEL)
        self.assertEqual(len(CLASSES), 80)
        runtime = root.parent / "tfjs-wasm-4.22.0"
        for directory, entries in [
            (root, manifest["files"]),
            (runtime, json.loads((runtime / "manifest.json").read_text())["files"]),
        ]:
            for item in entries:
                raw = (directory / item["file"]).read_bytes()
                self.assertEqual(len(raw), item["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])

    def test_specific_timed_feedback_is_idempotent_without_score_changes(self):
        report = self.report()
        original = copy.deepcopy(report)
        updated = attach_visual_review(report, self.payload())
        self.assertEqual(report, original)
        rec = updated["recommendations"][-1]
        self.assertIn("closer view of the dog", rec["title"])
        self.assertIn("3.0%", rec["reason"])
        self.assertIn("Keep the dog visible", rec["quote"])
        self.assertEqual(rec["timestamp"], 0)
        self.assertEqual(updated["overallScore"], 72)
        self.assertEqual(attach_visual_review(updated, self.payload()), updated)

    def test_untimed_words_are_never_claimed_to_align_with_a_frame(self):
        report = self.report()
        report["transcript"] = "The dog runs across the field."
        updated = attach_visual_review(report, self.payload())
        self.assertIsNone(updated["recommendations"][-1]["quote"])
        self.assertNotIn(
            "subtitle at this moment", updated["recommendations"][-1]["reason"]
        )

    def test_malformed_labels_geometry_and_times_are_rejected(self):
        for patch in [
            {"label": "happy person"},
            {"confidence": float("nan")},
            {"confidence": float("inf")},
            {"confidence": 0.3},
            {"box": [0, 0, 2, 1]},
            {"box": [0, 0, -1, 1]},
            {"box": [0, 0, 0.2]},
            {"box": [0, 0, float("nan"), 1]},
        ]:
            payload = self.payload()
            payload["frames"][0]["objects"][0].update(patch)
            with self.assertRaises(ValidationError):
                VisualPayload.model_validate(payload)
        payload = self.payload()
        payload["frames"][0]["timestamp"] = 5
        with self.assertRaises(ValueError):
            attach_visual_review(self.report(), payload)
        payload = self.payload()
        payload["frames"] *= 2
        with self.assertRaises(ValueError):
            attach_visual_review(self.report(), payload)

    def test_empty_detections_do_not_invent_subjects_or_suggestions(self):
        payload = self.payload()
        payload["frames"][0]["objects"] = []
        updated = attach_visual_review(self.report(), payload)
        self.assertEqual(updated["visualReview"]["subjects"], [])
        self.assertEqual(updated["recommendations"], self.report()["recommendations"])
        self.assertIn(
            "missed detection does not prove absence", updated["visualReview"]["note"]
        )

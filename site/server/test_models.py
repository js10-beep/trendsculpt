import csv, io, pathlib, unittest, json, hashlib, subprocess, sys, tempfile, shutil
from .datasets import train_private_csv
from .analysis import MODELS

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ModelDataTests(unittest.TestCase):
    def sample(self):
        return (ROOT / "tests/fixtures/synthetic-creator-watch.csv").read_text()

    def test_duplicate_video_snapshots_are_counted_once(self):
        sample = self.sample()
        lines = sample.splitlines()
        model = train_private_csv(sample + "\n" + "\n".join(lines[1:11]), "YouTube")
        self.assertEqual(model["info"]["rows"], 40)
        self.assertEqual(model["info"]["duplicatesSkipped"], 10)
        self.assertEqual(model["info"]["watchRows"], 40)
        self.assertTrue(model["info"]["watchValidation"]["beatsBaseline"])

    def test_youtube_analytics_headers_and_clock_durations(self):
        rows = list(csv.DictReader(io.StringIO(self.sample())))
        target = io.StringIO()
        writer = csv.writer(target)
        writer.writerow(
            [
                "Video title",
                "Views",
                "Likes",
                "Comments",
                "Transcript",
                "Video duration",
                "Average view duration",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["title"],
                    r["views"],
                    r["likes"],
                    r["comments"],
                    r["transcript"],
                    "0:00:30",
                    "0:00:" + r["average_view_duration_seconds"].zfill(2),
                ]
            )
        model = train_private_csv(target.getvalue(), "YouTube")
        self.assertEqual({r["rate"] for r in model["watchModel"]["rows"]}, {20, 80})
        self.assertIn("flour", model["watchModel"]["vector"].vocabulary_)
        self.assertNotIn(
            "average_view_duration", model["watchModel"]["vector"].vocabulary_
        )

    def test_percentage_targets_preserve_replays_and_reject_nonfinite(self):
        rows = list(csv.DictReader(io.StringIO(self.sample())))
        target = io.StringIO()
        writer = csv.writer(target)
        writer.writerow(["title", "views", "likes", "average_percentage_viewed"])
        for i, r in enumerate(rows):
            writer.writerow(
                [r["title"], 1000, 10, "NaN" if i == 0 else 125 if i % 2 == 0 else 20]
            )
        model = train_private_csv(target.getvalue(), "YouTube")
        self.assertEqual(model["info"]["watchRowsSkipped"], 1)
        self.assertEqual(model["info"]["watchRows"], 39)
        self.assertIn(125, {r["rate"] for r in model["watchModel"]["rows"]})

    def test_missing_outcome_columns_are_rejected(self):
        with self.assertRaises(ValueError):
            train_private_csv("title,views\nExample,1000", "YouTube")
        with self.assertRaises(ValueError):
            train_private_csv("title,views,shares\nExample,1000,2", "YouTube")

    def test_bundle_checksum_and_no_completion_model(self):
        meta = json.loads(
            (ROOT / "server/reference-data/artifact-manifest.json").read_text()
        )
        self.assertEqual(
            hashlib.sha256((ROOT / meta["artifact"]).read_bytes()).hexdigest(),
            meta["sha256"],
        )
        self.assertNotIn("completionModel", MODELS["Kuaishou reference"])
        self.assertEqual(len({r["video_id"] for r in MODELS["YouTube"]["rows"]}), 30000)

    def test_corrupted_artifact_is_rejected_before_installation(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "scripts").mkdir()
            (root / "server/reference-data").mkdir(parents=True)
            shutil.copyfile(
                ROOT / "scripts/prepare_models.py", root / "scripts/prepare_models.py"
            )
            (root / "server/reference-data/models.joblib").write_bytes(b"corrupt")
            (root / "server/reference-data/artifact-manifest.json").write_text(
                json.dumps(
                    {
                        "artifact": "server/reference-data/models.joblib",
                        "sha256": "0" * 64,
                    }
                )
            )
            p = subprocess.run(
                [sys.executable, str(root / "scripts/prepare_models.py")],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("checksum mismatch", p.stderr)
            self.assertFalse((root / ".models").exists())


if __name__ == "__main__":
    unittest.main()

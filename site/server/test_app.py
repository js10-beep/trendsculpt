import base64, io, os, pathlib, tempfile, unittest, json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

os.environ["TRENDSCULPT_DATA_DIR"] = tempfile.mkdtemp(prefix="trendsculpt-api-test-")
test_url = os.environ.get("TRENDSCULPT_TEST_DATABASE_URL")
if test_url:
    parsed = urlsplit(test_url)
    if parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    } or not parsed.path.endswith("_test"):
        raise RuntimeError("API tests require an isolated local database named *_test.")
    os.environ["DATABASE_URL"] = test_url
    os.environ["TRENDSCULPT_ALLOW_LOCAL_DATABASE"] = "true"
else:
    # Never point destructive fixtures at a real deployment's DATABASE_URL.
    os.environ.pop("DATABASE_URL", None)
from fastapi.testclient import TestClient
from PIL import Image
from .app import app, db, COOKIE
from .analysis import analyze_content


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        with db() as c:
            c.execute("DELETE FROM users")
            c.execute("DELETE FROM attempts")
        self.a = TestClient(app)
        self.b = TestClient(app)

    def account(self, client, email="one@example.com"):
        r = client.post(
            "/api/auth/signup",
            json={
                "name": "Test Creator",
                "email": email,
                "password": "correct-horse-42",
                "agree": True,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def analyze(self, client, **extra):
        body = {
            "text": "How to build 3 habits for creators? Save this useful guide and tell me your favorite. #creator",
            "type": "Text",
            "platform": "Instagram",
            "objective": "Engagement",
            "audience": "creators",
            "topic": "content strategy",
            "cta": "",
        }
        body.update(extra)
        return client.post("/api/analyze", json=body)

    def test_password_auth_and_protected_sessions(self):
        response = self.a.post(
            "/api/auth/signup",
            json={
                "name": "User",
                "email": "one@example.com",
                "password": "correct-horse-42",
                "agree": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        id = response.json()["user"]["id"]
        with db() as c:
            stored = c.execute(
                "SELECT password FROM users WHERE id=?", (id,)
            ).fetchone()[0]
        self.assertNotIn("correct-horse", stored)
        self.assertEqual(self.a.get("/api/auth/me").json()["user"]["id"], id)
        self.assertEqual(
            self.b.post(
                "/api/auth/login",
                json={"email": "one@example.com", "password": "incorrect-password"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.b.post(
                "/api/auth/login",
                json={"email": "one@example.com", "password": "correct-horse-42"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.a.post(
                "/api/profile", headers={"Origin": "https://evil.example"}, json={}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.a.post(
                "/api/auth/signup",
                json={
                    "name": "User",
                    "email": "one@example.com",
                    "password": "short",
                    "agree": True,
                },
            ).status_code,
            400,
        )
        self.a.post("/api/auth/logout")
        self.assertIsNone(self.a.get("/api/auth/me").json()["user"])

    def test_accounts_cannot_access_others_reports_or_media(self):
        self.account(self.a)
        self.account(self.b, "two@example.com")
        buf = io.BytesIO()
        Image.new("RGB", (720, 1280), "green").save(buf, "PNG")
        r = self.analyze(
            self.a,
            type="Image",
            media="data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            mediaName="image.png",
        )
        self.assertEqual(r.status_code, 200, r.text)
        id = r.json()["id"]
        self.assertEqual(r.json()["mediaAnalysis"]["width"], 720)
        self.assertEqual(self.a.post("/api/reports/" + id + "/save").status_code, 200)
        self.assertEqual(len(self.a.get("/api/reports").json()), 1)
        self.assertEqual(self.b.get("/api/reports").json(), [])
        for method, url in [
            ("get", "/api/reports/" + id),
            ("delete", "/api/reports/" + id),
            ("get", "/api/media/" + id),
            ("post", "/api/reports/" + id + "/save"),
        ]:
            self.assertEqual(getattr(self.b, method)(url).status_code, 404)
        self.assertEqual(
            self.analyze(self.b, type="Image", media="/api/media/" + id).status_code,
            404,
        )
        self.assertEqual(self.a.get("/api/media/" + id).status_code, 200)

    def test_password_recovery_rotates_codes_and_revokes_sessions(self):
        account = self.account(self.a)
        self.b.post(
            "/api/auth/login",
            json={"email": "one@example.com", "password": "correct-horse-42"},
        )
        r = self.a.post(
            "/api/auth/recover",
            json={
                "email": "one@example.com",
                "code": account["recoveryCode"],
                "password": "new-correct-horse-42",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.json()["recoveryCode"], account["recoveryCode"])
        self.assertIsNone(self.b.get("/api/auth/me").json()["user"])
        self.assertEqual(
            self.a.post(
                "/api/auth/recover",
                json={
                    "email": "one@example.com",
                    "code": account["recoveryCode"],
                    "password": "another-password-42",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.a.post(
                "/api/auth/login",
                json={"email": "one@example.com", "password": "correct-horse-42"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.a.post(
                "/api/auth/login",
                json={"email": "one@example.com", "password": "new-correct-horse-42"},
            ).status_code,
            200,
        )

    def test_deletion_requires_password_and_cascades_private_data(self):
        a = self.account(self.a)
        r = self.analyze(self.a).json()
        self.a.post("/api/reports/" + r["id"] + "/save")
        self.assertEqual(
            self.a.request(
                "DELETE", "/api/account", json={"password": "incorrect-password"}
            ).status_code,
            401,
        )
        self.assertIsNotNone(self.a.get("/api/auth/me").json()["user"])
        self.assertEqual(
            self.a.request(
                "DELETE", "/api/account", json={"password": "correct-horse-42"}
            ).status_code,
            200,
        )
        with db() as c:
            for table in ["users", "sessions", "reports", "usage", "datasets"]:
                self.assertEqual(
                    c.execute("SELECT count(*) FROM " + table).fetchone()[0], 0
                )
        self.assertIsNone(self.a.get("/api/auth/me").json()["user"])
        self.assertEqual(self.a.get("/api/reports").status_code, 401)

    def test_quotas_and_score_integrity_are_server_enforced(self):
        a = self.account(self.a)
        r = self.analyze(self.a, overallScore=100).json()
        self.assertLess(r["overallScore"], 100)
        self.a.post("/api/reports/" + r["id"] + "/save")
        self.a.post("/api/reports/" + r["id"] + "/save")
        self.assertEqual(self.a.get("/api/usage").json()["count"], 1)
        self.a.delete("/api/reports/" + r["id"])
        self.assertEqual(self.a.get("/api/usage").json()["count"], 1)
        with db() as c:
            c.execute("UPDATE usage SET count=100 WHERE user_id=?", (a["user"]["id"],))
        self.assertEqual(self.analyze(self.a).status_code, 429)
        with db() as c:
            c.execute("UPDATE usage SET count=99 WHERE user_id=?", (a["user"]["id"],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(lambda _: self.analyze(self.a).status_code, range(2))
            )
        self.assertEqual(sorted(responses), [200, 429])
        self.assertEqual(self.a.get("/api/usage").json()["count"], 100)

    def test_real_local_models_and_decoded_video(self):
        self.account(self.a)
        r = self.analyze(self.a)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["evidence"]["datasetRows"], 176)
        self.assertGreater(r.json()["evidence"]["historicalEstimate"], 0)
        video = (
            pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/short.mp4"
        ).read_bytes()
        r = self.analyze(
            self.a,
            type="Video",
            media="data:video/mp4;base64," + base64.b64encode(video).decode(),
            mediaName="short.mp4",
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(
            r.json()["watchReference"]
            and r.json()["watchReference"]["modelUsedForScore"]
        )
        self.assertGreater(r.json()["mediaAnalysis"]["framesSampled"], 1)
        self.assertAlmostEqual(r.json()["mediaAnalysis"]["duration"], 1, places=1)
        self.assertEqual(
            self.analyze(
                self.a, media="data:image/png;base64,aW52YWxpZA==", type="Image"
            ).status_code,
            400,
        )

    def test_transcript_feedback_is_specific_and_timestamped(self):
        self.account(self.a)
        subtitles = "WEBVTT\n\n00:00.000 --> 00:03.000\nHello everyone welcome back.\n\n00:40.000 --> 00:47.000\nMix 50 grams of flour with 50 grams of water for your sourdough starter.\n\n02:40.000 --> 02:45.000\nFeed the sourdough starter each morning."
        sourdough = self.analyze(
            self.a,
            platform="YouTube (long-form)",
            transcript=subtitles,
            videoTitle="How to make a sourdough starter",
            text="",
        ).json()
        gardening = self.analyze(
            self.a,
            platform="YouTube (long-form)",
            transcript=subtitles.replace("sourdough starter", "basil plant").replace(
                "flour", "potting soil"
            ),
            videoTitle="How to grow basil",
            text="",
        ).json()
        self.assertNotEqual(sourdough["hooks"], gardening["hooks"])
        self.assertIn("50 grams", " ".join(sourdough["hooks"]))
        self.assertNotIn("your next post", str(sourdough["recommendations"]))
        self.assertEqual(sourdough["contentReview"]["source"], "Timestamped subtitles")
        self.assertTrue(sourdough["contentReview"]["longForm"])
        self.assertEqual(sourdough["contentReview"]["chapters"][1]["timestamp"], 40)
        self.assertIn("Title clarity", sourdough["scores"])
        self.assertNotIn("Retention potential", sourdough["scores"])
        bad = self.analyze(
            self.a,
            transcript="WEBVTT\n00:10.000 --> 00:01.000\nBad cue",
            platform="YouTube (long-form)",
        )
        self.assertEqual(bad.status_code, 400)

    def test_long_video_upload_is_sampled_private_and_keeps_original_ephemeral(self):
        self.account(self.a)
        self.account(self.b, "two@example.com")
        video = (
            pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/long-form.mp4"
        ).read_bytes()
        body = {
            "type": "Video",
            "platform": "YouTube (long-form)",
            "videoTitle": "Sourdough starter explained",
            "transcript": "0:00 Hello everyone welcome back.\n0:40 Mix 50 grams of flour with water.\n1:30 Feed your starter every day.\n3:00 Tell me which flour you use.",
            "text": "",
        }
        response = self.a.post(
            "/api/analyze/video",
            data={"payload": json.dumps(body)},
            files={"video": ("long.mp4", video, "video/mp4")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertGreater(report["mediaAnalysis"]["duration"], 180)
        self.assertGreater(len(report["mediaAnalysis"]["timeline"]), 7)
        self.assertTrue(report["mediaAnalysis"]["hasAudio"])
        self.assertGreater(len(report["mediaAnalysis"]["audioWindows"]), 0)
        self.assertTrue(
            any(
                "SOURDOUGH" in f["overlayText"].upper()
                for f in report["mediaAnalysis"]["timeline"]
            )
        )
        self.assertIsNone(report["media"])
        with db() as c:
            row = c.execute(
                "SELECT media FROM reports WHERE id=?", (report["id"],)
            ).fetchone()
        self.assertIsNone(row[0])
        self.assertEqual(
            self.a.post("/api/reports/" + report["id"] + "/save").status_code, 200
        )
        self.assertGreater(
            len(
                self.a.get("/api/reports/" + report["id"]).json()["mediaAnalysis"][
                    "timeline"
                ]
            ),
            7,
        )
        self.assertEqual(self.b.get("/api/reports/" + report["id"]).status_code, 404)
        self.assertEqual(
            self.analyze(self.b, sourceReportId=report["id"]).status_code, 404
        )
        invalid = self.a.post(
            "/api/analyze/video",
            data={"payload": json.dumps(body)},
            files={"video": ("bad.mp4", b"not a video", "video/mp4")},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_private_csv_training_is_scoped_and_can_be_deleted(self):
        self.account(self.a)
        self.account(self.b, "two@example.com")
        csv = "\ufeffcaption,impressions,likes,comments\n" + "\n".join(
            f"Creator strategy habit {i},1000,{20+i*3},{i}" for i in range(30)
        )
        csv += "\nInvalid numeric observation,1000,NaN,0"
        r = self.a.post(
            "/api/datasets",
            json={"platform": "Instagram", "csv": csv, "permission": True},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["rows"], 30)
        self.assertEqual(len(self.a.get("/api/datasets").json()), 1)
        self.assertEqual(self.b.get("/api/datasets").json(), [])
        self.assertEqual(self.analyze(self.a).json()["evidence"]["datasetRows"], 30)
        self.assertEqual(self.analyze(self.b).json()["evidence"]["datasetRows"], 176)
        self.assertEqual(self.a.delete("/api/datasets/Instagram").status_code, 200)
        self.assertEqual(self.analyze(self.a).json()["evidence"]["datasetRows"], 176)
        self.assertEqual(
            self.a.post(
                "/api/datasets",
                json={
                    "platform": "Instagram",
                    "csv": "wrong,fields\n1,2",
                    "permission": True,
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.a.post(
                "/api/datasets",
                json={
                    "platform": "Instagram",
                    "csv": "caption,impressions,likes\n" + "x" * 150000 + ",1000,2",
                    "permission": True,
                },
            ).status_code,
            400,
        )

    def test_public_references_have_validated_targets_and_provenance(self):
        sources = self.a.get("/api/sources").json()
        models = {m["platform"]: m for m in sources["models"]}
        self.assertEqual(models["YouTube"]["rows"], 30000)
        self.assertTrue(models["YouTube"]["temporalValidation"]["beatsBaseline"])
        self.assertLess(
            models["YouTube"]["holdoutMAE"], models["YouTube"]["baselineMAE"]
        )
        self.assertEqual(models["Kuaishou reference"]["rows"], 5432)
        self.assertEqual(sources["sources"][2]["license"], "CC BY-SA 4.0")
        self.account(self.a)
        r = self.analyze(
            self.a,
            platform="YouTube (long-form)",
            text="How to mix sourdough flour and water?",
        ).json()
        self.assertEqual(r["evidence"]["datasetRows"], 30000)
        self.assertIsNone(r["watchReference"])
        self.assertIn(
            "public-2020-2024-kuairand",
            self.a.get("/api/health").json()["modelVersion"],
        )

    def test_measured_short_video_gets_separate_kuaishou_reference(self):
        self.account(self.a)
        video = (
            pathlib.Path(__file__).resolve().parents[1]
            / "tests/fixtures/watch-reference.mp4"
        ).read_bytes()
        r = self.analyze(
            self.a,
            type="Video",
            platform="YouTube Shorts",
            media="data:video/mp4;base64," + base64.b64encode(video).decode(),
            mediaName="sample.mp4",
            duration=90,
            transcript="0:00 Mix 50 grams of flour with water.\n0:07 Feed your sourdough starter every day.",
        ).json()
        reference = r["watchReference"]
        self.assertAlmostEqual(reference["measuredDuration"], 10, delta=0.2)
        self.assertEqual(reference["durationBand"], [5, 15])
        self.assertFalse(reference["modelUsedForScore"])
        self.assertGreater(reference["referenceExposures"], 100)
        self.assertIsNone(r["creatorWatchEvidence"])
        saved = self.a.get("/api/reports/" + r["id"]).json()
        self.assertEqual(saved["watchReference"], reference)

    def test_private_creator_watch_training_is_scoped_deleted_and_quoted(self):
        self.account(self.a)
        self.account(self.b, "two@example.com")
        csv_text = (
            pathlib.Path(__file__).resolve().parents[1]
            / "tests/fixtures/synthetic-creator-watch.csv"
        ).read_text()
        response = self.a.post(
            "/api/datasets",
            json={"platform": "YouTube", "csv": csv_text, "permission": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["watchRows"], 40)
        self.assertTrue(response.json()["watchValidation"]["beatsBaseline"])
        r = self.analyze(
            self.a,
            platform="YouTube (long-form)",
            text="",
            videoTitle="Sourdough flour water starter",
            transcript="0:00 Mix 50 grams of flour with water.\n0:40 Feed your sourdough starter every day.",
        ).json()
        self.assertEqual(r["creatorWatchEvidence"]["datasetRows"], 40)
        self.assertTrue(r["creatorWatchEvidence"]["usableReference"])
        self.assertTrue(
            any(
                s.get("source") == "Your private creator analytics"
                and "50 grams" in s["quote"]
                for s in r["recommendations"]
            )
        )
        self.assertIsNone(
            self.analyze(self.b, platform="YouTube Shorts").json()[
                "creatorWatchEvidence"
            ]
        )
        self.assertEqual(self.b.get("/api/reports/" + r["id"]).status_code, 404)
        self.assertEqual(self.a.delete("/api/datasets/YouTube").status_code, 200)
        self.assertIsNone(
            self.analyze(self.a, platform="YouTube Shorts").json()[
                "creatorWatchEvidence"
            ]
        )


if __name__ == "__main__":
    unittest.main()

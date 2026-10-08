import base64, io, os, pathlib, tempfile, unittest
from datetime import datetime, timezone

os.environ["TRENDSCULPT_DATA_DIR"] = tempfile.mkdtemp(prefix="trendsculpt-api-test-")
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
        self.assertGreater(r.json()["mediaAnalysis"]["framesSampled"], 1)
        self.assertAlmostEqual(r.json()["mediaAnalysis"]["duration"], 1, places=1)
        self.assertEqual(
            self.analyze(
                self.a, media="data:image/png;base64,aW52YWxpZA==", type="Image"
            ).status_code,
            400,
        )

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


if __name__ == "__main__":
    unittest.main()

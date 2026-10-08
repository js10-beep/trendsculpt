import pickle, csv
import base64, hashlib, hmac, json, os, pathlib, re, secrets, sqlite3, time, uuid
from contextlib import contextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from .datasets import train_private_csv
from .analysis import analyze_content, inspect_media, MODELS

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = pathlib.Path(os.environ.get("TRENDSCULPT_DATA_DIR", str(ROOT / ".data")))
DATA.mkdir(parents=True, exist_ok=True)
os.chmod(DATA, 0o700)
DATABASE = DATA / "app.sqlite"
COOKIE = "ts_session"
SECURE = (
    os.environ.get(
        "COOKIE_SECURE",
        "true" if os.environ.get("SITE_ORIGIN", "").startswith("https://") else "false",
    ).lower()
    == "true"
)
MAX_BODY = 15 * 1024 * 1024


@contextmanager
def db():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


with db() as c:
    c.executescript("""PRAGMA journal_mode=WAL;
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,recovery TEXT NOT NULL,profile TEXT NOT NULL,created REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,report TEXT NOT NULL,saved INTEGER NOT NULL DEFAULT 0,media BLOB,mime TEXT,created REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS datasets(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,platform TEXT,model BLOB NOT NULL,info TEXT NOT NULL,PRIMARY KEY(user_id,platform));
 CREATE INDEX IF NOT EXISTS own_reports ON reports(user_id,saved,created);
 CREATE TABLE IF NOT EXISTS usage(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,month TEXT,count INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,month));
 CREATE TABLE IF NOT EXISTS attempts(key TEXT,created REAL);
 CREATE INDEX IF NOT EXISTS recent_attempts ON attempts(key,created);""")
os.chmod(DATABASE, 0o600)
app = FastAPI(title="TrendSculpt", docs_url=None, redoc_url=None)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = 0

        async def bounded_receive():
            nonlocal length
            msg = await receive()
            length += len(msg.get("body", b""))
            if length > MAX_BODY:
                raise HTTPException(413, "Upload exceeds the 10 MB media limit.")
            return msg

        await self.app(scope, bounded_receive, send)


app.add_middleware(BodyLimit)


@app.middleware("http")
async def protections(request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        expected = str(request.base_url).rstrip("/")
        origin = request.headers.get("origin")
        configured = os.environ.get("SITE_ORIGIN")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and origin not in {expected, configured}
        ):
            return Response("Cross-origin writes are not permitted.", 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def json_object(request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Send a valid JSON request.")
    if not isinstance(data, dict):
        raise HTTPException(400, "Send a valid request object.")
    return data


def hash_secret(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        value.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32
    )
    return salt.hex() + ":" + digest.hex()


def password_ok(value, stored):
    try:
        salt, digest = stored.split(":")
        actual = hashlib.scrypt(
            value.encode(),
            salt=bytes.fromhex(salt),
            n=32768,
            r=8,
            p=1,
            maxmem=64 * 1024 * 1024,
            dklen=32,
        ).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


DUMMY = password_hash("placeholder password never used")


def password_check(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise HTTPException(400, "Use a password between 10 and 128 characters.")


def email_check(value):
    if (
        not isinstance(value, str)
        or len(value) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip())
    ):
        raise HTTPException(400, "Enter a valid email address.")
    return value.strip().lower()


def session_user(request):
    token = request.cookies.get(COOKIE, "")
    with db() as c:
        row = c.execute(
            "SELECT users.* FROM users JOIN sessions ON users.id=sessions.user_id WHERE sessions.hash=? AND sessions.expires>?",
            (hash_secret(token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Please log in to continue.")
    return row


def profile(row):
    return {
        **json.loads(row["profile"]),
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
    }


def session(response, id, remember=False):
    token = secrets.token_urlsafe(32)
    duration = 30 * 86400 if remember else 86400
    with db() as c:
        c.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (hash_secret(token), id, time.time() + duration),
        )
    response.set_cookie(
        COOKIE,
        token,
        max_age=duration if remember else None,
        httponly=True,
        secure=SECURE,
        samesite="lax",
        path="/",
    )


def rate_limit(request, label, limit=12):
    ip = request.client.host if request.client else "unknown"
    key = hash_secret(ip + ":" + label)
    now = time.time()
    with db() as c:
        c.execute("DELETE FROM attempts WHERE created<?", (now - 3600,))
        count = c.execute(
            "SELECT count(*) FROM attempts WHERE key=? AND created>?", (key, now - 600)
        ).fetchone()[0]
        if count >= limit:
            raise HTTPException(
                429, "Too many attempts. Please wait 10 minutes and try again."
            )
        c.execute("INSERT INTO attempts VALUES(?,?)", (key, now))


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "models": [{**v["info"]} for v in MODELS.values()],
        "auth": "server sessions",
        "emailDelivery": False,
    }


@app.get("/api/auth/me")
def me(request: Request):
    try:
        return {"user": profile(session_user(request))}
    except HTTPException:
        return {"user": None}


@app.post("/api/auth/signup")
async def signup(request: Request, response: Response):
    rate_limit(request, "signup", 30)
    data = await json_object(request)
    email = email_check(data.get("email"))
    password = data.get("password")
    password_check(password)
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 80:
        raise HTTPException(400, "Add a name between 1 and 80 characters.")
    if data.get("agree") is not True:
        raise HTTPException(400, "Please agree to the Terms and Privacy Policy.")
    id = str(uuid.uuid4())
    recovery = secrets.token_urlsafe(24)
    prefs = {
        "platform": "Instagram",
        "creator": "Content Creator",
        "onboarded": False,
        "notifications": False,
    }
    try:
        with db() as c:
            c.execute(
                "INSERT INTO users VALUES(?,?,?,?,?,?,?)",
                (
                    id,
                    email,
                    name,
                    password_hash(password),
                    hash_secret(recovery),
                    json.dumps(prefs),
                    time.time(),
                ),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(
            409,
            "An account with this email already exists. Log in or recover your account.",
        )
    session(response, id)
    return {
        "user": {**prefs, "id": id, "email": email, "name": name},
        "recoveryCode": recovery,
    }


@app.post("/api/auth/login")
async def login(request: Request, response: Response):
    rate_limit(request, "login", 30)
    data = await json_object(request)
    email = email_check(data.get("email"))
    password = str(data.get("password", ""))[:129]
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    valid = password_ok(password, row["password"] if row else DUMMY)
    if not row or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    session(response, row["id"], bool(data.get("remember")))
    return {"user": profile(row)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with db() as c:
        c.execute(
            "DELETE FROM sessions WHERE hash=?",
            (hash_secret(request.cookies.get(COOKIE, "")),),
        )
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.post("/api/auth/recover")
async def recover(request: Request, response: Response):
    rate_limit(request, "recovery", 15)
    data = await json_object(request)
    email = email_check(data.get("email"))
    password = data.get("password")
    password_check(password)
    code = str(data.get("code", ""))
    new_code = secrets.token_urlsafe(24)
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not hmac.compare_digest(row["recovery"], hash_secret(code)):
            raise HTTPException(400, "Email or recovery code is incorrect.")
        c.execute(
            "UPDATE users SET password=?,recovery=? WHERE id=?",
            (password_hash(password), hash_secret(new_code), row["id"]),
        )
        c.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "recoveryCode": new_code}


@app.patch("/api/profile")
async def update_profile(request: Request):
    row = session_user(request)
    data = await json_object(request)
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 80:
        raise HTTPException(400, "Name must have 1–80 characters.")
    if data.get("platform") not in [
        "Instagram",
        "YouTube Shorts",
        "TikTok",
        "LinkedIn",
        "X",
        "Other",
    ]:
        raise HTTPException(400, "Choose a supported platform.")
    if data.get("creator") not in [
        "Content Creator",
        "Influencer",
        "Founder",
        "Brand",
        "Social Media Manager",
        "Agency",
        "Other",
    ]:
        raise HTTPException(400, "Choose a creator type.")
    prefs = {
        "platform": data["platform"],
        "creator": data["creator"],
        "onboarded": bool(data.get("onboarded")),
        "notifications": bool(data.get("notifications")),
    }
    with db() as c:
        c.execute(
            "UPDATE users SET name=?,profile=? WHERE id=?",
            (name, json.dumps(prefs), row["id"]),
        )
    return {"user": {**prefs, "name": name, "id": row["id"], "email": row["email"]}}


@app.delete("/api/account")
async def delete_account(request: Request, response: Response):
    row = session_user(request)
    data = await json_object(request)
    if not password_ok(str(data.get("password", "")), row["password"]):
        raise HTTPException(401, "Confirm your password to delete your account.")
    with db() as c:
        c.execute("DELETE FROM users WHERE id=?", (row["id"],))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


class Content(BaseModel):
    text: str = Field(default="", max_length=5000)
    type: Literal["Text", "Image", "Video"] = "Text"
    platform: Literal["Instagram", "YouTube Shorts", "TikTok", "LinkedIn", "X"] = (
        "Instagram"
    )
    objective: Literal["Reach", "Engagement", "Followers", "Leads", "Awareness"] = (
        "Engagement"
    )
    audience: str = Field(default="", max_length=150)
    topic: str = Field(default="", max_length=100)
    cta: str = Field(default="", max_length=150)
    media: str | None = Field(default=None, max_length=14 * 1024 * 1024)
    mediaName: str | None = Field(default=None, max_length=200)
    applied: bool = False


def media_bytes(data, owner):
    media = data.get("media")
    mime = None
    raw = None
    stats = None
    if not media:
        return raw, mime, stats
    if media.startswith("/api/media/"):
        id = media.rsplit("/", 1)[-1]
        with db() as c:
            r = c.execute(
                "SELECT media,mime,report FROM reports WHERE id=? AND user_id=?",
                (id, owner),
            ).fetchone()
        if not r or not r["media"]:
            raise HTTPException(404, "Media not found in your account.")
        return r["media"], r["mime"], json.loads(r["report"]).get("mediaAnalysis")
    match = re.fullmatch(
        r"data:(image/(?:png|jpeg|webp)|video/mp4);base64,([A-Za-z0-9+/=\r\n]+)", media
    )
    if not match:
        raise HTTPException(400, "Use PNG, JPG, WEBP or MP4 media.")
    mime = match[1]
    try:
        raw = base64.b64decode(match[2], validate=True)
    except ValueError:
        raise HTTPException(400, "Could not decode uploaded media.")
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Media must be under 10 MB.")
    if mime == "video/mp4" and raw[4:8] != b"ftyp":
        raise HTTPException(
            400, "Upload a valid MP4 file, not a playlist or external media reference."
        )
    if (
        data["type"] == "Video"
        and mime != "video/mp4"
        or data["type"] == "Image"
        and not mime.startswith("image/")
    ):
        raise HTTPException(
            400, "The uploaded file does not match the selected content type."
        )
    try:
        stats = inspect_media(raw, mime)
    except Exception as e:
        if isinstance(e, ValueError):
            raise HTTPException(400, str(e))
        raise HTTPException(
            400, "This media could not be read. Try a supported export."
        )
    return raw, mime, stats


@app.post("/api/analyze")
async def analysis(request: Request):
    owner = session_user(request)
    rate_limit(request, "analyze:" + owner["id"], 30)
    try:
        data = Content.model_validate(await json_object(request)).model_dump()
    except (ValidationError, json.JSONDecodeError):
        raise HTTPException(400, "Check your content fields and try again.")
    if not data["text"].strip() and not data.get("media"):
        raise HTTPException(400, "Add content or upload a file first.")
    if data["type"] != "Text" and not data.get("media"):
        raise HTTPException(400, "Upload media before analyzing.")
    raw, mime, stats = media_bytes(data, owner["id"])
    from datetime import datetime, timezone

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        usage = c.execute(
            "SELECT count FROM usage WHERE user_id=? AND month=?", (owner["id"], month)
        ).fetchone()
        if usage and usage["count"] >= 100:
            raise HTTPException(
                429,
                "Your free workspace includes 100 analyses per month. Try again next month.",
            )
        c.execute(
            "INSERT INTO usage(user_id,month,count) VALUES(?,?,1) ON CONFLICT(user_id,month) DO UPDATE SET count=count+1",
            (owner["id"], month),
        )
    with db() as c:
        private_rows = c.execute(
            "SELECT platform,model FROM datasets WHERE user_id=?", (owner["id"],)
        ).fetchall()
    private_models = {r["platform"]: pickle.loads(r["model"]) for r in private_rows}
    report = analyze_content(data, stats, private_models)
    report["media"] = "/api/media/" + report["id"] if raw else None
    with db() as c:
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?,?,?)",
            (report["id"], owner["id"], json.dumps(report), 0, raw, mime, time.time()),
        )
    return report


@app.get("/api/reports")
def reports(request: Request):
    owner = session_user(request)
    with db() as c:
        rows = c.execute(
            "SELECT report FROM reports WHERE user_id=? AND saved=1 ORDER BY created DESC",
            (owner["id"],),
        ).fetchall()
    return [json.loads(r["report"]) for r in rows]


@app.get("/api/reports/{id}")
def report_by_id(id: str, request: Request):
    owner = session_user(request)
    with db() as c:
        row = c.execute(
            "SELECT report FROM reports WHERE id=? AND user_id=?", (id, owner["id"])
        ).fetchone()
    if not row:
        raise HTTPException(404, "Report not found in your account.")
    return json.loads(row["report"])


@app.post("/api/reports/{id}/save")
def save_report(id: str, request: Request):
    owner = session_user(request)
    with db() as c:
        result = c.execute(
            "UPDATE reports SET saved=1 WHERE id=? AND user_id=?", (id, owner["id"])
        )
        if result.rowcount != 1:
            raise HTTPException(404, "Report not found in your account.")
    return {"ok": True}


@app.delete("/api/reports/{id}")
def remove_report(id: str, request: Request):
    owner = session_user(request)
    with db() as c:
        result = c.execute(
            "DELETE FROM reports WHERE id=? AND user_id=?", (id, owner["id"])
        )
        if result.rowcount != 1:
            raise HTTPException(404, "Report not found in your account.")
    return {"ok": True}


@app.get("/api/media/{id}")
def private_media(id: str, request: Request):
    owner = session_user(request)
    with db() as c:
        row = c.execute(
            "SELECT media,mime FROM reports WHERE id=? AND user_id=?", (id, owner["id"])
        ).fetchone()
    if not row or not row["media"]:
        raise HTTPException(404, "Media not found in your account.")
    return Response(
        bytes(row["media"]),
        media_type=row["mime"],
        headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
    )


@app.get("/api/usage")
def usage(request: Request):
    from datetime import datetime, timezone

    owner = session_user(request)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    with db() as c:
        row = c.execute(
            "SELECT count FROM usage WHERE user_id=? AND month=?", (owner["id"], month)
        ).fetchone()
    return {"count": row["count"] if row else 0, "limit": 100, "month": month}


@app.get("/api/sources")
def sources():
    return {
        "models": [m["info"] for m in MODELS.values()],
        "sources": json.loads((ROOT / "server/source-manifest.json").read_text()),
        "connectors": {
            "huggingFace": "Not connected; network access required",
            "kaggle": "Not connected; network access required",
            "youtubeAPI": "Not connected; API key required",
        },
        "visualPipeline": "Pillow + FFmpeg actual pixel and frame measurements",
    }


@app.get("/api/datasets")
def own_datasets(request: Request):
    owner = session_user(request)
    with db() as c:
        rows = c.execute(
            "SELECT info FROM datasets WHERE user_id=?", (owner["id"],)
        ).fetchall()
    return [json.loads(r["info"]) for r in rows]


@app.post("/api/datasets")
async def upload_dataset(request: Request):
    owner = session_user(request)
    rate_limit(request, "dataset:" + owner["id"], 10)
    data = await json_object(request)
    if data.get("platform") not in ["Instagram", "YouTube"]:
        raise HTTPException(400, "Choose Instagram or YouTube.")
    if data.get("permission") is not True:
        raise HTTPException(400, "Confirm you have permission to use this data.")
    if not isinstance(data.get("csv"), str):
        raise HTTPException(400, "Upload a CSV dataset.")
    try:
        model = train_private_csv(data["csv"], data["platform"])
    except (ValueError, csv.Error) as e:
        raise HTTPException(400, str(e))
    with db() as c:
        c.execute(
            "INSERT INTO datasets VALUES(?,?,?,?) ON CONFLICT(user_id,platform) DO UPDATE SET model=excluded.model,info=excluded.info",
            (
                owner["id"],
                data["platform"],
                pickle.dumps(model),
                json.dumps(model["info"]),
            ),
        )
    return model["info"]


@app.delete("/api/datasets/{platform}")
def remove_dataset(platform: str, request: Request):
    owner = session_user(request)
    with db() as c:
        c.execute(
            "DELETE FROM datasets WHERE user_id=? AND platform=?",
            (owner["id"], platform),
        )
    return {"ok": True}


@app.get("/{path:path}")
def website(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Endpoint not found.")
    dist = ROOT / "dist"
    candidate = (dist / path).resolve()
    if not candidate.is_relative_to(dist):
        raise HTTPException(404, "Page not found.")
    if candidate.is_file():
        return FileResponse(candidate)
    if (dist / "index.html").exists():
        return FileResponse(dist / "index.html")
    raise HTTPException(
        503,
        "Frontend is not built. Run npm run build, or start the Vite development server.",
    )

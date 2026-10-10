# TrendSculpt — creator & brand content intelligence

This is the **new full-stack site** in `/workspace/trendsculpt/site`. The earlier browser-local demo in the parent directory remains separate. This version uses real password-protected server accounts, private durable storage, local trained models, and actual image/video measurements. The live site is https://trendsculpt.onrender.com, deployed from the `codex/trendsculpt-site` branch with server-backed accounts and hosted PostgreSQL.

## Start the site

Requires Node.js 22+, Python 3.12, FFmpeg, FFprobe, and Tesseract OCR with English language data. The Dockerfile installs the media tools; Python dependencies include python-multipart for bounded streamed video uploads. Dependencies are pinned in `package-lock.json` and `server/requirements.lock.txt`.

```sh
cd /workspace/trendsculpt/site
npm ci
python -m venv .venv
.venv/bin/python -m pip install -r server/requirements.lock.txt
OPENBLAS_NUM_THREADS=2 .venv/bin/python scripts/prepare_models.py --skip-metadata
npm run dev
```

Development serves the website on port **5174** and its API on port **8000**. The Vite proxy keeps browser API requests on the same origin. The startup script uses the local virtual environment when available. It stops both processes together and watches backend source changes.

## Hosting without a paid plan

On Render, choose a **Free Web Service**, branch `codex/trendsculpt-site`, root directory `site`, Dockerfile `./Dockerfile`, build context `.`, region Singapore if appropriate for your users, and health check `/api/health`. Leave Docker/start command overrides empty and do not add a disk. Use `PORT=8000`, `COOKIE_SECURE=true`, and `SITE_ORIGIN` set to the exact Render HTTPS origin without a trailing slash. The image defaults to one worker to reduce memory use; optional `WEB_CONCURRENCY=1` makes this explicit.

Render's free filesystem is temporary. Without a hosted database, login, analysis and deletion work, but accounts, reports, uploads and private models can disappear when the instance is replaced or redeployed. Free instances can sleep after inactivity, making the first visit slower.

For saved accounts and reports without a paid Render disk, create a **free PostgreSQL project on [Neon](https://neon.tech)** and copy its connection string into Render's private `DATABASE_URL` environment variable. Keep this URL out of chat, GitHub and frontend variables. Save and redeploy. The app creates its schema automatically and stores users, sessions, reports, uploaded media, quotas and private dataset models in PostgreSQL. Outgoing database connections require TLS certificate and hostname verification. `/api/health` reports `storage: postgresql` when enabled; it never returns credentials.

Neon and Render free-tier usage/storage limits apply. No Neon project is connected by this code change; you create the free project and configure its URL yourself. Switching an existing SQLite deployment to PostgreSQL starts a separate database; existing SQLite records are not automatically migrated. SQLite remains the default for local development.

Start with Home → Get started → signup → save the recovery code → onboarding → analysis → report → compare → save → library. Creator, Brand, and Agency preferences are supported. Individual reports, private datasets, and the entire account can be deleted. Account deletion requires the current password.

## Functional accounts and storage

- Passwords use salted scrypt hashes; raw passwords are not stored.
- Sessions use random tokens in HTTP-only SameSite cookies. Only token hashes are stored in SQLite.
- Login, remember-me, logout, profile/preferences, private reports/media, recovery, deletion, and the monthly quota are server-backed.
- Password recovery uses a **one-time recovery code shown at signup**. Resetting rotates that code and revokes all sessions. Store the replacement code safely.
- Email verification, password-reset email delivery, and notification delivery are **not configured**. The UI does not claim to send them. Email addresses are login identifiers, not verified inbox ownership.
- By default, SQLite, private uploaded media, and private dataset models live in ignored `.data/app.sqlite`. Keep this directory on durable storage for a SQLite deployment. When `DATABASE_URL` is configured, all those records are stored in hosted PostgreSQL instead. Model artifacts live separately in ignored `.models`, so mounting a fresh data volume does not hide the bundled model.
- User content is not kept in localStorage or sessionStorage. Server authorization filters every private operation by its authenticated owner; client-side scores are not trusted.
- The free workspace allows **100 completed analysis requests per UTC calendar month**, enforced on the server. Saving an existing analysis does not consume another credit. Deleting reports does not reset usage. Revisions are new analyses.
- Unsaved analyses are private server drafts and survive reload; they are not listed in the saved library until saved. Account deletion removes drafts too. Backups and operational retention must be configured by the deployment operator.

## Video-specific feedback and long-form YouTube

Choose **YouTube (long-form)** in Analyze content. Upload an MP4 up to **50 MB and 60 minutes**, or choose Text and provide the full transcript when the video is larger. Add the real video title and optionally the description/topic/audience. Paste spoken words or upload `.srt`, `.vtt` or `.txt` subtitles (at most 200,000 characters / 1 MB). Ordered timestamps are validated; malformed subtitles are rejected before consuming an analysis credit.

Video feedback quotes the supplied opening, practical instructions and closing, with their available timestamps. It reviews repeated wording, dense subtitle timing, title/topic alignment, and proposes chapters from actual transcript passages. Untimed text produces section ideas without invented timestamps. Suggested rewrites reuse the creator's wording; they do not fabricate facts or automatically understand visual subjects. Frame OCR and transcript disagreement is a verification prompt, not a claim that subtitles are wrong.

The visual timeline displays actual sampled frames and English OCR estimates, with exposure/contrast measurements. Audio advice cites measured short windows; an audio track is not proof of intelligible speech. Speech is **not automatically transcribed**. The user-supplied transcript may be inaccurate and is labelled accordingly. Long-form scores use a separate title/structure rubric and opening words, avoiding reel caption-length rules. They remain heuristic content review scores, not watch-time predictions.

Long uploads are streamed to a temporary file and deleted after analysis. Saved reports retain their transcript, small frame previews, measurements and recommendations; the full long-form file is not stored in PostgreSQL. One media analysis is processed at a time per server worker, off the event loop, with a bounded processing budget. Highly demanding exports may need compression or transcript-only review. Short-form uploads retain the existing 10 MB / 3-minute limit. All saved samples and source-report reuse are authorized by their account owner.

The live check runs nine browser journeys, including a real 190-second MP4 with audio/overlay text and subtitles, saved evidence across reload, and transcript-only long-form analysis. Reports are published without credentials on the separate `live-check-results` branch. Twelve API tests additionally check transcript-specific rewrites, OCR, sampled audio, malformed timings, original-file disposal, and cross-account source access.

## What the analysis actually does

`server/analysis.py` combines transparent caption/hook/CTA features with local **TF-IDF + ridge regression and similarity retrieval**. Platform matching and relevance/validation gates determine whether historical model evidence adjusts the engagement signal. The adjustment is capped at a 20% blend for that signal. TikTok, LinkedIn, and X currently use the content framework because no platform-specific training observations are bundled.

- **Instagram:** 176 public observations; `(likes + comments + shares + saves) / impressions` as the target.
- **YouTube:** 30,000 deduplicated videos sampled by SHA-256 identity from 2020–2024 India/US Kaggle trending data, pinned version 1346. `(likes + comments) / views` is the target. Channel-group holdout error is 2.681 percentage points versus a 3.693 median baseline. A later unseen-channel test (281 videos after 2024-01-01) has error 2.372 versus 3.015. Both gates must pass before score blending. This selected sample has no verified Shorts label, duration, transcripts or retention ground truth.
- **Kuaishou reference:** KuaiRand-1K random-exposure sample from a pinned Hugging Face mirror, aggregated to 5,432 video groups / 33,335 eligible exposures. Duration-only ridge reference estimates mean watched percentage per random exposure, including skips and replays capped at 3× length. Video-group holdout error is 9.871 versus 12.652 baseline. The completion predictor failed its baseline and was excluded. The reference appears only for measured 5–180 second short videos and never changes an Instagram/YouTube/TikTok score. KuaiRand-derived aggregates and parameters carry CC BY-SA 4.0 attribution and licence terms.
- Validation uses a fixed 25% grouped holdout, keeping identical Instagram captions or YouTube channels out of both sides of the split. The Instagram model's mean absolute error is 1.208 percentage points versus a median-only baseline of 1.414. The YouTube and Kuaishou results above use their own new datasets and targets; errors cannot be compared directly across platforms. Offline holdouts are not a production accuracy guarantee.
- Report evidence includes reference size, similarity, historical-pattern estimate, error-band heuristic, validation, and whether the model contributed to the score. The error band is **not a calibrated confidence interval**.
- Pillow measures actual image exposure, contrast, clipped pixels, edge detail, and resolution. FFmpeg samples the opening, middle and ending of videos; FFprobe reads duration, dimensions, and audio-track presence. Selected frames receive English Tesseract OCR, and three short audio windows measure volume. Each sample has an inspectable preview and timestamp. Uploaded MP4 signatures are validated, and media processing is restricted to local file/pipe protocols.
- The current pipeline does **not** understand visual subjects, transcribe speech, evaluate all video frames, or generate prose with a large language model. Caption/hook/CTA alternatives are dynamic templates grounded in the supplied topic and text. Paste your script/transcript for feedback on spoken hooks.
- Scores and suggestions are guidance. They cannot establish causation or guarantee engagement, virality, retention, revenue, or real-world lifts.

## Data sources and private training

The complete source ledger, pinned revisions, row counts, and SHA-256 checksums are in `server/source-manifest.json`. Public models are trained offline with pinned dependencies and bundled in `server/reference-data/models.joblib`. `prepare_models.py` verifies the artifact checksum and copies it into `.models` without downloads or training. `artifact-manifest.json` pins the artifact and reports validation; compressed source tables, original/derived digests, licences and transformations are included. `scripts/train_public_models.py` retrains offline; `scripts/acquire_public_samples.py --cache /tmp/trendsculpt-public-datasets` reproduces and verifies the YouTube/KuaiRand samples from pinned upstream downloads. Temporary full downloads stay outside the repository and Render.

Bundled sources are [Aman Kharwal's Instagram observations](https://github.com/amankharwal/Website-data/blob/6c3f3ebde421a9d5a57105d47fbd259605faf545/Instagram%20data.csv), [Rishav Sharma's Kaggle YouTube version 1346](https://www.kaggle.com/datasets/rsrishav/youtube-trending-video-dataset/versions/1346), and a [pinned KuaiRand-1K mirror](https://huggingface.co/datasets/numberbeat6/kuairand/tree/b86438794b71ac3ebb95d96e167f52d22edccda7). Compact public tables and trained artifacts are tracked under `server/reference-data`; full upstream downloads stay in a temporary cache. KuaiRand attribution, transformations and its licence are included there. Creator exports, transcripts and private trained models remain in the account-authorized database and are never bundled.

In **Data & models**, upload a CSV downloaded from Kaggle, Hugging Face, a permitted API export, or your own analytics. Each account can keep one private model per supported platform. The import validates and trains it locally; other accounts cannot access it. New analyses prefer the account's matching private model. Removing the private dataset restores the bundled model for future analyses; saved reports preserve their original evidence.

CSV requirements: 20–5,000 valid rows, at least eight distinct captions/channels, maximum 5 MB. Use `caption`, `title`, or `text`; `impressions` for Instagram or `views`/`view_count` for YouTube; and interaction columns such as `likes`, `comments`/`comment_count`, with optional Instagram `shares` and `saves`. Add `channel_id` when combining channels to support grouped validation. Confirm your permission to process uploaded data. Duplicate video/post IDs count once. Content features never contain outcome metrics. For one creator, validation separates content groups; sufficiently diverse multi-channel data separates channels.

Optional `transcript` joins the caption/title as content input. Add `average_percentage_viewed`, or `duration_seconds` plus `average_view_duration_seconds` (`hh:mm:ss` also works), or `watch_time_hours` with views and duration. A separate private watched-percentage model is trained with at least 20 valid viewing records and eight groups. It preserves replay percentages up to 300%, reports skipped invalid viewing values, and hides estimates when validation/relevance is insufficient. Relevant private comparisons can suggest an opening experiment using the actual supplied words. These models do not measure retention in a new video. CSV templates are downloadable in Data & models and `public/templates`. Training is bounded and offloaded, sharing the single heavy-processing slot with media analysis.

Optional command-line importers:

```sh
.venv/bin/python scripts/import_external.py kaggle owner/dataset --file data.csv --output .data/imports/kaggle.csv
.venv/bin/python scripts/import_external.py huggingface owner/dataset path/to/data.csv --output .data/imports/hf.csv
.venv/bin/python scripts/import_external.py youtube --region US --pages 2 --output .data/imports/youtube.csv
```

The YouTube importer needs `YOUTUBE_API_KEY`; private Hugging Face datasets may need `HF_TOKEN`, and Kaggle may need `KAGGLE_USERNAME`/`KAGGLE_KEY`. Supply private credentials through secure server environment settings, never frontend variables or chat. The bundled public sample acquisitions from Kaggle and the pinned Hugging Face mirror were verified end-to-end without private credentials. These standalone optional live importers are separate and have not all been exercised; no live YouTube key or creator API accounts are connected. Zenodo remains outside the current runtime allowlist, so its domain requirement was saved for environment review. The working bundled data and private CSV uploads do not depend on it.

## Build and publish

```sh
npm run build
.venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

The Python server serves the compiled frontend, private API, and client-side routes from one origin. A static-only host is insufficient for accounts, persistence, and analysis. Configure an HTTPS domain, `SITE_ORIGIN=https://your-domain`, `COOKIE_SECURE=true`, and either hosted PostgreSQL via `DATABASE_URL` or durable `.data` storage for SQLite. `.env.example` documents variables; the application expects deployment environment injection rather than loading that example automatically. Use a single host/durable volume for SQLite. Docker starts `python -m server.start`, respecting `PORT` and `WEB_CONCURRENCY` (default one worker).

A Dockerfile is supplied for a full-stack deployment. It builds the frontend, installs the pinned Python stack and FFmpeg, installs checksum-verified offline model artifacts, and runs as an unprivileged user. The earlier image build, six browser journeys and account/session/report/quota restart checks passed before this dataset update; current validation is reported separately. Configure the actual hosting domain, HTTPS and durable storage before publication.

```sh
docker build -t trendsculpt .
docker run --rm -p 8000:8000 -v trendsculpt-data:/app/.data \
  -e SITE_ORIGIN=https://your-domain -e COOKIE_SECURE=true trendsculpt
```

For a managed proxy, pass Docker's standard proxy build arguments. If that proxy uses a platform-provided CA, supply its trusted public certificate bundle with `--secret id=environment_ca,src=/path/to/trusted-ca-bundle.crt`. The optional secret extends trust for npm, pip during the build; it is not copied into the runtime image. Keep TLS verification enabled. This environment also required an explicit Docker `--add-host` mapping for its proxy hostname; use the environment's supported resolution rather than a hard-coded address.

The public site is https://trendsculpt.onrender.com. Render automatically deploys the source branch; the live browser workflow waits for the exact deployment commit before checking it. Publishing the **cloud environment snapshot** is separate from publishing this website.

## Validation

```sh
npm run build
npm test
.venv/bin/python -m unittest server.test_app server.test_models -v
npm run test:e2e
```

To exercise an already running compiled production server instead of starting Vite, set `TRENDSCULPT_TEST_URL` to that server's origin when running `npm run test:e2e`. The current suite includes three frontend analysis tests, twelve API tests, six model/data tests and nine browser journeys. The new journey exercises private transcript/watch-time training, an actual 10-second video, separate cross-platform reference evidence, saved reports, template download and dataset deletion. Google Chrome is used for MP4 playback in live CI.

API tests use an isolated temporary database. Browser tests cover real signup/login, one-time recovery, persisted reports, comparisons, profile/preferences, private CSV training/deletion, image/video measurement, confirmed deletion, mobile/tablet layouts, public pages, and cross-account browser-history isolation. Chromium is selected automatically when installed; otherwise use Playwright's verified browser installation.

Frontend architecture: reusable page/components in `src/main.tsx`, a typed API adapter in `src/store.ts`, sample-only scoring in `src/engine.ts`, and local font assets. Runtime scoring lives on the server. Backend modules separate authentication/storage, analysis/media processing, and private dataset training.

PostgreSQL storage was exercised using a real, isolated local PostgreSQL 17 database: all seven API tests and six browser journeys passed. Accounts, sessions, saved reports, uploaded images and quotas also survived replacing the application process and its local data directory. The one-worker Docker image passed signup, actual video analysis, report saving and account deletion with a 512 MB memory limit; this is a bounded smoke test, not a capacity guarantee for larger workloads. To reproduce the PostgreSQL API checks, use `TRENDSCULPT_TEST_DATABASE_URL` with a loopback-only PostgreSQL database named `*_test` and run the server tests. The tests intentionally ignore a deployment's ordinary `DATABASE_URL` to avoid destroying real records. The adapter permits non-TLS connections only for an explicit loopback test; hosted connections always verify TLS. Live browser checks have exercised the configured hosted PostgreSQL connection. Its private connection URL stays in Render environment settings.

Each cloud task already runs in an isolated environment. Use the existing checkout and this `site` directory; do not create worktrees unless explicitly requested. Preserve private data and user changes when refreshing setup.

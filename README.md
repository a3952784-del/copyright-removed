# ClipFix AI — website starter

A self-hostable MVP for uploading videos you own or are authorized to edit, applying FFmpeg effects, and exporting MP4.

## Included
- Responsive dark UI
- Account registration/login (SQLite + password hashing)
- Video upload (up to 250 MB)
- Speed, pitch, zoom/crop controls
- Optional sound-effect audio upload/mix
- MP4 export and download
- Direct HTTPS video-file URL import (does not rip YouTube watch pages)
- Dockerfile with FFmpeg installed

## Run locally
Requires Python 3.11+ and FFmpeg for non-Docker runs.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
export CLIPFIX_SECRET_KEY='replace-with-a-long-random-secret'
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

With Docker:
```bash
docker build -t clipfix-ai .
docker run -p 8000:8000 -e CLIPFIX_SECRET_KEY='replace-this-secret' clipfix-ai
```

## Before public launch
This is an MVP starter, not production-hardened. Add HTTPS, CSRF protection, rate limiting, upload scanning, a background job queue, cloud object storage, account recovery, privacy/terms pages, and robust SSRF protection for URL import. Use persistent storage for `uploads/`, `exports/`, and `clipfix.sqlite3`.

**Copyright:** Effects do not remove copyright or prevent claims. Only process content you own, have permission to edit, or can legally use. The app intentionally does not download YouTube watch pages or bypass platform restrictions.

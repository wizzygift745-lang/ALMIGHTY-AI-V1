# ALMIGHTY AI — Public Deployment Guide

Goal: a public URL anyone can open, with auth & admin pages protected.
The app is fully self-contained (SQLite + local storage) so it deploys anywhere.

> Inside your Arena workspace the app is already served as a **live preview**
> at `https://8080-<SANDBOX_ID>.e2b.app` (shown in the preview panel).
> Arena previews are session-scoped, so for a permanent public home use any host below.

---

## Option A — Render (easiest, free tier OK)

1. **Push to GitHub**
   ```bash
   git init
   git add -A
   git commit -m "ALMIGHTY AI MVP"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USER>/almighty-ai.git
   git push -u origin main
   ```
   (The repo is already `git init`-ed and committed in your workspace — just add the remote.)
2. On [render.com](https://render.com): **New → Web Service** → connect the repo.
3. Settings:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python run.py`
   - Environment: `PORT=10000` (or any; Render injects `$PORT`), optional:
     `ADMIN_PASSWORD=<choose-a-strong-password>` (used only on the very first boot)
   - Add a **persistent disk** mounted at `/app/data` (Render dashboard → Disks) so the DB,
     generations and the admin password survive restarts.
4. Deploy → your public URL: `https://almighty-ai.onrender.com`. Done.

## Option B — Railway

1. Push repo to GitHub (same as above).
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Railway auto-detects the Dockerfile (or set start command `python run.py`).
4. Add a **volume** mounted at `/app/data`. Set `PORT=8080`.
5. Public URL via **Settings → Networking → Generate Domain**.

## Option C — Fly.io (Docker, great for GPU-adjacent future)

```bash
fly launch            # accept defaults, app name e.g. almighty-ai
fly volumes create almighty_data --region <nearest>
# add to fly.toml:
#   [mounts]
#     source = "almighty_data"
#     destination = "/app/data"
fly deploy
fly open              # public URL
```

## Option D — Any VPS (DigitalOcean / Hetzner / AWS EC2)

```bash
git clone https://github.com/<YOUR_USER>/almighty-ai.git
cd almighty-ai
docker build -t almighty-ai .
docker run -d --name almighty-ai -p 80:8080 \
  -v $(pwd)/data:/app/data \
  -e ADMIN_PASSWORD='<choose-a-strong-password>' \
  almighty-ai
```
Point your domain at the server (A record) and put nginx/Caddy with TLS in front if desired.

---

## After every deploy

1. Open the URL → public landing page loads with **no login required** ✅
2. Log in with the owner email `amulukugodswill11@gmail.com` and the password printed in the
   server log on first boot (or the `ADMIN_PASSWORD` you set) — also stored at
   `data/initial_admin_password.txt` on the server, never in the frontend.
3. Immediately change it: **Admin Console → your account → change password** (`/api/auth/me/password`).
4. Verify protection: `/api/admin/*` returns 401/403 without an admin token.

## Notes

- **No external AI API required.** Generation runs on ALMIGHTY dev engines; when trained
  ALMIGHTY weights exist they slot in behind `app/engines/*` with zero frontend changes.
- Videos are MP4 when ffmpeg is present (included in the Dockerfile), GIF otherwise.
- Scaling: SQLite is fine to ~thousands of users; migrate to Postgres + Redis queue +
  object storage per ARCHITECTURE.md §8 when you cross that.

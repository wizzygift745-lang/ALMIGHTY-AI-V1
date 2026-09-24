# ALMIGHTY AI ⚡

**Independent AI. Infinite creation.**

ALMIGHTY AI is designed as an independent AI technology platform — not a wrapper around
other companies' APIs. It ships with an internal model abstraction (`ALMIGHTY_MODEL_ENGINE`),
an orchestrator, a quality-evaluation system, a character-identity system, a story-to-video
pipeline, RBAC security, credits/quota management, and a full admin console — architected so
that today's development engines are progressively replaced by trained ALMIGHTY weights
behind the exact same interfaces.

```
TARGET:   User → ALMIGHTY AI → ALMIGHTY models → ALMIGHTY infrastructure
(NOT:     User → ALMIGHTY AI → Other company's API)
```

## What ships in this MVP (Phase 1 + parts of Phase 2)

| Area | Status |
|---|---|
| Landing page (public) | ✅ |
| Auth (register/login, PBKDF2-hashed passwords, HMAC-signed tokens) | ✅ |
| Owner account `amulukugodswill11@gmail.com` (seeded at first boot, full admin) | ✅ |
| ALMIGHTY IMAGE — text→image, image→image, styles, seeds, guidance, aspect | ✅ dev engine |
| ALMIGHTY VIDEO — text→video, camera paths, motion strength | ✅ dev engine |
| ALMIGHTY ANIME — anime key visuals, cel-shading | ✅ dev engine |
| ALMIGHTY 2D — walk/run/fight/dance cycles, expressions, dialogue, camera | ✅ dev engine |
| ALMIGHTY STORY — story → storyboard → scenes → subtitles → final video | ✅ dev engine |
| ALMIGHTY UPSCALE — 2×/4× enhancement with detail recovery | ✅ dev engine |
| Character identity system (CHARACTER IDs, locked seeds, traits) | ✅ |
| Projects, generation history, downloads | ✅ |
| ALMIGHTY ORCHESTRATOR — routing, evaluation, auto-improve retry | ✅ |
| Quality evaluation per artifact (score + metrics) | ✅ |
| Credits & quotas (daily free credits, per-kind costs, auto-refund on failure) | ✅ |
| Admin console: users, models, versions, datasets, jobs, logs, settings, analytics | ✅ |
| Temporary provider adapter layer (isolated, OFF by default) | ✅ |
| Trained ALMIGHTY weights, distributed GPU training, dataset pipelines | 🗓 Phases 3–4 |

## Quick start

```bash
pip install -r requirements.txt
python run.py            # binds 0.0.0.0:8080
```

First boot seeds the **owner account** for `amulukugodswill11@gmail.com`:
the generated password is printed once in the server log and saved server-side in
`data/initial_admin_password.txt` (mode 600). It is **never** present in frontend code.
Set `ADMIN_PASSWORD=<your-password>` (env) before first boot to choose it yourself.
Log in → Admin Console.

### Configuration (environment variables)

| Var | Default | Meaning |
|---|---|---|
| `PORT` | 8080 | HTTP port |
| `HOST` | 0.0.0.0 | bind address (keep 0.0.0.0 for containers/proxies) |
| `ALMIGHTY_ADMIN_EMAIL` | amulukugodswill11@gmail.com | owner account email |
| `ADMIN_PASSWORD` | *(generated)* | owner password on first boot only |
| `ALMIGHTY_DATA_DIR` | ./data | DB + generations + uploads |

## Architecture overview

See **ARCHITECTURE.md** for the full engineering design (model registry, training
infrastructure plan, data engine, orchestrator, evaluation, security, scalability).

## Public deployment

See **DEPLOY.md** — exact steps for GitHub + Render / Railway / Fly.io / VPS with Docker.
`Dockerfile` included (uses ffmpeg for MP4 output; GIF fallback otherwise).

## Security notes

- Passwords: PBKDF2-HMAC-SHA256, per-user salt, 200k iterations.
- Sessions: stateless HMAC-signed tokens; secret generated server-side (`data/secret.key`, never exposed to browser).
- RBAC enforced **server-side** on every admin endpoint (`owner` / `admin` / `user`).
- Uploads validated and re-encoded through PIL (type spoofing neutralized), 10 MB cap.
- Credits/quota enforced per user; failed generations are refunded automatically.
- Full audit log of auth, generation, and admin actions.

## Repository layout

```
almighty-ai/
├── run.py                  # server launcher
├── app/
│   ├── main.py             # FastAPI app, SPA serving
│   ├── config.py           # env-driven config
│   ├── db.py               # SQLite schema + seeds (users/models/datasets/settings/logs)
│   ├── security.py         # passwords, tokens, RBAC
│   ├── registry.py         # ALMIGHTY_MODEL_ENGINE registry access
│   ├── orchestrator.py     # pipeline: understand→route→generate→evaluate→improve
│   ├── evaluation.py       # internal quality evaluation
│   ├── fonts.py
│   ├── routes_auth.py  routes_generate.py  routes_admin.py
│   └── engines/            # ALMIGHTY IMAGE / VIDEO / ANIME / 2D / STORY / UPSCALE
│       └── providers.py    # TEMPORARY external provider layer (isolated, OFF)
├── static/                 # SPA frontend (landing, studios, admin console)
├── Dockerfile
├── requirements.txt
├── ARCHITECTURE.md
└── DEPLOY.md
```

© ALMIGHTY AI — built to become fully proprietary AI infrastructure.

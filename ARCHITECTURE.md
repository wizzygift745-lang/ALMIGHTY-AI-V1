# ALMIGHTY AI — Engineering Architecture

Long-term target: **User → ALMIGHTY AI → ALMIGHTY Models → ALMIGHTY Infrastructure.**
External providers are *temporary* and architecturally isolated; every subsystem below has a
concrete path to proprietary technology.

---

## 1. ALMIGHTY_MODEL_ENGINE (model abstraction)

Implemented in `app/registry.py` + `app/db.py` (tables `models`, `model_versions`).

Every model row carries: **Model ID, version, architecture, capabilities, max resolution,
max duration, VRAM requirement, inference config, safety config, status.**
The registry supports:

- **Registry & routing** – `registry.route(kind)` resolves task kind → model.
- **Versions** – `model_versions` records every status/version change (rollback trail).
- **Statuses & rollback** – admin can set `online / development / planned / offline`;
  rolling a model back = flipping status/version; the orchestrator refuses to route to
  non-online models.
- **Config** – per-model JSON inference config (steps, fps, rig id…).
- **Monitoring** – every routing decision and generation is audit-logged with model id.
- **Evaluation** – `evaluation.py` scores are stored per job, giving per-model benchmark
  history for Phase 4.

Model family seeded today (dev engines live, trained weights pending):

```
ALMIGHTY IMAGE · VIDEO · ANIME · 2D · MOTION · UPSCALE · STORY
```

New families (AUDIO, VOICE, MUSIC, 3D, AGENTS…) are added by inserting registry rows +
implementing the engine interface — no core changes. This is the seam where Phase 3
plugs in trained weights.

## 2. Engines (Phase 1/2 dev backends, Phase 3 swap points)

| Engine | MVP backend (deterministic, zero external APIs) | Phase 3 replacement |
|---|---|---|
| `image_engine.py` | procedural latent-renderer (palette hashing, layered composition, style post-FX, character rig) | ALMIGHTY IMAGE diffusion model |
| `video_engine.py` | temporally-coherent frame renderer + camera-path system + ffmpeg/GIF assembly | ALMIGHTY VIDEO temporal model |
| `twod_engine.py` | parametric rig animator (walk/run/fight/dance/jump/talk, expressions, lip-sync, dialogue bubbles) | learned cel-animation synthesis |
| `story_engine.py` | genre detection → storyboard planner → per-scene generation → Ken Burns + burned subtitles → assembly | ALMIGHTY STORY planner + ALMIGHTY VIDEO scenes |
| `upscale_engine.py` | Lanczos 2–4× + unsharp detail recovery | ALMIGHTY UPSCALE network |

Determinism contract: same `(prompt, seed, style, character traits)` ⇒ same output.
This is what makes **character consistency** possible pre-training; Phase 3 upgrades to
identity embeddings while keeping the same trait/seed contract.

### Temporary provider layer
`engines/providers.py` — an isolated adapter base (`ProviderAdapter`) + one example
OpenAI-compatible stub. Disabled unless admin setting `allow_external_providers=on` **and**
server-side env credentials exist. Credentials never reach the browser. Deleting the file
breaks nothing else. *External = temporary; ALMIGHTY = long-term.*

## 3. ALMIGHTY ORCHESTRATOR

`app/orchestrator.py` — threaded worker pipeline per job:

```
request → prompt understanding → task classification → registry model selection
        → generation (dev engine or temporary provider)
        → quality evaluation (evaluation.py)
        → auto-improve: if score < quality_threshold → re-generate with new seed/params,
          keep best → finalize
```

Each stage writes `jobs.step/progress` (streamed live to the UI) and audit logs.

## 4. Quality evaluation (`evaluation.py`)

Per-image metrics: luminance, contrast, sharpness (edge energy), colorfulness,
prompt-alignment heuristic → composite score 0–100.
Per-video additions: motion energy + temporal consistency (detects frozen or flickering clips).
Stored on every job → future model versions are benchmarked against real production scores.
Phase 3/4 adds learned evaluators (face/hand quality, text rendering, scene continuity)
behind the same interface.

## 5. Character identity system

`characters` table: `CHARACTER CODE (CHR-XXXXXX)`, name, description, **traits**
(skin/hair/outfit/accent + future identity embeddings), and a **locked seed**.
Studios accept `character_id`; engines render the shared rig from traits, so a character is
recognizable across images, anime scenes, 2D animation and story scenes.
Phase 3: traits are replaced/augmented by an identity embedding extracted once per character.

## 6. Training infrastructure (Phase 4 design)

Not yet active; schema + processes reserved:

- **Data engine** — `datasets` table: Dataset ID, version, source, license info, quality
  score, safety status (pending/cleared/restricted), training eligibility. **Training is
  blocked until a dataset is rights-cleared** (`training_eligible` flag). Pipeline steps to
  implement on top of this registry: ingestion → cleaning → filtering → dedup → caption
  generation → annotation → data versioning.
- **Training jobs** — future `training_jobs` + `checkpoints` tables; experiment tracking via
  `logs` + `model_versions`; checkpoint recovery by design (every stage persists state).
- **Distributed training** — target topology: launcher with torchrun/accelerate across
  multi-GPU/multi-node, mixed precision (bf16), gradient sharding; containerized per the
  Dockerfile pattern; autoscaling via GPU queues (see §8).

## 7. Security model

- Authentication: PBKDF2 (200k iters) + per-user salt; HMAC-signed session tokens with
  expiry; server secret in `data/secret.key` (0600), never in frontend.
- Authorization: roles `owner > admin > user`; **every** `/api/admin/*` endpoint guarded
  server-side; owner account is immutable from other accounts.
- Quotas: per-kind credit costs, daily grant, refunds on failure, HTTP 402 when exhausted.
- Uploads: PIL verification + re-encode sanitize, 10 MB cap; files stored outside web root,
  served only through authenticated routes (`/api/files/{job}`) with ownership checks.
- Audit: auth events, generations, admin actions, model/dataset/setting changes.
- Secrets/credentials (provider keys, infra creds) live in server env only.

## 8. Scalability plan

Components are already separated at the code level and can scale independently:

```
Frontend (static SPA)   → CDN / any static host
API (FastAPI)           → N horizontal replicas (stateless; SQLite → Postgres)
Auth                    → part of API (stateless tokens) → replicas scale freely
Generation queue        → today: in-process threads; next: Redis/DB queue + workers
Model inference         → GPU worker pool, model containers, load balancing,
                          autoscaling on queue depth, model weight caching
Storage                 → object storage (S3-compatible) for generations/datasets
Database                → Postgres (+ read replicas at 100k+ users)
Billing/Analytics       → derived from jobs/users tables; separate services later
```

Scaling milestones: 100 users (current stack) → 1k (Postgres + queue workers) →
100k (replicated API, GPU pool, object storage, CDN) → millions (multi-region,
per-tenant sharding, dedicated inference clusters).

## 9. Roadmap mapping

| Phase | Contents | Where in code |
|---|---|---|
| 1 MVP | auth, admin, dashboard, image/video gen, projects, history, storage, model abstraction | ✅ shipped |
| 2 Creator | anime, 2D, characters, storyboards, story→video, captions, creator presets (9:16/16:9/1:1) | ✅ core shipped; timeline editor pending |
| 3 Proprietary AI | trained ALMIGHTY IMAGE/VIDEO/ANIME/2D/MOTION | engine swap points (engines/*) |
| 4 Research | datasets, distributed training, evaluation, auto model improvement | §6 + evaluation.py |
| 5 Ecosystem | audio, voice, music, 3D, lip sync, motion capture, agents, world simulation, real-time | registry rows + new engines |

---
*Every external dependency has an expiry date; every internal interface has a future.*

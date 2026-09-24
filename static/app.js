/* ============================================================
   ALMIGHTY AI — frontend application
   Single-page app. All admin capability is enforced server-side;
   this UI only *shows* admin areas to authenticated owner/admins.
   ============================================================ */

const APP = document.getElementById("app");
let state = { token: localStorage.getItem("almighty_token") || null, user: null, poller: null };

/* ---------------- helpers ---------------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root = APP) => root.querySelector(sel);

function toast(msg, ok = true) {
  let t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  if (!ok) t.style.borderColor = "#8a2540";
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add("show"));
  setTimeout(() => { t.classList.remove("show"); setTimeout(() => t.remove(), 300); }, 2600);
}

async function api(path, opts = {}) {
  const headers = {};
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  let body = opts.body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json"; body = JSON.stringify(body);
  }
  const res = await fetch("/api" + path, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  if (res.status === 401 && state.token) { doLogout(true); throw { status: 401, detail: "Session expired" }; }
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw { status: res.status, detail: data.detail || "Request failed" };
  return data;
}

const fileUrl = (jobId) => `/api/files/${jobId}?token=${encodeURIComponent(state.token || "")}`;
const fmtBytes = (b) => b > 1e9 ? (b / 1e9).toFixed(2) + " GB" : b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : (b / 1e3).toFixed(0) + " KB";
const timeAgo = (iso) => {
  if (!iso) return ""; const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 90) return "just now"; if (d < 3600) return Math.floor(d / 60) + "m ago";
  if (d < 86400) return Math.floor(d / 3600) + "h ago"; return Math.floor(d / 86400) + "d ago";
};
const LOGO = `<svg viewBox="0 0 64 64"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#f7c948"/><stop offset=".5" stop-color="#ee5d6c"/><stop offset="1" stop-color="#7c5cff"/>
</linearGradient></defs><rect width="64" height="64" rx="14" fill="#0d1020"/>
<path d="M32 8 52 52H40l-8-18-8 18H12z" fill="url(#lg)"/></svg>`;

/* ---------------- session ---------------- */
function saveSession(token, user) {
  state.token = token; state.user = user;
  localStorage.setItem("almighty_token", token);
}
function doLogout(silent) {
  state.token = null; state.user = null;
  localStorage.removeItem("almighty_token");
  if (!silent) { location.hash = "#/"; render(); }
}
async function refreshMe() {
  try { state.user = await api("/auth/me"); return true; }
  catch (_) { doLogout(true); return false; }
}

/* ============================================================
   LANDING PAGE (public — no login required)
   ============================================================ */
function viewLanding() {
  const fams = [
    ["IMAGE", "ALMIGHTY IMAGE", ["Text → image", "Image → image", "Editing · inpainting · outpainting", "Character & style consistency"]],
    ["VIDEO", "ALMIGHTY VIDEO", ["Text → video", "Image → video", "Camera control", "Motion strength control"]],
    ["ANIME", "ALMIGHTY ANIME", ["Anime images & video", "Manga & cinematic anime", "Character reuse across a story", "Genres: action, horror, romance…"]],
    ["2D", "ALMIGHTY 2D", ["Walk / run / fight / dance cycles", "Expressions & lip sync", "Dialogue bubbles", "Camera moves & transitions"]],
    ["MOTION", "ALMIGHTY MOTION", ["Pose control", "Motion transfer", "Camera paths", "Character movement"]],
    ["UPSCALE", "ALMIGHTY UPSCALE", ["Image enhancement", "Super-resolution up to 4×", "Detail recovery", "Frame interpolation (roadmap)"]],
    ["STORY", "ALMIGHTY STORY", ["Script understanding", "Auto storyboard", "Scene planning", "Story → finished video"]],
  ];
  APP.innerHTML = `
  <nav class="land-nav">
    <a class="logo" href="#/">${LOGO}<span>ALMIGHTY&nbsp;AI</span></a>
    <div style="display:flex;gap:10px">
      <a class="btn ghost small" href="#/login">Log in</a>
      <a class="btn small" href="#/register">Get started</a>
    </div>
  </nav>

  <header class="hero">
    <span class="chip">⚡ Independent AI technology platform — not a wrapper</span>
    <h1 style="margin-top:18px">Create anything with<br><span class="grad-text">ALMIGHTY AI</span></h1>
    <p class="sub">Our own model family — ALMIGHTY IMAGE, VIDEO, ANIME, 2D, MOTION, UPSCALE and STORY —
    running toward fully proprietary AI infrastructure. Images, videos, anime, 2D animation and
    complete story-to-video production with characters that stay consistent everywhere.</p>
    <div class="cta">
      <a class="btn" href="#/register">Start creating — it's free</a>
      <a class="btn ghost" href="#/login">Open studio</a>
    </div>
    <div class="pill-row">
      <span class="chip">🎬 Story → Video</span><span class="chip">🧑‍🎤 Character consistency</span>
      <span class="chip">🎨 7 model families</span><span class="chip">📱 Creator presets 9:16 · 16:9 · 1:1</span>
    </div>
  </header>

  <section class="section">
    <h2>One platform. <span class="grad-text">Seven proprietary model families.</span></h2>
    <p class="lede">Every engine is built behind ALMIGHTY_MODEL_ENGINE — our internal model abstraction with
    registry, versioning, routing, evaluation and rollback. Development engines ship today; trained
    ALMIGHTY weights drop in behind the same interface tomorrow.</p>
    <div class="grid c3">${fams.map(f => `
      <div class="card">
        <div class="fam">ALMIGHTY ${f[0]}</div>
        <h3>${f[1]}</h3>
        <ul>${f[2].map(x => `<li>${x}</li>`).join("")}</ul>
      </div>`).join("")}
    </div>
  </section>

  <section class="section">
    <h2>The <span class="grad-text">ALMIGHTY ORCHESTRATOR</span></h2>
    <p class="lede">Every request flows through our internal orchestrator: it understands the prompt,
    classifies the task, routes it to the right ALMIGHTY model, evaluates quality, and automatically
    improves results that miss the bar.</p>
    <div class="pipe">
      ${["User request", "Prompt understanding", "Task classification", "Model selection",
        "Generation", "Quality evaluation", "Auto-improve", "Final result"]
        .map((s, i, a) => `<span class="step">${s}</span>${i < a.length - 1 ? '<span class="arr">→</span>' : ""}`).join("")}
    </div>
  </section>

  <section class="section">
    <h2>Built for <span class="grad-text">creators</span></h2>
    <div class="grid c4">
      <div class="card"><h3>📱 Shorts & Reels</h3><p>9:16 presets, captions and pacing for YouTube Shorts, TikTok and Instagram.</p></div>
      <div class="card"><h3>🎥 Faceless channels</h3><p>Story-to-video with narration-ready scenes, subtitles and thumbnails.</p></div>
      <div class="card"><h3>⛩️ Anime studios</h3><p>Create a character once, reuse it across an entire anime story.</p></div>
      <div class="card"><h3>🧸 2D animation</h3><p>Walk cycles, fights, expressions and dialogue — animated from a rig.</p></div>
    </div>
  </section>

  <section class="section">
    <h2>The road to <span class="grad-text">fully proprietary AI</span></h2>
    <p class="lede">ALMIGHTY AI is designed to remove external dependencies step by step —
    ending at our own models, training pipelines and inference infrastructure.</p>
    <div class="phases">
      <div class="phase"><b>PHASE 1</b><span>MVP — auth, dashboard, image & video generation, projects, history, model abstraction layer. <em style="color:#4ade80">(live now)</em></span></div>
      <div class="phase"><b>PHASE 2</b><span>Creator platform — anime, 2D animation, character system, storyboards, story-to-video, captions, timeline.</span></div>
      <div class="phase"><b>PHASE 3</b><span>Proprietary AI — trained ALMIGHTY IMAGE · VIDEO · ANIME · 2D · MOTION models replace dev engines.</span></div>
      <div class="phase"><b>PHASE 4</b><span>Research platform — dataset engine, distributed GPU training, evaluation, automatic model improvement.</span></div>
      <div class="phase"><b>PHASE 5</b><span>Full ecosystem — audio, voice, music, 3D, agents, world simulation, real-time generation.</span></div>
    </div>
  </section>

  <section class="section" style="text-align:center">
    <div class="card" style="padding:44px 24px">
      <h2 style="justify-content:center">Ready to create with <span class="grad-text">ALMIGHTY AI</span>?</h2>
      <p class="lede" style="margin:10px auto 24px">Free daily credits. No credit card. Your characters, your stories, your worlds.</p>
      <a class="btn" href="#/register">Create your free account</a>
    </div>
  </section>

  <footer class="lf">ALMIGHTY AI — independent AI research &amp; generation platform ·
    Security-first: hashed passwords, role-based access, encrypted server-side secrets ·
    © ${new Date().getFullYear()} ALMIGHTY AI</footer>`;
}

/* ============================================================
   AUTH PAGES
   ============================================================ */
function viewAuth(mode) {
  const isLogin = mode === "login";
  APP.innerHTML = `
  <div class="auth-wrap"><div class="auth">
    <a class="logo" href="#/">${LOGO}<span>ALMIGHTY&nbsp;AI</span></a>
    <h2>${isLogin ? "Welcome back" : "Create your account"}</h2>
    <div class="mut">${isLogin ? "Log in to your studio." : "Free daily credits. Start creating in seconds."}</div>
    <form id="authForm">
      ${isLogin ? "" : `<label>NAME</label><input name="name" required minlength="2" placeholder="Your name">`}
      <label>EMAIL</label><input name="email" type="email" required placeholder="you@example.com">
      <label>PASSWORD</label><input name="password" type="password" required minlength="8"
        placeholder="${isLogin ? "Your password" : "At least 8 characters"}">
      <div class="err" id="authErr"></div>
      <button class="btn" type="submit">${isLogin ? "Log in" : "Create account"}</button>
    </form>
    <div class="switch">${isLogin
      ? `New here? <a href="#/register">Create an account</a>`
      : `Already have an account? <a href="#/login">Log in</a>`}</div>
  </div></div>`;
  $("#authForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target); const err = $("#authErr"); err.textContent = "";
    const btn = e.target.querySelector("button"); btn.disabled = true;
    try {
      const data = await api("/auth/" + (isLogin ? "login" : "register"), {
        body: isLogin ? { email: f.get("email"), password: f.get("password") }
                      : { name: f.get("name"), email: f.get("email"), password: f.get("password") } });
      saveSession(data.token, data.user);
      location.hash = "#/dashboard"; render();
    } catch (ex) { err.textContent = ex.detail || "Something went wrong"; }
    btn.disabled = false;
  });
}

/* ============================================================
   APP SHELL
   ============================================================ */
const NAV = [
  { sec: "CREATE" },
  { hash: "#/dashboard", ico: "◆", label: "Dashboard" },
  { hash: "#/studio/image", ico: "🖼", label: "Image Studio", kind: "image" },
  { hash: "#/studio/video", ico: "🎬", label: "Video Studio", kind: "video" },
  { hash: "#/studio/anime", ico: "⛩", label: "Anime Studio", kind: "anime" },
  { hash: "#/studio/2d", ico: "🧸", label: "2D Animation", kind: "2d" },
  { hash: "#/studio/story", ico: "📖", label: "Story → Video", kind: "story" },
  { hash: "#/studio/upscale", ico: "🔍", label: "Upscale", kind: "upscale" },
  { sec: "LIBRARY" },
  { hash: "#/characters", ico: "🧑‍🎤", label: "Characters" },
  { hash: "#/projects", ico: "🗂", label: "Projects" },
  { hash: "#/history", ico: "🕘", label: "History" },
];
const NAV_ADMIN = [{ sec: "ADMINISTRATION" }, { hash: "#/admin", ico: "🛡", label: "Admin Console" }];

function shell(activeHash, title, innerHtml) {
  const u = state.user;
  const nav = [...NAV, ...(u && ["owner", "admin"].includes(u.role) ? NAV_ADMIN : [])];
  APP.innerHTML = `
  <div class="shell">
    <aside class="side" id="side">
      <a class="logo" href="#/" style="margin:2px 10px 14px">${LOGO}<span>ALMIGHTY&nbsp;AI</span></a>
      ${nav.map(n => n.sec ? `<div class="sec">${n.sec}</div>` : `
        <a class="nav-item ${activeHash === n.hash ? "active" : ""}" href="${n.hash}">
          <span class="ico">${n.ico}</span>${n.label}</a>`).join("")}
      <div style="flex:1"></div>
      <div style="padding:10px;color:var(--dim);font-size:11.5px">
        ${u ? esc(u.name) + " · " + u.role : ""}<br>
        <a href="#" id="logoutLink" style="color:var(--rose)">Log out</a>
      </div>
    </aside>
    <div class="main">
      <div class="topbar">
        <button class="hamburger" id="burger">☰</button>
        <div class="title">${title}</div>
        <div class="credits" title="Generation credits — refresh daily">⚡ ${u ? (u.credits < 0 ? "∞" : u.credits) : "…"}</div>
        <div class="avatar">${u ? esc(u.name[0]).toUpperCase() : "?"}</div>
      </div>
      <div class="content" id="content">${innerHtml}</div>
    </div>
  </div>`;
  $("#logoutLink").addEventListener("click", (e) => { e.preventDefault(); doLogout(); });
  $("#burger").addEventListener("click", () => $("#side").classList.toggle("open"));
  document.addEventListener("click", (e) => {
    const s = $("#side"); if (s && s.classList.contains("open") && !s.contains(e.target) && e.target.id !== "burger")
      s.classList.remove("open");
  });
  return $("#content");
}

/* ============================================================
   DASHBOARD
   ============================================================ */
async function viewDashboard() {
  const c = shell("#/dashboard", "Dashboard", `
    <div class="stat-grid">
      <div class="stat"><div class="n" id="stJobs">…</div><div class="l">Generations</div></div>
      <div class="stat"><div class="n" id="stChars">…</div><div class="l">Characters</div></div>
      <div class="stat"><div class="n" id="stProj">…</div><div class="l">Projects</div></div>
      <div class="stat"><div class="n">${state.user.credits < 0 ? "∞" : state.user.credits}</div><div class="l">Credits today</div></div>
    </div>
    <div class="grid c2">
      <div class="panel">
        <h3>Quick start</h3>
        <div class="hint">Jump straight into a studio</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px">
          ${[["#/studio/image", "🖼 Generate an image"], ["#/studio/video", "🎬 Generate a video"],
             ["#/studio/anime", "⛩ Anime scene"], ["#/studio/2d", "🧸 2D animation"],
             ["#/studio/story", "📖 Story → Video"], ["#/characters", "🧑‍🎤 Create a character"]]
            .map(([h, l]) => `<a class="btn ghost small" style="justify-content:center" href="${h}">${l}</a>`).join("")}
        </div>
      </div>
      <div class="panel">
        <h3>Platform status</h3>
        <div class="hint">ALMIGHTY model family</div>
        <div id="modelStatus" style="margin-top:8px;display:flex;flex-direction:column;gap:8px"></div>
      </div>
    </div>
    <div class="panel" style="margin-top:16px">
      <h3>Recent generations</h3>
      <div class="hint">Your latest results — open History for everything</div>
      <div id="recent" class="grid c3" style="margin-top:12px"></div>
    </div>`);

  const [jobs, chars, projects] = await Promise.all([
    api("/jobs?limit=6"), api("/characters"), api("/projects")]);
  $("#stJobs").textContent = jobs.length;
  $("#stChars").textContent = chars.length; $("#stProj").textContent = projects.length;

  // public-safe model status comes from a dedicated public endpoint (no admin creds needed)
  try {
    const ms = await api("/models/public");
    $("#modelStatus").innerHTML = ms.map(m => `
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:13.5px">
        <span>${esc(m.name)} <span class="mono" style="color:var(--dim)">v${esc(m.version)}</span></span>
        <span class="badge ${m.status}">${m.status}</span></div>`).join("");
  } catch (_) { $("#modelStatus").innerHTML = ""; }

  $("#recent").innerHTML = jobs.length ? jobs.map(jobCard).join("") :
    `<div class="empty">Nothing yet — create your first generation! ✨</div>`;
  bindJobCards(c);
}

/* ============================================================
   STUDIOS
   ============================================================ */
const STUDIO_DEFS = {
  image: { title: "Image Studio", model: "ALMIGHTY IMAGE", blurb: "Text → image with full creative control.",
    fields: ["prompt", "negative", "style", "aspectImg", "resolution", "steps", "guidance", "seed", "character", "upload", "project"] },
  anime: { title: "Anime Studio", model: "ALMIGHTY ANIME", blurb: "Anime key visuals with character consistency.",
    fields: ["prompt", "negative", "aspectImg", "resolution", "guidance", "seed", "character", "project"] },
  video: { title: "Video Studio", model: "ALMIGHTY VIDEO", blurb: "Text/image → video with camera control.",
    fields: ["prompt", "style", "aspect", "duration", "motion", "camera", "seed", "character", "upload", "project"] },
  "2d": { title: "2D Animation Studio", model: "ALMIGHTY 2D", blurb: "Rig-animated scenes: action, emotion, dialogue.",
    fields: ["prompt", "aspect", "duration2d", "action", "emotion", "dialogue", "camera2d", "character", "project"] },
  story: { title: "Story → Video", model: "ALMIGHTY STORY", blurb: "Type a story — get a storyboarded video with subtitles.",
    fields: ["storyPrompt", "aspect", "durationStory", "character", "project"] },
  upscale: { title: "Upscale", model: "ALMIGHTY UPSCALE", blurb: "Enhance any image up to 4× with detail recovery.",
    fields: ["uploadRequired", "scale", "project"] },
};

const FIELD_TEMPLATES = {
  prompt: `<label>PROMPT</label><textarea name="prompt" required placeholder="Describe what you want to create…"></textarea>`,
  storyPrompt: `<label>YOUR STORY</label><textarea name="prompt" required minlength="20" rows="5"
      placeholder='e.g. "Create a 60-second horror story about a boy who discovers his reflection is alive."'></textarea>`,
  negative: `<label>NEGATIVE PROMPT</label><input name="negative" placeholder="blurry, dark, noisy… (optional)">`,
  style: `<label>STYLE</label><select name="style">
      ${["cinematic", "vibrant", "anime", "noir", "neon", "watercolor", "fantasy"]
        .map(s => `<option>${s}</option>`).join("")}</select>`,
  aspectImg: `<label>ASPECT RATIO</label><select name="aspect">
      <option value="1:1">1:1 square</option><option value="16:9">16:9 wide</option>
      <option value="9:16">9:16 vertical (Shorts/Reels)</option></select>`,
  aspect: `<label>ASPECT RATIO</label><select name="aspect">
      <option value="16:9">16:9 wide</option><option value="9:16">9:16 vertical (Shorts/Reels)</option>
      <option value="1:1">1:1 square</option></select>`,
  resolution: `<label>RESOLUTION</label><select name="resolution">
      <option value="768">768px (fast)</option><option value="1024" selected>1024px</option>
      <option value="1280">1280px (max)</option></select>`,
  steps: `<label>STEPS <span class="hint" style="display:inline">— detail passes</span></label>
      <div class="range-wrap"><input type="range" name="steps" min="10" max="50" value="28"
      oninput="this.nextElementSibling.textContent=this.value"><span class="val">28</span></div>`,
  guidance: `<label>GUIDANCE</label>
      <div class="range-wrap"><input type="range" name="guidance" min="1" max="15" step="0.5" value="7"
      oninput="this.nextElementSibling.textContent=this.value"><span class="val">7</span></div>`,
  duration: `<label>DURATION (SECONDS)</label>
      <div class="range-wrap"><input type="range" name="duration" min="2" max="8" value="4"
      oninput="this.nextElementSibling.textContent=this.value+'s'"><span class="val">4s</span></div>`,
  duration2d: `<label>DURATION (SECONDS)</label>
      <div class="range-wrap"><input type="range" name="duration" min="2" max="6" value="3"
      oninput="this.nextElementSibling.textContent=this.value+'s'"><span class="val">3s</span></div>`,
  durationStory: `<label>TARGET LENGTH (SECONDS)</label>
      <div class="range-wrap"><input type="range" name="duration" min="10" max="30" step="5" value="20"
      oninput="this.nextElementSibling.textContent=this.value+'s'"><span class="val">20s</span></div>
      <div class="hint">MVP cap 30s — long-form coherence lands with ALMIGHTY VIDEO Phase 3.</div>`,
  motion: `<label>MOTION STRENGTH</label>
      <div class="range-wrap"><input type="range" name="motion" min="0" max="2" step="0.1" value="0.8"
      oninput="this.nextElementSibling.textContent=this.value"><span class="val">0.8</span></div>`,
  camera: `<label>CAMERA MOVEMENT</label><select name="camera">
      <option value="zoom-in">Zoom in</option><option value="zoom-out">Zoom out</option>
      <option value="pan-left">Pan left</option><option value="pan-right">Pan right</option>
      <option value="orbit">Orbit</option><option value="push-up">Push up</option>
      <option value="static">Static</option></select>`,
  camera2d: `<label>CAMERA</label><select name="camera">
      <option value="static">Static</option><option value="pan-follow">Pan follow</option>
      <option value="zoom-in">Zoom in</option></select>`,
  action: `<label>ACTION</label><select name="action">
      ${["walk", "run", "wave", "dance", "jump", "talk", "fight"].map(a => `<option>${a}</option>`).join("")}</select>`,
  emotion: `<label>EMOTION</label><select name="emotion">
      ${["happy", "calm", "sad", "angry", "surprised", "determined"].map(a => `<option>${a}</option>`).join("")}</select>`,
  dialogue: `<label>DIALOGUE (OPTIONAL)</label><input name="dialogue" maxlength="120" placeholder='e.g. "We have to go, now!"'>`,
  seed: `<label>SEED</label><input name="seed" type="number" min="0" placeholder="random (0)">`,
  scale: `<label>UPSCALE FACTOR</label><select name="scale"><option value="2">2×</option><option value="4">4×</option></select>`,
  upload: `<label>REFERENCE IMAGE (OPTIONAL — image→image)</label>
      <input type="file" name="file" accept="image/*" id="fileInput">
      <div class="hint" id="uploadState"></div>`,
  uploadRequired: `<label>INPUT IMAGE (REQUIRED)</label>
      <input type="file" name="file" accept="image/*" id="fileInput" required>
      <div class="hint" id="uploadState"></div>`,
  character: `<label>CHARACTER (CONSISTENCY)</label><select name="character_id" id="charSel">
      <option value="">— no character —</option></select>`,
  project: `<label>SAVE TO PROJECT</label><select name="project_id" id="projSel"><option value="">— none —</option></select>`,
};

async function viewStudio(kind) {
  const def = STUDIO_DEFS[kind];
  const c = shell("#/studio/" + kind, def.title, `
    <div class="studio">
      <div class="panel">
        <h3>${def.model}</h3><div class="hint">${def.blurb}</div>
        <form id="genForm">
          ${def.fields.map(f => FIELD_TEMPLATES[f]).join("")}
          <button class="btn" style="width:100%;justify-content:center;margin-top:20px" id="genBtn">
            ✨ Generate</button>
          <div class="err" id="genErr"></div>
        </form>
      </div>
      <div class="result-pane" id="resultPane">
        <div class="drop"><div><div class="big">${{image:"🖼",video:"🎬",anime:"⛩","2d":"🧸",story:"📖",upscale:"🔍"}[kind]}</div>
        Your ${kind === "upscale" ? "enhanced image" : kind === "story" ? "story video" : "result"} will appear here.<br>
        <span style="font-size:12.5px">Routed by ALMIGHTY ORCHESTRATOR → ${def.model}</span></div></div>
      </div>
    </div>`);

  // populate selects
  const [chars, projects] = await Promise.all([api("/characters"), api("/projects")]);
  const cs = $("#charSel"); if (cs) cs.innerHTML += chars.map(ch =>
    `<option value="${ch.id}">${esc(ch.name)} · ${ch.character_code}</option>`).join("");
  const ps = $("#projSel"); if (ps) ps.innerHTML += projects.map(p =>
    `<option value="${p.id}">${esc(p.name)}</option>`).join("");

  // upload handling
  let uploadId = null;
  const fi = $("#fileInput");
  if (fi) fi.addEventListener("change", async () => {
    if (!fi.files[0]) return;
    $("#uploadState").textContent = "Uploading & validating…";
    const fd = new FormData(); fd.append("file", fi.files[0]);
    try { const r = await api("/uploads", { body: fd });
      uploadId = r.upload_id; $("#uploadState").textContent = "✓ " + r.name + " ready"; }
    catch (ex) { $("#uploadState").textContent = "✗ " + ex.detail; fi.value = ""; }
  });

  $("#genForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target); const err = $("#genErr"); err.textContent = "";
    const params = {};
    for (const [k, v] of f.entries()) {
      if (["file"].includes(k) || v === "") continue;
      params[k] = v;
    }
    if (uploadId) params.upload_id = uploadId;
    if (params.character_id) params.character_id = parseInt(params.character_id);
    if (params.project_id) params.project_id = parseInt(params.project_id);
    const btn = $("#genBtn"); btn.disabled = true;
    try {
      const r = await api("/generate", { body: { kind, prompt: f.get("prompt") || "", params } });
      toast(`Job queued · ${r.cost} credits`);
      trackJob(r.job_id);
    } catch (ex) { err.textContent = ex.detail || "Generation failed"; }
    btn.disabled = false;
  });
}

/* ---------------- job tracking & result rendering ---------------- */
function trackJob(jobId) {
  if (state.poller) clearInterval(state.poller);
  const pane = $("#resultPane"); if (!pane) return;
  pane.innerHTML = `<div class="progress-card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <b>ALMIGHTY ORCHESTRATOR</b><span class="chip" id="pct">0%</span></div>
      <div style="color:var(--mut);font-size:13.5px;margin-top:6px" id="stepTxt">queued…</div>
      <div class="bar"><i id="bar" style="width:2%"></i></div>
      <div class="hint" style="margin-top:8px">prompt understanding → routing → generation → quality evaluation</div>
    </div>`;
  state.poller = setInterval(async () => {
    let job; try { job = await api("/jobs/" + jobId); } catch (_) { return; }
    const bar = $("#bar"), txt = $("#stepTxt"), pct = $("#pct");
    if (!bar) { clearInterval(state.poller); return; }
    bar.style.width = Math.max(3, job.progress) + "%"; pct.textContent = job.progress + "%";
    txt.textContent = job.step || job.status;
    if (job.status === "done" || job.status === "failed") {
      clearInterval(state.poller); state.poller = null;
      if (job.status === "failed") {
        pane.innerHTML = `<div class="drop" style="border-color:#57202f;color:#ff8f9e">
          <div><div class="big">⚠️</div>Generation failed<br><span style="font-size:13px">${esc(job.error)}</span></div></div>`;
        refreshMe(); return;
      }
      renderResult(job); refreshMe();
    }
  }, 1100);
}

function renderResult(job) {
  const pane = $("#resultPane"); if (!pane) return;
  let ev = {}; try { ev = JSON.parse(job.eval_json || "{}"); } catch (_) {}
  let paramsExtra = {};
  const url = fileUrl(job.id);
  const media = job.media_type === "image/gif"
    ? `<img src="${url}" alt="generated result">`
    : job.media_type && job.media_type.startsWith("video")
      ? `<video src="${url}" controls autoplay loop muted playsinline></video>`
      : `<img src="${url}" alt="generated result">`;
  let planHtml = "";
  try {
    const p = JSON.parse(job.params || "{}");
    if (p.plan && p.plan.storyboard) {
      planHtml = `<div class="panel" style="padding:14px 16px">
        <h3 style="font-size:13.5px">Storyboard — ${esc(p.plan.genre)} · ${esc(p.plan.style)}</h3>
        ${p.plan.storyboard.map(s => `<div style="font-size:13px;color:var(--mut);margin-top:5px">
          <b style="color:var(--gold)">Scene ${s.scene}.</b> ${esc(s.caption)}</div>`).join("")}</div>`;
    }
  } catch (_) {}
  pane.innerHTML = `
    <div class="media-frame">${media}</div>
    <div class="eval-row">
      <span class="score-pill">Quality ${ev.score ?? "—"}</span>
      ${["contrast", "sharpness", "colorfulness", "motion_energy", "temporal_consistency", "prompt_alignment"]
        .filter(k => ev[k] != null).map(k => `<span class="chip">${k}: <b style="color:var(--txt)">${ev[k]}</b></span>`).join("")}
      <span class="chip">model: <b style="color:var(--txt)">${esc(job.model_id)}</b></span>
    </div>
    ${planHtml}
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="btn small" href="${url}" download>⬇ Download</a>
      <button class="btn danger small" id="delJob">Delete</button>
      <span class="chip">adjust controls on the left to regenerate</span>
    </div>`;
  $("#delJob").addEventListener("click", async () => {
    try { await api("/jobs/" + job.id, { method: "DELETE" }); toast("Deleted"); 
      pane.innerHTML = `<div class="drop"><div><div class="big">🗑</div>Result deleted.</div></div>`;
    } catch (ex) { toast(ex.detail, false); }
  });
}

/* ============================================================
   HISTORY
   ============================================================ */
function jobCard(j) {
  const ok = j.status === "done";
  let ev = {}; try { ev = JSON.parse(j.eval_json || "{}"); } catch (_) {}
  return `<div class="media-card" data-job="${j.id}">
    <div class="thumb">${ok
      ? (j.media_type === "image/gif" ? `<img loading="lazy" src="${fileUrl(j.id)}">`
         : j.media_type && j.media_type.startsWith("video") ? `<video src="${fileUrl(j.id)}" muted loop autoplay playsinline preload="metadata"></video>`
         : `<img loading="lazy" src="${fileUrl(j.id)}">`)
      : `<span style="color:var(--dim)">${j.status === "failed" ? "⚠ failed" : "…running"}</span>`}</div>
    <div class="body">
      <div style="display:flex;justify-content:space-between;gap:8px">
        <span class="chip">${j.kind}</span>
        ${ok ? `<span class="score-pill" style="font-size:11.5px;padding:2px 9px">Q ${ev.score ?? "—"}</span>` : ""}
      </div>
      <div class="p">${esc(j.prompt) || "—"}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;color:var(--dim);font-size:12px">
        <span>${timeAgo(j.created_at)} · ${j.cost}⚡</span>
        <span>
          ${ok ? `<a href="${fileUrl(j.id)}" download class="chip" style="margin-right:6px">⬇</a>` : ""}
          <button class="chip" data-del="${j.id}" style="background:#251318;border-color:#46202c;color:#ff8f9e">✕</button>
        </span></div>
    </div></div>`;
}
function bindJobCards(scope) {
  scope.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    try { await api("/jobs/" + b.dataset.del, { method: "DELETE" }); toast("Deleted"); render(); }
    catch (ex) { toast(ex.detail, false); }
  }));
}
async function viewHistory() {
  const c = shell("#/history", "Generation History", `<div class="grid c3" id="histGrid"><div class="empty">Loading…</div></div>`);
  const jobs = await api("/jobs?limit=60");
  $("#histGrid").innerHTML = jobs.length ? jobs.map(jobCard).join("") :
    `<div class="empty">No generations yet. Create something mighty! ⚡</div>`;
  bindJobCards(c);
}

/* ============================================================
   CHARACTERS
   ============================================================ */
async function viewCharacters() {
  const c = shell("#/characters", "Character Identity System", `
    <div class="grid c2" style="align-items:start">
      <div class="panel">
        <h3>Create a character</h3>
        <div class="hint">Every character gets a CHARACTER ID and a locked identity seed —
        the same face, hair, outfit and colors across every image, scene and video.</div>
        <form id="charForm">
          <label>NAME</label><input name="name" required maxlength="60" placeholder="e.g. Kaito">
          <label>DESCRIPTION</label><textarea name="description" rows="2" placeholder="Who are they?"></textarea>
          <div class="row2">
            <label>SKIN</label><input type="color" name="skin" value="#eab98f">
            <label>HAIR</label><input type="color" name="hair" value="#2b2118">
          </div>
          <div class="row2">
            <label>OUTFIT</label><input type="color" name="outfit" value="#7c5cff">
            <label>ACCENT</label><input type="color" name="accent" value="#f7c948">
          </div>
          <button class="btn" style="width:100%;justify-content:center;margin-top:18px">＋ Create character</button>
          <div class="err" id="charErr"></div>
        </form>
      </div>
      <div><div class="grid c2" id="charGrid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))"></div></div>
    </div>`);

  async function load() {
    const chars = await api("/characters");
    $("#charGrid").innerHTML = chars.length ? chars.map(ch => `
      <div class="media-card"><div class="body">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <b>${esc(ch.name)}</b><span class="chip mono">${ch.character_code}</span></div>
        <div style="display:flex;gap:6px;margin:6px 0">
          ${["skin", "hair", "outfit", "accent"].map(k =>
            `<span class="swatch" style="background:${esc(ch.traits[k] || "#444")}"></span>`).join("")}
        </div>
        <div class="p">${esc(ch.description || "—")}</div>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn ghost small" data-portrait="${ch.id}" data-name="${esc(ch.name)}">🎨 Portrait</button>
          <button class="btn danger small" data-cdel="${ch.id}">✕</button>
        </div></div></div>`).join("") :
      `<div class="empty">No characters yet — create your first one!</div>`;
    c.querySelectorAll("[data-cdel]").forEach(b => b.addEventListener("click", async () => {
      await api("/characters/" + b.dataset.cdel, { method: "DELETE" }); toast("Character removed"); load();
    }));
    c.querySelectorAll("[data-portrait]").forEach(b => b.addEventListener("click", async () => {
      try {
        const r = await api("/generate", { body: { kind: "anime",
          prompt: `portrait of ${b.dataset.name}, detailed character sheet, front view`,
          params: { character_id: parseInt(b.dataset.portrait), aspect: "1:1", resolution: "768" } } });
        toast("Portrait job queued"); location.hash = "#/history"; render();
        setTimeout(() => trackJob(r.job_id), 200);
      } catch (ex) { toast(ex.detail, false); }
    }));
  }
  $("#charForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const f = new FormData(e.target);
    try {
      await api("/characters", { body: { name: f.get("name"), description: f.get("description"),
        traits: { skin: f.get("skin"), hair: f.get("hair"), outfit: f.get("outfit"), accent: f.get("accent") } } });
      toast("Character created"); e.target.reset(); load();
    } catch (ex) { $("#charErr").textContent = ex.detail; }
  });
  load();
}

/* ============================================================
   PROJECTS
   ============================================================ */
async function viewProjects() {
  const c = shell("#/projects", "Projects", `
    <form id="projForm" style="display:flex;gap:10px;margin-bottom:18px;max-width:460px">
      <input name="name" placeholder="New project name…" required style="flex:1">
      <button class="btn">＋ Create</button>
    </form>
    <div class="grid c3" id="projGrid"></div>`);
  async function load() {
    const projects = await api("/projects");
    $("#projGrid").innerHTML = projects.length ? projects.map(p => `
      <div class="media-card"><div class="body">
        <b>🗂 ${esc(p.name)}</b>
        <div style="color:var(--dim);font-size:12.5px">${p.job_count} generation${p.job_count === 1 ? "" : "s"} · ${timeAgo(p.created_at)}</div>
        <div><button class="btn danger small" data-pdel="${p.id}">Delete</button></div>
      </div></div>`).join("") : `<div class="empty">No projects yet.</div>`;
    c.querySelectorAll("[data-pdel]").forEach(b => b.addEventListener("click", async () => {
      await api("/projects/" + b.dataset.pdel, { method: "DELETE" }); toast("Project deleted"); load();
    }));
  }
  $("#projForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const f = new FormData(e.target);
    try { await api("/projects", { body: { name: f.get("name") } }); e.target.reset(); load(); }
    catch (ex) { toast(ex.detail, false); }
  });
  load();
}

/* ============================================================
   ADMIN CONSOLE (owner/admin only — enforced server-side)
   ============================================================ */
let adminTab = "overview";
async function viewAdmin() {
  if (!["owner", "admin"].includes(state.user.role)) { location.hash = "#/dashboard"; return; }
  const tabs = [["overview", "Overview"], ["users", "Users"], ["models", "Models"],
                ["datasets", "Datasets"], ["jobs", "Jobs"], ["logs", "System Logs"],
                ["settings", "Settings"], ["analytics", "Analytics"]];
  const c = shell("#/admin", "Admin Console", `
    <div class="tabs">${tabs.map(([t, l]) =>
      `<button data-tab="${t}" class="${t === adminTab ? "active" : ""}">${l}</button>`).join("")}</div>
    <div id="adminBody"><div class="empty">Loading…</div></div>`);
  c.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => {
    adminTab = b.dataset.tab; viewAdmin();
  }));
  const body = $("#adminBody");
  try {
    if (adminTab === "overview") await adminOverview(body);
    if (adminTab === "users") await adminUsers(body);
    if (adminTab === "models") await adminModels(body);
    if (adminTab === "datasets") await adminDatasets(body);
    if (adminTab === "jobs") await adminJobs(body);
    if (adminTab === "logs") await adminLogs(body);
    if (adminTab === "settings") await adminSettings(body);
    if (adminTab === "analytics") await adminAnalytics(body);
  } catch (ex) { body.innerHTML = `<div class="empty">⚠ ${esc(ex.detail || "Failed to load")}</div>`; }
}

async function adminOverview(body) {
  const o = await api("/admin/overview");
  body.innerHTML = `
    <div class="stat-grid">
      <div class="stat"><div class="n">${o.counts.users}</div><div class="l">Users</div></div>
      <div class="stat"><div class="n">${o.counts.jobs_total}</div><div class="l">Total jobs</div></div>
      <div class="stat"><div class="n">${o.counts.jobs_today}</div><div class="l">Jobs today</div></div>
      <div class="stat"><div class="n">${o.counts.characters}</div><div class="l">Characters</div></div>
      <div class="stat"><div class="n">${o.credits_issued}</div><div class="l">Credits in circulation</div></div>
      <div class="stat"><div class="n">${fmtBytes(o.storage_bytes)}</div><div class="l">Generation storage</div></div>
    </div>
    <div class="grid c2">
      <div class="panel"><h3>System</h3>
        <table class="tbl">
          <tr><td>CPU load (1/5/15m)</td><td class="mono">${o.system.cpu_load.join(" / ")}</td></tr>
          <tr><td>Memory</td><td class="mono">${o.system.memory_used_mb} / ${o.system.memory_total_mb} MB</td></tr>
          <tr><td>Disk free</td><td class="mono">${o.system.disk_free_gb} GB</td></tr>
          <tr><td>GPU</td><td style="font-size:12.5px;color:var(--mut)">${esc(o.system.gpu)}</td></tr>
        </table></div>
      <div class="panel"><h3>Platform</h3>
        <table class="tbl">
          <tr><td>App</td><td class="mono">${esc(o.app.name)} ${esc(o.app.version)}</td></tr>
          <tr><td>Safety filter</td><td>${o.settings.safety_filter}</td></tr>
          <tr><td>External providers</td><td>${o.settings.allow_external_providers === "on"
            ? '<span class="badge development">temporary layer ON</span>' : '<span class="badge online">off — proprietary only</span>'}</td></tr>
          <tr><td>Maintenance</td><td>${o.settings.maintenance_mode}</td></tr>
          <tr><td>Daily free credits</td><td>${o.settings.daily_free_credits}</td></tr>
        </table></div>
    </div>`;
}

async function adminUsers(body) {
  const users = await api("/admin/users");
  body.innerHTML = `<div class="panel" style="overflow-x:auto"><table class="tbl">
    <tr><th>ID</th><th>Email</th><th>Name</th><th>Role</th><th>Credits</th><th>Status</th><th>Actions</th></tr>
    ${users.map(u => `<tr>
      <td>${u.id}</td><td class="mono">${esc(u.email)}</td><td>${esc(u.name)}</td>
      <td>${u.role === "owner" ? '<span class="badge development">owner</span>' : esc(u.role)}</td>
      <td>${u.credits < 0 ? "∞" : u.credits}</td>
      <td>${u.banned ? '<span class="badge offline">banned</span>' : '<span class="badge online">active</span>'}</td>
      <td style="white-space:nowrap">
        <button class="chip" data-act="add_credits" data-uid="${u.id}" data-role="${u.role}">+30⚡</button>
        ${u.role === "owner" ? "" : `
          <button class="chip" data-act="set_role" data-uid="${u.id}" data-val="${u.role === "admin" ? "user" : "admin"}">${u.role === "admin" ? "↓ user" : "↑ admin"}</button>
          <button class="chip" data-act="${u.banned ? "unban" : "ban"}" data-uid="${u.id}">${u.banned ? "unban" : "ban"}</button>`}
      </td></tr>`).join("")}
  </table></div>`;
  body.querySelectorAll("[data-act]").forEach(b => b.addEventListener("click", async () => {
    try {
      await api(`/admin/users/${b.dataset.uid}`, { body: { action: b.dataset.act,
        value: b.dataset.act === "add_credits" ? 30 : b.dataset.val || null } });
      toast("Updated"); adminUsers(body);
    } catch (ex) { toast(ex.detail, false); }
  }));
}

async function adminModels(body) {
  const models = await api("/admin/models");
  body.innerHTML = `<div class="panel" style="overflow-x:auto"><table class="tbl">
    <tr><th>Model</th><th>Family</th><th>Version</th><th>Architecture</th><th>VRAM</th><th>Status</th><th>Set status</th></tr>
    ${models.map(m => `<tr>
      <td><b>${esc(m.name)}</b><br><span class="hint">${esc(m.capabilities)}</span></td>
      <td>${esc(m.family)}</td><td class="mono">${esc(m.version)}</td>
      <td style="font-size:12.5px">${esc(m.architecture)}</td>
      <td class="mono">${m.vram_gb} GB</td>
      <td><span class="badge ${m.status}">${m.status}</span></td>
      <td><select data-model="${m.id}" style="width:auto;padding:6px 10px">
        ${["online", "development", "planned", "offline"].map(s =>
          `<option ${s === m.status ? "selected" : ""}>${s}</option>`).join("")}</select></td>
    </tr>`).join("")}
  </table></div>
  <div class="hint" style="margin-top:10px">Rollback = set the model back to a previous status/version.
  Full versioned weight rollback arrives with the Phase 3 registry.</div>`;
  body.querySelectorAll("[data-model]").forEach(sel => sel.addEventListener("change", async () => {
    try { await api(`/admin/models/${sel.dataset.model}/status`, { body: { status: sel.value } });
      toast("Model updated"); adminModels(body); }
    catch (ex) { toast(ex.detail, false); }
  }));
}

async function adminDatasets(body) {
  const ds = await api("/admin/datasets");
  body.innerHTML = `
    <form id="dsForm" class="panel" style="margin-bottom:16px;display:grid;grid-template-columns:1fr 1fr;gap:0 12px">
      <div style="grid-column:1/-1"><h3>Register dataset</h3>
      <div class="hint">Training is blocked for datasets that are not rights-cleared.</div></div>
      <div><label>NAME</label><input name="name" required></div>
      <div><label>SOURCE</label><input name="source" placeholder="where it comes from"></div>
      <div><label>LICENSE</label><input name="license" value="rights-verified only"></div>
      <div style="display:flex;align-items:flex-end"><button class="btn" style="width:100%;justify-content:center">＋ Register</button></div>
    </form>
    <div class="panel" style="overflow-x:auto"><table class="tbl">
      <tr><th>Name</th><th>Version</th><th>Source</th><th>License</th><th>Quality</th><th>Safety</th><th>Training</th><th></th></tr>
      ${ds.map(d => `<tr>
        <td><b>${esc(d.name)}</b></td><td class="mono">${esc(d.version)}</td>
        <td style="font-size:12.5px">${esc(d.source)}</td><td style="font-size:12.5px">${esc(d.license)}</td>
        <td class="mono">${d.quality_score}</td>
        <td><span class="badge ${d.safety_status === "cleared" ? "online" : d.safety_status === "restricted" ? "offline" : "development"}">${d.safety_status}</span></td>
        <td>${d.training_eligible ? '<span class="badge online">eligible</span>' : '<span class="badge planned">blocked</span>'}</td>
        <td><button class="chip" data-clear="${d.id}">mark cleared & eligible</button></td>
      </tr>`).join("")}
    </table></div>`;
  $("#dsForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const f = new FormData(e.target);
    try { await api("/admin/datasets", { body: { name: f.get("name"), source: f.get("source"), license: f.get("license") } });
      toast("Dataset registered"); adminDatasets(body); }
    catch (ex) { toast(ex.detail, false); }
  });
  body.querySelectorAll("[data-clear]").forEach(b => b.addEventListener("click", async () => {
    try { await api(`/admin/datasets/${b.dataset.clear}/review`,
      { body: { safety_status: "cleared", training_eligible: 1 } });
      toast("Dataset cleared"); adminDatasets(body); }
    catch (ex) { toast(ex.detail, false); }
  }));
}

async function adminJobs(body) {
  const jobs = await api("/admin/jobs?limit=80");
  body.innerHTML = `<div class="panel" style="overflow-x:auto"><table class="tbl">
    <tr><th>ID</th><th>User</th><th>Kind</th><th>Prompt</th><th>Status</th><th>Score</th><th>Cost</th><th>When</th></tr>
    ${jobs.map(j => { let ev = {}; try { ev = JSON.parse(j.eval_json || "{}"); } catch (_) {}
      return `<tr><td>${j.id}</td><td class="mono" style="font-size:12px">${esc(j.email || "")}</td>
      <td><span class="chip">${j.kind}</span></td>
      <td style="max-width:280px" class="p">${esc((j.prompt || "").slice(0, 80))}</td>
      <td>${j.status === "done" ? '<span class="badge online">done</span>' : j.status === "failed"
        ? '<span class="badge offline">failed</span>' : '<span class="badge development">' + j.status + "</span>"}</td>
      <td class="mono">${ev.score ?? "—"}</td><td>${j.cost}⚡</td><td>${timeAgo(j.created_at)}</td></tr>`; }).join("")}
  </table></div>`;
}

async function adminLogs(body) {
  const logs = await api("/admin/logs?limit=150");
  body.innerHTML = `<div class="panel" style="overflow-x:auto"><table class="tbl">
    <tr><th>Time</th><th>Level</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
    ${logs.map(l => `<tr><td class="mono" style="font-size:11.5px;white-space:nowrap">${l.ts}</td>
      <td>${l.level === "error" ? '<span class="badge offline">error</span>' : l.level === "warn"
        ? '<span class="badge development">warn</span>' : '<span class="badge online">info</span>'}</td>
      <td class="mono" style="font-size:12px">${esc(l.actor)}</td><td class="mono" style="font-size:12px">${esc(l.action)}</td>
      <td style="font-size:12.5px;color:var(--mut)">${esc(l.detail)}</td></tr>`).join("") ||
      '<tr><td colspan="5" class="empty">No logs yet</td></tr>'}
  </table></div>`;
}

async function adminSettings(body) {
  const s = await api("/admin/settings");
  const f = (k, label, hint, options) => `
    <label>${label}</label>
    ${options ? `<select name="${k}">${options.map(o =>
        `<option ${String(s[k]) === o ? "selected" : ""}>${o}</option>`).join("")}</select>`
      : `<input name="${k}" value="${esc(s[k])}">`}
    <div class="hint">${hint}</div>`;
  body.innerHTML = `<form id="setForm" class="panel" style="max-width:560px">
    ${f("daily_free_credits", "DAILY FREE CREDITS", "Granted to each standard user once per day.")}
    ${f("quality_threshold", "QUALITY THRESHOLD", "Auto-improve retries when a generation scores below this (0–100).")}
    ${f("safety_filter", "SAFETY FILTER", "Master safety switch for generations.", ["on", "off"])}
    ${f("allow_external_providers", "TEMPORARY EXTERNAL PROVIDERS",
      "OFF = proprietary engines only. ON enables the temporary adapter layer during development.", ["off", "on"])}
    ${f("maintenance_mode", "MAINTENANCE MODE", "Blocks non-admin generations while on.", ["off", "on"])}
    <button class="btn" style="margin-top:18px">Save settings</button>
    <div class="err" id="setMsg"></div>
  </form>`;
  $("#setForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const fd = new FormData(e.target); const values = {};
    for (const [k, v] of fd.entries()) values[k] = v;
    try { await api("/admin/settings", { body: { values } }); $("#setMsg").textContent = "✓ Saved"; toast("Settings saved"); }
    catch (ex) { $("#setMsg").textContent = ex.detail; }
  });
}

async function adminAnalytics(body) {
  const a = await api("/admin/analytics");
  const maxJ = Math.max(1, ...a.jobs_by_day.map(d => d.n));
  body.innerHTML = `<div class="grid c2">
    <div class="panel"><h3>Jobs — last 14 days</h3>
      <div class="bars">${a.jobs_by_day.map(d =>
        `<div class="b" style="height:${(d.n / maxJ) * 100}%" title="${d.d}: ${d.n}"></div>`).join("") ||
        '<div class="hint">No data yet</div>'}</div>
      <div class="bar-labels">${a.jobs_by_day.map(d => `<span>${d.d.slice(5)}</span>`).join("")}</div></div>
    <div class="panel"><h3>Jobs by model family</h3>
      <table class="tbl">${a.jobs_by_kind.map(k =>
        `<tr><td><span class="chip">${k.kind}</span></td><td class="mono">${k.n}</td></tr>`).join("") ||
        '<tr><td class="hint">No generations yet</td></tr>'}</table></div>
  </div>`;
}

/* ============================================================
   ROUTER
   ============================================================ */
function stopPoller() { if (state.poller) { clearInterval(state.poller); state.poller = null; } }

async function render() {
  stopPoller();
  const hash = location.hash || "#/";
  const publicRoutes = ["#/", "#/login", "#/register"];

  if (state.token && !state.user) { if (!(await refreshMe())) { location.hash = "#/"; } }
  if (state.user && ["#/login", "#/register"].includes(hash)) { location.hash = "#/dashboard"; return; }
  if (!state.user && !publicRoutes.includes(hash)) { location.hash = "#/login"; return; }

  if (hash === "#/" ) return viewLanding();
  if (hash === "#/login") return viewAuth("login");
  if (hash === "#/register") return viewAuth("register");
  if (!state.user) return;

  if (hash === "#/dashboard") return viewDashboard();
  if (hash.startsWith("#/studio/")) {
    const kind = hash.split("/")[2];
    if (STUDIO_DEFS[kind]) return viewStudio(kind);
  }
  if (hash === "#/characters") return viewCharacters();
  if (hash === "#/projects") return viewProjects();
  if (hash === "#/history") return viewHistory();
  if (hash === "#/admin") return viewAdmin();
  location.hash = "#/dashboard";
}

window.addEventListener("hashchange", render);
render();

import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "@playwright/test";

// Documentation screenshots of the real dashboard against a mocked API.
// Every title, poster and user here is fictional, so the images can be published anywhere.
const OUT = join(__dirname, "..", "..", "docs", "assets", "screenshots");
mkdirSync(OUT, { recursive: true });
// Deliberately unsigned fixture token, as in e2e/critical-flow.spec.js. Every API request is intercepted.
const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";

const palettes = [
  ["#0b1d33", "#2a6fdb", "#9fd3ff"], ["#2b1030", "#c2477a", "#ffc2d6"], ["#10241c", "#2f9e6e", "#b9f5d8"],
  ["#2a1a0c", "#d9822b", "#ffe0b3"], ["#16112e", "#6a4cd9", "#d2c7ff"], ["#2b0f0f", "#c23b3b", "#ffc9c2"],
  ["#0c2626", "#1c9aa6", "#b5f0f2"], ["#24210a", "#b8a224", "#fff2a8"], ["#1a1424", "#8a5fa8", "#ecd2ff"],
  ["#0f1a2b", "#3d8bd9", "#cfe6ff"], ["#2a1420", "#d16a8c", "#ffd3e2"], ["#13221a", "#5aa83d", "#d8f5c4"],
];
const titles = [
  "Orbit", "Afterlight", "Night Signal", "The Last Horizon", "Glass Harbor", "Ember Road",
  "Tidewater", "Golden Hour", "Paper Moons", "Northbound", "Velvet City", "Wildgrove",
];
const scenes = [
  (l, m) => `<circle cx="200" cy="230" r="105" fill="${l}"/><ellipse cx="200" cy="230" rx="175" ry="40" fill="none" stroke="${m}" stroke-width="22" transform="rotate(-25 200 230)"/>`,
  (l, m, d) => `<circle cx="200" cy="220" r="115" fill="${l}"/><path d="M0 380 120 230 245 380 340 260 400 380V600H0Z" fill="${d}"/><path d="M0 450 160 310 300 460 400 340V600H0Z" fill="${m}"/>`,
  (l, m, d) => `<path d="M30 450V270h45v180h30V180h60v270h30V320h45v130h30V130h65v320h35V230h40v370H0Z" fill="${d}"/><circle cx="200" cy="150" r="40" fill="${l}"/>`,
  (l, m, d) => `<circle cx="280" cy="190" r="95" fill="${l}"/><path d="M0 400 125 210 240 390 315 285 400 425V600H0Z" fill="${m}"/><path d="M0 475 155 330 320 500 400 400V600H0Z" fill="${d}"/>`,
];

function poster(i, wide = false) {
  const [d, m, l] = palettes[i % palettes.length];
  const scene = scenes[i % scenes.length](l, m, d);
  const title = titles[i % titles.length].toUpperCase();
  if (wide) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 400 225" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="${d}"/><stop offset="1" stop-color="${m}"/></linearGradient></defs><rect width="400" height="225" fill="url(#g)"/><g transform="translate(60 -120) scale(.7)">${scene}</g></svg>`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 400 600"><defs><linearGradient id="g" x2="0" y2="1"><stop stop-color="${d}"/><stop offset="1" stop-color="${m}"/></linearGradient></defs><rect width="400" height="600" fill="url(#g)"/>${scene}<text x="200" y="525" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="bold" font-size="${title.length > 12 ? 26 : 34}" letter-spacing="3">${title}</text></svg>`;
}

const img = (i) => `https://image.tmdb.org/t/p/w500/docs-poster-${i}.svg`;
const backdrop = (i) => `https://image.tmdb.org/t/p/w1280/docs-backdrop-${i}.svg`;
const ago = (hours) => new Date(Date.now() - hours * 3600_000).toISOString().slice(0, 19).replace("T", " ");
const users = ["alex", "sam", "jordan"];
const overview = "A fictional title made up for the SuggestArr documentation, with an overview long enough to fill the card.";

function request(i, source, extra = {}) {
  return {
    request_id: 100 + i, media_type: i % 3 === 1 ? "tv" : "movie", requested_at: ago(i * 5 + 1),
    title: titles[i % titles.length], overview, release_date: `${2018 + (i % 7)}-0${1 + (i % 9)}-12`,
    poster_path: img(i), backdrop_path: backdrop(i), rating: 6.8 + ((i * 7) % 25) / 10, logo_path: null,
    rationale: `Because ${users[i % 3]} watched ${source}`, user_id: 2 + (i % 3), user_name: users[i % 3],
    source_origin: "media_server", feedback: null, watched_at: null,
    availability: ["available", "processing", "requested", "available", "partial"][i % 5], media_url: null, ...extra,
  };
}

const sources = [0, 1, 2, 3].map((s) => ({
  source_id: 900 + s, source_title: titles[(s + 8) % 12], source_overview: overview, source_release_date: "2021-05-01",
  source_poster_path: img(s + 8), rating: 7.9, media_type: s === 1 ? "tv" : "movie", logo_path: null,
  backdrop_path: backdrop(s + 8), is_anime: false, max_requested_at: ago(s * 6),
  requests: [0, 1, 2].map((k) => request(s * 3 + k, titles[(s + 8) % 12])),
}));

const jobs = [
  { id: 1, name: "Nightly discovery", job_type: "discover", media_type: "movie", enabled: true, max_results: 10, filters: {}, schedule_type: "preset", schedule_value: "daily", delivery_mode: "auto", last_run: ago(3), next_run: ago(-21) },
  { id: 2, name: "Weekly TV picks", job_type: "recommendation", media_type: "tv", enabled: true, max_results: 5, filters: {}, schedule_type: "preset", schedule_value: "weekly", delivery_mode: "manual", last_run: ago(30), next_run: ago(-120) },
  { id: 3, name: "Trending lists import", job_type: "list_import", media_type: "both", enabled: false, max_results: 20, filters: {}, schedule_type: "preset", schedule_value: "daily", delivery_mode: "auto", last_run: ago(80), next_run: null },
];
const history = [
  { id: 31, job_id: 1, job_name: "Nightly discovery", status: "completed", results_count: 14, requested_count: 6, started_at: ago(3.1), finished_at: ago(3) },
  { id: 30, job_id: 2, job_name: "Weekly TV picks", status: "completed", results_count: 8, requested_count: 3, started_at: ago(30.2), finished_at: ago(30) },
  { id: 29, job_id: 1, job_name: "Nightly discovery", status: "completed", results_count: 11, requested_count: 4, started_at: ago(27.1), finished_at: ago(27) },
  { id: 28, job_id: 3, job_name: "Trending lists import", status: "completed", results_count: 20, requested_count: 9, started_at: ago(80.3), finished_at: ago(80) },
];
const pending = [4, 7, 10].map((i) => ({
  id: 50 + i, tmdb_id: String(500 + i), title: titles[i], media_type: i % 2 ? "tv" : "movie", rating: 7.6,
  name: "Weekly TV picks", status: "awaiting_approval", poster_path: `/docs-poster-${i}.svg`, created_at: ago(i), user_name: users[i % 3],
  overview, rationale: `Because ${users[i % 3]} watched ${titles[(i + 3) % 12]}`,
}));

const badgeLabels = { 10: "First discoveries", 50: "Half-century", 100: "Century club", 250: "Film buff", 500: "Discovery enthusiast", 1000: "A thousand discoveries", 2500: "Marathon curator" };
const recap = {
  scope: "installation", has_linked_profiles: true, total: 1284, movies: 902, tv: 382,
  first_requested_at: "2025-09-01T00:00:00+00:00",
  badges: Object.keys(badgeLabels).map(Number).map((threshold, i) => ({
    id: `titles_${threshold}`, kind: "titles", threshold, label: badgeLabels[threshold], description: `Request ${threshold} titles`,
    progress: Math.min(1284, threshold), unlocked: 1284 >= threshold, unlocked_at: 1284 >= threshold ? `2026-0${i + 2}-10T12:00:00+00:00` : null,
  })),
  watch_tracking: true, watched: 412, hit_rate: 32, streak: { current: 4, longest: 9 },
  next_badge: { id: "titles_2500", threshold: 2500, label: "Marathon curator" },
  preferences: { reminder_mode: "enabled" }, posters: [], can_support: false,
};
const aiResults = [5, 0, 9, 2, 6, 11, 3, 8].map((i, k) => ({
  id: 700 + i, title: titles[i], media_type: k % 3 === 1 ? "tv" : "movie", year: 2015 + k, release_date: `${2015 + k}-03-01`,
  poster_path: img(i), rating: 7.1 + (k % 4) / 2, overview,
  rationale: ["Slow-burn space drama with a lonely crew", "Quiet sci-fi about memory and loss", "A crew stranded far from home", "Character-driven survival story"][k % 4],
}));

async function mockApi(page, unmocked) {
  await page.addInitScript(() => {
    localStorage.setItem("suggestarr_tour_done", "1");
    localStorage.setItem("suggestarr_jobs_tour_done", "1");
  });
  await page.route("https://image.tmdb.org/**", (route) => {
    const url = route.request().url();
    const i = Number(url.match(/-(\d+)\.svg/)?.[1] ?? 0);
    return route.fulfill({ contentType: "image/svg+xml", body: poster(i, url.includes("backdrop")) });
  });
  await page.route("http://localhost:5000/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const json = (body) => route.fulfill({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" },
      body: JSON.stringify(body),
    });
    const p = pathname.replace(/\/$/, "");
    if (p === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: true });
    if (p === "/api/auth/login" || p === "/api/auth/refresh") return json({ access_token: token });
    if (p === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (p === "/api/config/fetch") return json({ AUTH_MODE: "enabled", SELECTED_SERVICE: "jellyfin" });
    if (p === "/api/config/status") return json({ setup_completed: true, is_complete: true });
    if (p === "/api/automation/requests/stats") {
      return json({ total: 1284, approved: 0, pending: 0, today: 7, this_week: 38, this_month: 142, previous: { today: 5, this_week: 31, this_month: 120 } });
    }
    if (p === "/api/automation/requests") {
      return json({ data: sources, total_pages: 1, total_sources: sources.length, total_requests: 12, request_users: users.map((u, i) => ({ id: 2 + i, username: u })) });
    }
    if (p === "/api/automation/requests/workflow") return json({ items: pending, total: pending.length, page: 1, pages: 1 });
    if (p === "/api/jobs") return json({ status: "success", jobs, request_approval_default: false });
    if (p === "/api/jobs/history") return json({ status: "success", history });
    if (p === "/api/jobs/queue-status") return json({ status: "success", queued: 0, submitting: 0, submitted: 0, failed: 0, total_pending: 0 });
    if (p === "/api/recap") return json({ status: "success", data: recap });
    if (p === "/api/ai-search/status") return json({ available: true });
    if (p === "/api/ai-search/history") return json({ status: "success", history: ["A cozy mystery series set in a small town"] });
    if (p === "/api/ai-search/inspiration") return json({ items: [0, 1, 2, 3].map((i) => ({ title: titles[i], year: 2019 + i, media_type: i === 1 ? "tv" : "movie", poster_path: `/docs-poster-${i}.svg` })) });
    if (p === "/api/ai-search/query") return json({ status: "success", results: aiResults, ai_reasoning: { genres: ["Science Fiction", "Drama"], original_language: null } });
    if (p === "/api/tmdb/languages") return json({ languages: [{ iso_639_1: "en", english_name: "English", name: "English" }] });
    if (p.startsWith("/api/ai-search")) return json({ status: "success", feedback: [], people: [] });
    unmocked.add(`${request.method()} ${p}`);
    return json({});
  });
}

async function signIn(page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL(/\/dashboard/);
}

const shots = [
  { name: "home", path: "/dashboard" },
  { name: "requests", path: "/requests?status=sent" },
  { name: "jobs", path: "/dashboard/jobs" },
  {
    name: "ai-search", path: "/dashboard/ai_search",
    async act(page) {
      await page.getByRole("textbox").first().fill("A slow-burn space drama about a crew far from home");
      await page.getByRole("button", { name: "Search", exact: true }).click();
      await page.getByText(titles[5], { exact: true }).first().waitFor();
    },
  },
];

// The hero image is built from the screenshots above, so they must exist first.
test.describe.configure({ mode: "serial" });

for (const shot of shots) {
  test(`screenshot ${shot.name}`, async ({ page }) => {
    const unmocked = new Set();
    await mockApi(page, unmocked);
    await signIn(page);
    await page.goto(shot.path);
    await page.waitForLoadState("networkidle");
    if (shot.act) await shot.act(page);
    await page.waitForTimeout(800);
    await page.screenshot({ path: join(OUT, `${shot.name}.png`) });
    if (unmocked.size) console.log(shot.name, "unmocked:", [...unmocked].join(", "));
  });
}

test("README hero image", async ({ page }) => {
  const data = (file) => `data:image/png;base64,${readFileSync(file).toString("base64")}`;
  const logo = data(join(__dirname, "..", "src", "assets", "logo.png"));
  // Same tokens as src/assets/main.css (dark theme): flat canvas, one accent, the app's own font.
  await page.setViewportSize({ width: 1600, height: 800 });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;800&display=swap" rel="stylesheet">
    <style>
      * { margin: 0; box-sizing: border-box; }
      body { width: 1600px; height: 800px; overflow: hidden; position: relative; background: #0b0d12; color: #e8eaf0;
        font-family: "Plus Jakarta Sans", sans-serif; }
      .copy { position: absolute; left: 96px; top: 88px; bottom: 88px; width: 540px; display: flex; flex-direction: column; }
      .brand { display: flex; align-items: center; gap: 12px; font-size: 24px; font-weight: 800; }
      .brand img { height: 32px; }
      .main { margin-top: auto; margin-bottom: auto; }
      h1 { font-size: 58px; line-height: 1.08; font-weight: 800; letter-spacing: -1.6px; }
      h1 span { color: #b3a9ff; }
      p { margin-top: 24px; font-size: 20px; line-height: 1.55; color: #9aa3b5; font-weight: 500; max-width: 470px; }
      .meta { font-size: 15px; color: #8790a3; font-weight: 600; }
      .meta b { color: #c5cbd8; font-weight: 600; }
      .window { position: absolute; left: 720px; top: 112px; width: 1200px; border-radius: 14px; overflow: hidden;
        border: 1px solid #2a3042; box-shadow: 0 30px 60px rgba(0, 0, 0, .45); }
      .window img { display: block; width: 100%; }
    </style></head><body>
    <div class="copy">
      <div class="brand"><img src="${logo}" alt="">SuggestArr</div>
      <div class="main">
        <h1>You watch.<br><span>SuggestArr finds what's next.</span></h1>
        <p>It picks movies and shows like the ones you watched and requests them in Seer, automatically or after you approve them.</p>
      </div>
      <div class="meta">Works with <b>Jellyfin</b>, <b>Plex</b>, <b>Emby</b> and <b>Seer</b> · Self-hosted · Open source</div>
    </div>
    <div class="window"><img src="${data(join(OUT, "requests.png"))}" alt=""></div>
    </body></html>`);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, "..", "suggestarr-hero.png") });
});

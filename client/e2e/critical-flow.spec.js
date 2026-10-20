import { expect, test } from "@playwright/test";

// Deliberately unsigned fixture token. Every API request is intercepted below.
const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";

async function mockApi(page, { subpath = "", setupCompleted = true, radarrServers = null, deliveryMode = "manual", approvalDefault = false } = {}) {
  let approved = false;
  let approveCalls = 0;
  let approveBody = null;
  let runCalls = 0;

  await page.addInitScript(() => {
    localStorage.setItem("suggestarr_tour_done", "1");
    localStorage.setItem("suggestarr_jobs_tour_done", "1");
  });

  await page.route("http://localhost:5000/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const expectedPrefix = `${subpath}/api/`;
    if (!pathname.startsWith(expectedPrefix)) {
      throw new Error(`Expected API request under ${expectedPrefix}, got ${pathname}`);
    }
    const apiPath = pathname.slice(subpath.length);
    const json = (body) => route.fulfill({
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:5173",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify(body),
    });

    if (apiPath === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: setupCompleted });
    if (apiPath === "/api/auth/login") return json({ access_token: token });
    if (apiPath === "/api/auth/refresh") return json({ access_token: token });
    if (apiPath === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (apiPath === "/api/config/fetch") return json({ AUTH_MODE: "enabled" });
    if (apiPath === "/api/config/status") return json({ setup_completed: setupCompleted, is_complete: setupCompleted });
    if (apiPath === "/api/jobs") {
      return json({ status: "success", jobs: [{
        id: 7, name: "Manual job", job_type: "discover", media_type: "movie", enabled: true,
        max_results: 5, filters: {}, schedule_type: "preset", schedule_value: "daily",
        delivery_mode: deliveryMode,
      }], request_approval_default: approvalDefault });
    }
    if (apiPath === "/api/jobs/history") return json({ status: "success", history: [] });
    if (apiPath === "/api/jobs/queue-status") return json({ status: "success", queued: 0, submitting: 0, submitted: 0, failed: 0, total_pending: 0 });
    if (apiPath === "/api/jobs/7/dry-run" && request.method() === "POST") {
      return json({ status: "success", dry_run: true, items_count: 1, items: [{
        tmdb_id: 101, media_type: "movie", title: "Preview title", would_request: true,
      }] });
    }
    if (apiPath === "/api/jobs/7/run" && request.method() === "POST") {
      runCalls += 1;
      return json({ status: "success", results_count: 1, requested_count: 1, run_id: 9 });
    }
    if (apiPath === "/api/automation/requests/workflow/approve" && request.method() === "POST") {
      approved = true;
      approveCalls += 1;
      approveBody = request.postDataJSON();
      return json({ updated: 1 });
    }
    if (radarrServers && apiPath === "/api/seer/radarr-servers") return json({ servers: radarrServers });
    if (radarrServers && apiPath === "/api/seer/sonarr-servers") return json({ servers: [] });
    if (apiPath === "/api/automation/requests/workflow" || apiPath === "/api/automation/requests/workflow/") {
      return json({
        items: approved ? [] : [{ id: 42, tmdb_id: "42", title: "Smoke title", media_type: "movie", rating: 8.1, name: "Manual job", status: "awaiting_approval" }],
        total: approved ? 0 : 1, page: 1, pages: 1,
      });
    }
    if (apiPath === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });
  return { approveCalls: () => approveCalls, approveBody: () => approveBody, runCalls: () => runCalls };
}

async function injectSubpathIndex(page, subpath) {
  const inject = async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replace("<head>", `<head><meta name=\"suggestarr-subpath\" content=\"${subpath}\"><base href=\"${subpath}/\">`);
    await route.fulfill({ response, body });
  };
  await page.route(`**${subpath}/login`, inject);
  await page.route(`**${subpath}/requests**`, inject);
}

for (const subpath of ["", "/suggestarr"]) {
  test(`an administrator can sign in and approve a queued suggestion${subpath || " at root"}`, async ({ page }) => {
    const api = await mockApi(page, { subpath });
    if (subpath) await injectSubpathIndex(page, subpath);

    await page.goto(`${subpath}/login`);
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("correct-horse-battery-staple");
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page).toHaveURL(new RegExp(`${subpath}/dashboard$`));

    await page.goto(`${subpath}/requests?status=awaiting_approval`);
    await expect(page.getByText("Smoke title")).toBeVisible();
    await page.getByRole("button", { name: "Approve request" }).click();
    await expect.poll(api.approveCalls).toBe(1);
    await expect(page.getByText("Smoke title")).toHaveCount(0);
  });
}

const twoRadarrServers = [
  { id: 0, name: "Radarr", is4k: false, profiles: [{ id: 7, name: "HD" }, { id: 9, name: "Original language" }], rootFolders: [{ path: "/movies" }] },
  { id: 1, name: "Radarr 4K", is4k: true, profiles: [{ id: 3, name: "UHD" }], rootFolders: [{ path: "/movies-4k" }] },
];

test("approving asks for a quality profile and sends the chosen one", async ({ page }) => {
  const api = await mockApi(page, {
    // Two servers, so there is something to choose (a single server is filled
    // in by itself — see approval-dialog.spec.js). id 0 on purpose: Jellyseerr
    // numbers its first server 0, and a falsy check once treated that as
    // "nothing chosen".
    radarrServers: twoRadarrServers,
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/requests?status=awaiting_approval");
  await expect(page.getByText("Smoke title")).toBeVisible();
  await page.getByRole("button", { name: "Approve request" }).click();

  // With a server to choose from, the click opens the dialog instead of sending.
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Quality profile", { exact: true })).toBeVisible();
  expect(api.approveCalls()).toBe(0);

  await dialog.getByLabel("Server", { exact: true }).selectOption({ label: "Radarr" });
  await dialog.getByLabel("Quality profile", { exact: true }).selectOption({ label: "Original language" });
  // The chosen server has a single root folder, so it is already there.
  await expect(dialog.getByLabel("Root folder", { exact: true })).toHaveValue("/movies");
  await dialog.getByRole("button", { name: "Send", exact: true }).click();

  await expect.poll(api.approveCalls).toBe(1);
  expect(api.approveBody()).toEqual({
    ids: [42],
    profile: { movie: { serverId: 0, profileId: 9, rootFolder: "/movies", is4k: false } },
  });
});

test("approving without touching the profile sends none", async ({ page }) => {
  const api = await mockApi(page, {
    radarrServers: [{ id: 3, name: "Radarr", is4k: false, profiles: [{ id: 7, name: "HD" }], rootFolders: [{ path: "/movies" }] }],
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/requests?status=awaiting_approval");
  await page.getByRole("button", { name: "Approve request" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Send", exact: true }).click();

  await expect.poll(api.approveCalls).toBe(1);
  expect(api.approveBody()).toEqual({ ids: [42] });
});

test("approving from the dashboard asks for a quality profile too", async ({ page }) => {
  // The dashboard has its own approve button (HomePage). It once
  // skipped the dialog entirely and sent the request with Jellyseerr's default.
  const api = await mockApi(page, {
    radarrServers: twoRadarrServers,
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await expect(page.getByText("Smoke title")).toBeVisible();
  await page.getByRole("button", { name: "Approve request" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Quality profile", { exact: true })).toBeVisible();
  expect(api.approveCalls()).toBe(0);

  await dialog.getByLabel("Server", { exact: true }).selectOption({ label: "Radarr" });
  await dialog.getByLabel("Quality profile", { exact: true }).selectOption({ label: "Original language" });
  // The chosen server has a single root folder, so it is already there.
  await expect(dialog.getByLabel("Root folder", { exact: true })).toHaveValue("/movies");
  await dialog.getByRole("button", { name: "Send", exact: true }).click();

  await expect.poll(api.approveCalls).toBe(1);
  expect(api.approveBody()).toEqual({
    ids: [42],
    profile: { movie: { serverId: 0, profileId: 9, rootFolder: "/movies", is4k: false } },
  });
});

test("an authenticated administrator can start the setup wizard", async ({ page }) => {
  await mockApi(page, { setupCompleted: false });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/setup$/);

  await page.getByRole("button", { name: "Start Setup" }).click();
  await expect(page.getByText(/Step 1 of/)).toBeVisible();
});

test("a job preview and simulated request run without external providers", async ({ page }) => {
  const api = await mockApi(page);

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Manual job" })).toBeVisible();
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByRole("heading", { name: "Dry run preview" })).toBeVisible();
  await expect(page.getByText("Preview title")).toBeVisible();
  await expect(page.getByText(/nothing was requested/)).toBeVisible();

  await page.getByRole("button", { name: "Run job now" }).click();
  await expect.poll(api.runCalls).toBe(1);
});

test("secondary job actions sit in a keyboard-friendly menu", async ({ page }) => {
  await mockApi(page);
  await signIn(page);
  await page.getByRole("link", { name: "Jobs", exact: true }).click();

  const more = page.getByRole("button", { name: "More actions for Manual job" });
  await more.click();
  const menu = page.getByRole("menu", { name: "More actions for Manual job" });
  await expect(menu.getByRole("menuitem")).toHaveText(["Pause", "Edit", "Duplicate", "Delete"]);
  await expect(menu.getByRole("menuitem", { name: "Pause" })).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(menu.getByRole("menuitem", { name: "Delete" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(more).toBeFocused();

  await more.click();
  await page.getByRole("menuitem", { name: "Duplicate" }).click();
  const dialog = page.getByRole("dialog", { name: "New job" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: /name/i }).first()).toHaveValue("Manual job (copy)");
});

async function signIn(page, landing = /\/dashboard$/) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(landing);
}

test("a signed-in administrator can log out", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("an unknown path lands on the dashboard", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/no-such-page");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("jobs that inherit a global approval requirement show the approval queue everywhere", async ({ page }) => {
  await mockApi(page, { deliveryMode: "inherit", approvalDefault: true });
  await signIn(page);

  // Sidebar badge, Home queue and the Requests tab all agree.
  await expect(page.getByRole("link", { name: /Requests\s*1/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Waiting for your approval" })).toBeVisible();
  await page.getByRole("link", { name: /^Requests/ }).first().click();
  await expect(page.getByRole("tab", { name: /Needs approval/ })).toBeVisible();
  await expect(page.getByText("Smoke title")).toBeVisible();
});

test("leaving Connections asks only when something was changed", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.getByRole("link", { name: "Connections", exact: true }).click();
  await expect(page.locator("#tmdbApiKey")).toBeVisible();
  // Untouched: no question.
  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Manual job" })).toBeVisible();

  await page.getByRole("link", { name: "Connections", exact: true }).click();
  await page.locator("#tmdbApiKey").fill("edited-key");
  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Leave without saving?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(page.locator("#tmdbApiKey")).toHaveValue("edited-key");

  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await page.getByRole("dialog", { name: "Leave without saving?" }).getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByRole("heading", { name: "Manual job" })).toBeVisible();
});

test("the job dialog closes on Escape and asks before discarding edits", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await page.getByRole("button", { name: "New job" }).click();
  const jobDialog = page.getByRole("dialog", { name: "New job" });
  await expect(jobDialog.locator("#jobName")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(jobDialog).toBeHidden();

  await page.getByRole("button", { name: "New job" }).click();
  await jobDialog.locator("#jobName").fill("Draft job");
  await page.keyboard.press("Escape");
  const confirm = page.getByRole("dialog", { name: "Discard your changes?" });
  await confirm.getByRole("button", { name: "Keep editing" }).click();
  await expect(jobDialog.locator("#jobName")).toHaveValue("Draft job");

  await jobDialog.getByRole("button", { name: "Cancel" }).click();
  await confirm.getByRole("button", { name: "Discard" }).click();
  await expect(jobDialog).toBeHidden();
});

test("the setup wizard reports an import it cannot read", async ({ page }) => {
  await mockApi(page, { setupCompleted: false });
  await signIn(page, /\/setup$/);

  await page.locator('input[type="file"]').setInputFiles({ name: "broken.json", mimeType: "application/json", buffer: Buffer.from("not json") });
  await expect(page.getByText("Failed to import: Invalid file format")).toBeVisible();
});

test("the trailer button does not move the details when it arrives", async ({ page }) => {
  await mockApi(page);
  let answerTrailer;
  const trailerAnswered = new Promise(resolve => { answerTrailer = resolve; });
  // Registered after mockApi, so it wins for this path; held until the layout is measured.
  await page.route("http://localhost:5000/api/tmdb/details/**", async (route) => {
    await trailerAnswered;
    await route.fulfill({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" },
      body: JSON.stringify({ trailer_url: "https://www.youtube.com/watch?v=e2e" }),
    });
  });
  await signIn(page);

  await page.getByRole("button", { name: /Smoke title/ }).first().click();
  const dialog = page.getByRole("dialog", { name: "Smoke title" });
  const heading = dialog.getByRole("heading", { name: "Smoke title" });
  await expect(heading).toBeVisible();
  const before = await heading.boundingBox();

  answerTrailer();
  const trailerButton = dialog.getByRole("button", { name: "Watch trailer" });
  await expect(trailerButton).toBeVisible();
  expect(await heading.boundingBox()).toEqual(before);

  await trailerButton.click();
  await expect(page.locator('iframe[src^="https://www.youtube-nocookie.com/embed/"]')).toBeVisible();
});

test("a fully detailed request fits its dialog without scrolling and links to the library and Seer", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page);
  const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" };
  const fulfill = (route, body) => route.fulfill({ contentType: "application/json", headers: cors, body: JSON.stringify(body) });
  await page.route("http://localhost:5000/api/automation/requests?**", route => fulfill(route, {
    data: [{
      source_id: "100", source_title: "Fantastic Beasts: The Crimes of Grindelwald", media_type: "movie",
      requests: [{
        request_id: "155", title: "The Dark Knight", media_type: "movie", requested_at: "2030-01-01T10:00:00Z",
        overview: "Batman raises the stakes in his war on crime. With the help of Lt. Jim Gordon and District Attorney Harvey Dent, Batman sets out to dismantle the remaining criminal organizations that plague the streets. The partnership proves to be effective, but they soon find themselves prey to a reign of chaos.",
        release_date: "2008-07-16", rating: 8.5, user_id: "u1", user_name: "giuseppe",
        rationale: "Given your interest in Spider-Man and 2001: A Space Odyssey, you seem to appreciate well-crafted superhero films with darker themes and strong visuals. The Dark Knight boasts a TMDB rating of 9.0 and aligns with the action and adventure genres.",
        availability: "available", media_url: "http://192.168.1.20:8096/web/index.html#!/details?id=abc",
      }],
    }],
    total_pages: 1, total_sources: 1, total_requests: 1, request_users: [],
  }));
  await page.route("http://localhost:5000/api/tmdb/details/**", route => fulfill(route, {
    trailer_url: "https://www.youtube.com/watch?v=e2e", genres: ["Action", "Thriller", "Crime"], runtime: 152, region: "IT",
    cast: ["Christian Bale", "Heath Ledger", "Aaron Eckhart", "Michael Caine", "Maggie Gyllenhaal", "Gary Oldman"].map(name => ({ name, character: "Role", profile_path: null })),
    providers: [{ name: "Netflix", logo_path: "/netflix.png" }],
  }));
  await page.route("http://localhost:5000/api/seer/web-url", route => fulfill(route, { url: "http://192.168.1.5:5055" }));
  await signIn(page);
  await page.getByRole("button", { name: "Show details for The Dark Knight" }).click();
  const dialog = page.getByRole("dialog", { name: "The Dark Knight" });
  await expect(dialog.getByRole("link", { name: "Watch now" })).toHaveAttribute("href", "http://192.168.1.20:8096/web/index.html#!/details?id=abc");
  await expect(dialog.getByRole("link", { name: "Seer" })).toHaveAttribute("href", "http://192.168.1.5:5055/movie/155");
  await expect(dialog.getByText("Available to watch")).toBeVisible();
  await expect(dialog.getByText("Action, Thriller, Crime")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Show all 6 cast members" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("details-modal.png") });

  const scroller = dialog.locator(".overflow-y-auto").first();
  expect(await scroller.evaluate(el => el.scrollHeight - el.clientHeight)).toBeLessThanOrEqual(1);
});

test("the light theme is chosen in the profile, applies at once and survives a reload", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ colorScheme: "dark" });
  await mockApi(page);
  const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" };
  await page.route("http://localhost:5000/api/automation/requests?**", route => route.fulfill({
    contentType: "application/json", headers: cors, body: JSON.stringify({
      data: [{ source_id: "100", source_title: "Fantastic Beasts", media_type: "movie", requests: [
        { request_id: "155", title: "The Dark Knight", media_type: "movie", requested_at: "2030-01-01T10:00:00Z", rating: 8.5, user_name: "giuseppe", availability: "available", rationale: "Darker superhero films with strong visuals." },
        { request_id: "156", title: "Mortal Engines", media_type: "movie", requested_at: "2030-01-01T09:00:00Z", rating: 6.2, user_name: "giuseppe", availability: "processing" },
      ] }],
      total_pages: 1, total_sources: 1, total_requests: 2, request_users: [],
    }),
  }));
  await signIn(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.getByRole("link", { name: "Profile", exact: true }).first().click();
  await page.getByRole("radio", { name: "Light" }).check({ force: true });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({ path: testInfo.outputPath("light-profile.png") });

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(244, 245, 249)");

  await page.getByRole("link", { name: "Home", exact: true }).first().click();
  await expect(page.getByText("The Dark Knight").first()).toBeVisible();
  await page.waitForTimeout(1000); // let the page transition finish before the screenshot
  await page.screenshot({ path: testInfo.outputPath("light-home.png"), fullPage: true });
  await page.getByRole("button", { name: "Show details for The Dark Knight" }).click();
  await page.screenshot({ path: testInfo.outputPath("light-modal.png") });
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Jobs", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Manual job" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("light-jobs.png") });
  await page.getByRole("link", { name: /^Requests/ }).first().click();
  await expect(page.getByText("Smoke title")).toBeVisible(); // the page settles on its default tab first
  await page.getByRole("tab", { name: /By watched title/ }).click();
  await expect(page.getByRole("heading", { name: "Fantastic Beasts" })).toBeVisible();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: testInfo.outputPath("light-requests.png"), fullPage: true });
});

test("Home lists titles ready to watch, with a play link and a filtered See all", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page);
  const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" };
  const svg = (hue) => `<svg xmlns="http://www.w3.org/2000/svg" width="780" height="439"><defs><linearGradient id="g"><stop offset="0" stop-color="hsl(${hue},70%,35%)"/><stop offset="1" stop-color="hsl(${hue + 60},70%,20%)"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/></svg>`;
  await page.route("https://image.tmdb.org/**", route => route.fulfill({ contentType: "image/svg+xml", body: svg(route.request().url().includes("knight") ? 220 : 20) }));
  const progressSeen = [];
  const knight = { request_id: "155", title: "The Dark Knight", media_type: "movie", requested_at: "2030-01-02T10:00:00Z", user_name: "giuseppe", availability: "available", media_url: "http://192.168.1.20:8096/web/#!/details?id=abc", backdrop_path: "https://image.tmdb.org/t/p/original/knight.jpg" };
  const babylon = { request_id: "615", title: "Babylon", media_type: "movie", requested_at: "2030-01-01T10:00:00Z", user_name: "giuseppe", availability: "available", backdrop_path: "https://image.tmdb.org/t/p/original/babylon.jpg" };
  const batman = { request_id: "414", title: "The Batman", media_type: "movie", requested_at: "2029-12-01T10:00:00Z", user_name: "giuseppe", availability: "processing" };
  const oppenheimer = { request_id: "872", title: "Oppenheimer", media_type: "movie", requested_at: "2030-01-03T10:00:00Z", user_name: "giuseppe", availability: "available" };
  await page.route("http://localhost:5000/api/automation/requests?**", route => {
    const progress = new URL(route.request().url()).searchParams.get("progress");
    progressSeen.push(progress);
    const requests = progress === "available" ? [knight, babylon, oppenheimer] : [oppenheimer, batman];
    return route.fulfill({ contentType: "application/json", headers: cors, body: JSON.stringify({
      data: [{ source_id: "100", source_title: "Fantastic Beasts", media_type: "movie", requests }],
      total_pages: 1, total_sources: 1, total_requests: requests.length, request_users: [],
    }) });
  });
  await signIn(page);

  const ready = page.locator("section", { has: page.getByRole("heading", { name: "Ready to watch" }) });
  await expect(ready.getByRole("button", { name: /Show details for/ })).toHaveCount(2);
  await expect(ready.getByRole("link", { name: "Watch The Dark Knight now" })).toHaveAttribute("href", "http://192.168.1.20:8096/web/#!/details?id=abc");
  await expect(ready.getByRole("link", { name: "Watch Babylon now" })).toHaveCount(0);
  const play = ready.getByRole("link", { name: "Watch The Dark Knight now" });
  await page.mouse.move(5, 5);
  await expect.poll(() => play.evaluate(el => getComputedStyle(el).opacity)).toBe("0");
  await ready.getByRole("button", { name: "Show details for The Dark Knight" }).hover();
  await expect.poll(() => play.evaluate(el => getComputedStyle(el).opacity)).toBe("1");

  // The newest requests stay in "Recently requested"; a title in both shows only there.
  const recent = page.locator("section", { has: page.getByRole("heading", { name: "Recently requested" }) });
  await expect(recent.getByText("Oppenheimer")).toBeVisible();
  await expect(recent.getByText("The Batman")).toBeVisible();
  await expect(ready.getByText("Oppenheimer")).toHaveCount(0);
  await expect(ready.getByRole("button", { name: /Previous|Next titles/ })).toHaveCount(0); // two fit: no arrows
  await page.waitForTimeout(800);
  await ready.screenshot({ path: testInfo.outputPath("ready-to-watch.png") });

  await ready.getByRole("button", { name: "Show details for The Dark Knight" }).click();
  await expect(page.getByRole("dialog", { name: "The Dark Knight" })).toBeVisible();
  await page.keyboard.press("Escape");

  await ready.getByRole("link", { name: "See all →" }).click();
  await expect(page).toHaveURL(/progress=available/);
  await expect(page.getByRole("combobox").filter({ hasText: "Any progress" })).toHaveValue("available");
  await expect.poll(() => progressSeen.filter(value => value === "available").length).toBeGreaterThan(1);
});

test("a user sets, tests and turns off their personal notifications", async ({ page }) => {
  await mockApi(page);
  const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" };
  const calls = [];
  let saved = null;
  await page.route("http://localhost:5000/api/users/me/notifications**", route => {
    const request = route.request();
    calls.push(`${request.method()} ${new URL(request.url()).pathname}`);
    const reply = (status, body) => route.fulfill({ status, contentType: "application/json", headers: cors, body: JSON.stringify(body) });
    if (request.method() === "PUT") {
      const body = request.postDataJSON();
      if (body.url.includes("192.168")) return reply(400, { error: "Private network addresses are not allowed" });
      saved = body;
      return reply(200, body);
    }
    if (request.method() === "DELETE") { saved = null; return route.fulfill({ status: 204, headers: cors }); }
    if (request.method() === "POST") return reply(202, { queued: true });
    return reply(200, saved || { format: null, url: null });
  });
  await signIn(page);
  await page.getByRole("link", { name: "Profile", exact: true }).first().click();

  const card = page.locator("form", { has: page.getByRole("radiogroup", { name: "Service" }) });
  await card.getByRole("radio", { name: "ntfy" }).check({ force: true });
  await card.getByRole("textbox", { name: /Topic URL/ }).fill("http://192.168.1.5/me");
  await card.getByRole("button", { name: "Save" }).click();
  await expect(card.getByRole("alert")).toHaveText("Private network addresses are not allowed");

  await card.getByRole("textbox", { name: /Topic URL/ }).fill("https://ntfy.sh/giuseppe");
  await card.getByRole("button", { name: "Save" }).click();
  await expect(card.getByRole("status")).toContainText("Saved");
  expect(saved).toEqual({ format: "ntfy", url: "https://ntfy.sh/giuseppe" });

  await card.getByRole("button", { name: "Send test" }).click();
  await expect(card.getByRole("status")).toContainText("Test sent");
  await card.getByRole("button", { name: "Turn off" }).click();
  await expect(card.getByRole("status")).toContainText("turned off");
  await expect(card.getByRole("button", { name: "Send test" })).toHaveCount(0);
  expect(calls).toContain("POST /api/users/me/notifications/test");
});

test("a long Ready to watch row pages by whole cards with arrows instead of a scrollbar", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page);
  const cors = { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" };
  await page.route("https://image.tmdb.org/**", route => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="780" height="439"><rect width="100%" height="100%" fill="#345"/></svg>' }));
  const titles = Array.from({ length: 7 }, (_, i) => ({ request_id: String(900 + i), title: `Title ${i + 1}`, media_type: "movie", requested_at: `2030-01-0${i + 1}T10:00:00Z`, availability: "available", backdrop_path: `https://image.tmdb.org/t/p/original/${i}.jpg` }));
  await page.route("http://localhost:5000/api/automation/requests?**", route => {
    // Ready titles are older than the recent ones, so none of them is hidden as a duplicate.
    const available = new URL(route.request().url()).searchParams.get("progress") === "available";
    const requests = available ? titles : [{ request_id: "1", title: "Newest", media_type: "movie", requested_at: "2030-02-01T10:00:00Z" }];
    return route.fulfill({ contentType: "application/json", headers: cors, body: JSON.stringify({
      data: [{ source_id: "1", source_title: "S", media_type: "movie", requests }], total_pages: 1, total_sources: 1, total_requests: requests.length, request_users: [],
    }) });
  });
  await signIn(page);

  const ready = page.locator("section", { has: page.getByRole("heading", { name: "Ready to watch" }) });
  const cards = ready.locator("article");
  await expect(cards).toHaveCount(7);
  const row = ready.locator(".overflow-x-auto");
  const fits = async () => row.evaluate(el => [...el.children].filter(card => {
    const a = card.getBoundingClientRect(); const b = el.getBoundingClientRect();
    return a.left >= b.left - 1 && a.right <= b.right + 1;
  }).length);
  // Four whole cards, none cut, and no visible scrollbar.
  expect(await fits()).toBe(4);
  expect(await row.evaluate(el => el.offsetHeight - el.clientHeight)).toBe(0);
  await expect(ready.getByRole("button", { name: "Previous titles ready to watch" })).toHaveCount(0);

  // Arrows and play buttons stay hidden until the pointer is over the row / card.
  const next = ready.getByRole("button", { name: "Next titles ready to watch" });
  const opacity = locator => locator.evaluate(el => getComputedStyle(el).opacity);
  await page.mouse.move(5, 5);
  await expect.poll(() => opacity(next)).toBe("0");
  await cards.first().hover();
  await expect.poll(() => opacity(next)).toBe("1");

  await next.click();
  await expect(ready.getByRole("button", { name: "Previous titles ready to watch" })).toBeVisible();
  await expect(ready.getByRole("button", { name: "Next titles ready to watch" })).toHaveCount(0);
  await page.waitForTimeout(600);
  expect(await row.evaluate(el => [...el.children].find(card => card.getBoundingClientRect().left >= el.getBoundingClientRect().left - 1).textContent)).toContain("Title 4");
  await ready.screenshot({ path: testInfo.outputPath("ready-row-paged.png") });
});

// SuggestArr landing: latest releases, screenshot viewer and copy button. Never parses HTML: every node is built with
// createElement/textContent, so release text cannot add markup, run script or load resources.
// Written next to the page by the "Update landing" workflow on every release (same origin, no rate limit).
const RELEASES_URL = "releases.json";

function el(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeHttpsUrl(raw) {
  try {
    const url = new URL(raw);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

// Inline markdown subset: `code`, ![alt](url) and [text](url) as https links, **strong**, *em*, _em_.
// Link destinations may contain one level of balanced parentheses, e.g. javascript:alert(1).
const INLINE = /`([^`]+)`|!\[([^\]]*)\]\(((?:[^()]|\([^()]*\))*)\)|\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)|\*\*(.+?)\*\*|\*([^*\s][^*]*?)\*|(?<![\w])_([^_\s][^_]*?)_(?![\w])/g;

function appendInline(parent, text) {
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    const [whole, code, imgAlt, imgUrl, linkText, linkUrl, strong, em1, em2] = m;
    if (code !== undefined) {
      parent.append(el("code", code));
    } else if (imgUrl !== undefined || linkUrl !== undefined) {
      const label = imgUrl !== undefined ? imgAlt || "image" : linkText;
      const dest = (imgUrl ?? linkUrl).trim();
      const href = /\s/.test(dest) ? null : safeHttpsUrl(dest);
      if (href) {
        const a = el("a");
        a.href = href;
        a.rel = "noopener noreferrer";
        appendInline(a, label);
        parent.append(a);
      } else {
        appendInline(parent, label);
      }
    } else if (strong !== undefined) {
      const s = el("strong");
      appendInline(s, strong);
      parent.append(s);
    } else {
      const e = el("em");
      appendInline(e, em1 ?? em2);
      parent.append(e);
    }
    last = m.index + whole.length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

// Block markdown subset: headings, lists (flattened), ---, > quotes, paragraphs. Returns a fragment.
export function renderMarkdown(source) {
  const frag = document.createDocumentFragment();
  const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
  const headings = [];
  let para = null;
  let list = null;
  let quote = null;

  const close = () => { para = null; list = null; quote = null; };

  for (const line of lines) {
    if (!line.trim()) { close(); continue; }

    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      close();
      const h = el("h4");
      appendInline(h, heading[2]);
      headings.push([h, heading[1].length]);
      frag.append(h);
      continue;
    }
    if (/^\s{0,3}([-*_])(\s*\1){2,}\s*$/.test(line)) { close(); frag.append(el("hr")); continue; }

    const q = line.match(/^\s{0,3}>\s?(.*)$/);
    if (q) {
      if (!quote) { para = null; list = null; quote = el("blockquote"); frag.append(quote); }
      if (!q[1].trim()) { para = null; continue; }
      if (!para) { para = el("p"); quote.append(para); } else { para.append(" "); }
      appendInline(para, q[1]);
      continue;
    }

    const item = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
    if (item) {
      const tag = /\d/.test(item[1]) ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== tag) {
        para = null; quote = null;
        list = el(tag);
        frag.append(list);
      }
      const li = el("li");
      appendInline(li, item[2]);
      list.append(li);
      continue;
    }

    if (list && /^\s+\S/.test(line)) { // indented continuation of the last list item
      list.lastElementChild.append(" ");
      appendInline(list.lastElementChild, line.trim());
      continue;
    }

    if (quote) para = null; // leaving a blockquote: start a fresh top-level paragraph
    quote = null;
    list = null;
    if (!para) { para = el("p"); frag.append(para); } else { para.append(" "); }
    appendInline(para, line.trim());
  }

  // Renumber headings under the release <h3>: first is h4, never more than one level deeper than the previous.
  const min = Math.min(...headings.map(([, level]) => level));
  let prev = 3;
  for (const [node, level] of headings) {
    const target = Math.min(6, 4 + (level - min), prev + 1);
    const h = el(`h${target}`);
    h.append(...node.childNodes);
    node.replaceWith(h);
    prev = target;
  }
  return frag;
}

function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString("en", { year: "numeric", month: "long", day: "numeric" });
}

function releaseCard(release) {
  const tag = String(release.tag_name || "");
  const details = el("details");
  details.className = "release";

  const summary = el("summary");
  summary.append(el("span", tag));
  summary.firstChild.className = "release-version";
  const time = el("time", formatDate(release.published_at));
  time.className = "release-date";
  if (time.textContent) time.dateTime = String(release.published_at);
  summary.append(time);

  const body = el("div");
  body.className = "release-body";
  const title = el("h3", `Release ${tag}`);
  title.className = "visually-hidden";
  body.append(title, renderMarkdown(release.body || "No release notes."));

  const url = safeHttpsUrl(release.html_url);
  if (url && url.startsWith("https://github.com/")) {
    const more = el("p");
    more.className = "release-more";
    const a = el("a", `${tag} on GitHub`);
    a.href = url;
    more.append(a);
    body.append(more);
  }
  details.append(summary, body);
  return details;
}

async function loadReleases() {
  const list = document.getElementById("release-list");
  if (!list) return;
  list.replaceChildren(el("p", "Loading releases…"));
  list.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(RELEASES_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`releases.json ${response.status}`);
    const releases = await response.json();
    if (!Array.isArray(releases) || releases.length === 0) throw new Error("No releases");
    list.replaceChildren(...releases.slice(0, 3).map(releaseCard));
  } catch (error) {
    console.warn("Could not load releases:", error);
    list.replaceChildren(el("p", "Could not load the latest releases right now. They are all on GitHub, linked below."));
  } finally {
    list.removeAttribute("aria-busy");
  }
}

function setUpCopy() {
  if (!navigator.clipboard) return;
  const status = document.querySelector(".status");
  for (const button of document.querySelectorAll("[data-copy]")) {
    const source = document.getElementById(button.dataset.copy);
    if (!source) continue;
    button.hidden = false;
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(source.textContent);
        status.textContent = "Copied to the clipboard.";
      } catch {
        status.textContent = "Could not copy. Select the text and copy it by hand.";
      }
    });
  }
}

// Screenshot links open the image in a modal <dialog>; without JS they open the file itself.
function setUpViewer() {
  const dialog = document.getElementById("viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const frame = dialog.querySelector(".viewer-frame");
  dialog.querySelector(".viewer-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => frame.replaceChildren());
  for (const link of document.querySelectorAll(".shot a")) {
    link.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const thumb = link.querySelector("img");
      const img = el("img");
      img.src = link.href;
      img.alt = thumb ? thumb.alt : "";
      img.width = 1440;
      img.height = 900;
      frame.replaceChildren(img);
      dialog.showModal();
    });
  }
}

setUpCopy();
setUpViewer();
loadReleases();

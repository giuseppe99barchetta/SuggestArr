const REPO_URL = 'https://github.com/giuseppe99barchetta/SuggestArr';

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Renders inline markdown on already-escaped text: code spans, links, bare URLs,
 * #issue and @user references, bold and italic.
 * Code spans and links are swapped for placeholders first so nothing inside them is touched again.
 */
function renderInline(text) {
  const slots = [];
  const stash = (html) => `${slots.push(html) - 1}`;

  const html = text
    .replace(/`([^`\n]+)`/g, (_, code) => stash(`<code>${code}</code>`))
    // Only http(s) targets, so release notes cannot smuggle in a javascript: URL.
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_, label, url) =>
      stash(`<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`))
    .replace(/https?:\/\/[^\s<]+[^\s<.,;:!?)]/g, (url) => {
      const pull = url.match(/\/(?:pull|issues)\/(\d+)$/);
      return stash(`<a href="${url}" target="_blank" rel="noopener noreferrer">${pull ? `#${pull[1]}` : url}</a>`);
    })
    .replace(/(^|[\s(])#(\d+)\b/g, (_, lead, num) =>
      `${lead}${stash(`<a href="${REPO_URL}/issues/${num}" target="_blank" rel="noopener noreferrer">#${num}</a>`)}`)
    .replace(/(^|[\s(])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\b/g, (_, lead, user) =>
      `${lead}${stash(`<a href="https://github.com/${user}" target="_blank" rel="noopener noreferrer">@${user}</a>`)}`)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');

  return html.replace(/(\d+)/g, (_, i) => slots[Number(i)]);
}

const HEADING = /^(#{1,6})\s+(.*?)\s*#*$/;
const RULE = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const LIST_ITEM = /^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$/;
const FENCE = /^\s*```/;

/**
 * Builds nested <ul>/<ol> markup from collected list lines.
 * @param {Array<{indent: number, ordered: boolean, text: string}>} items
 * @returns {string}
 */
function renderList(items) {
  let html = '';
  const stack = [];
  for (const item of items) {
    while (stack.length && item.indent < stack[stack.length - 1].indent) {
      html += `</li></${stack.pop().tag}>`;
    }
    const top = stack[stack.length - 1];
    if (!top || item.indent > top.indent) {
      const tag = item.ordered ? 'ol' : 'ul';
      stack.push({ indent: item.indent, tag });
      html += `<${tag}>`;
    } else {
      html += '</li>';
    }
    html += `<li>${renderInline(item.text)}`;
  }
  while (stack.length) html += `</li></${stack.pop().tag}>`;
  return html;
}

/**
 * Turns GitHub release notes into a small, safe HTML subset for the changelog dialog.
 * Input is escaped first; only headings, paragraphs, rules, (nested) lists, quotes,
 * code, emphasis and http(s) links survive.
 * @param {string} markdown - Raw release body from the GitHub API.
 * @returns {string} HTML safe to bind with v-html.
 */
export function releaseNotesToHtml(markdown) {
  if (!markdown) return '';

  const lines = escapeHtml(markdown.replace(/\r\n?/g, '\n')).split('\n');
  const out = [];
  let paragraph = [];
  let list = [];
  let quote = [];

  const flushParagraph = () => {
    if (paragraph.length) out.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list.length) out.push(renderList(list));
    list = [];
  };
  const flushQuote = () => {
    if (quote.length) out.push(`<blockquote>${quote.map(renderInline).join('<br>')}</blockquote>`);
    quote = [];
  };
  const flushAll = () => { flushParagraph(); flushList(); flushQuote(); };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (FENCE.test(line)) {
      flushAll();
      const code = [];
      while (++i < lines.length && !FENCE.test(lines[i])) code.push(lines[i]);
      out.push(`<pre><code>${code.join('\n')}</code></pre>`);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushQuote();
      // A blank line only ends a list when the next content is not another item.
      const next = lines.slice(i + 1).find(l => l.trim());
      if (!next || !LIST_ITEM.test(next)) flushList();
      continue;
    }

    if (RULE.test(line)) {
      flushAll();
      out.push('<hr>');
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      flushAll();
      const tag = `h${Math.min(heading[1].length + 1, 4)}`;
      out.push(`<${tag}>${renderInline(heading[2])}</${tag}>`);
      continue;
    }

    const item = line.match(LIST_ITEM);
    if (item) {
      flushParagraph();
      flushQuote();
      list.push({ indent: item[1].length, ordered: /^\s*\d/.test(line), text: item[2] });
      continue;
    }

    const quoted = line.match(/^&gt;\s?(.*)$/);
    if (quoted) {
      flushParagraph();
      flushList();
      quote.push(quoted[1]);
      continue;
    }

    // A wrapped line right after a list item belongs to that item.
    if (list.length && !paragraph.length) {
      list[list.length - 1].text += ` ${line.trim()}`;
      continue;
    }

    flushList();
    flushQuote();
    paragraph.push(line.trim());
  }
  flushAll();

  return out.join('');
}

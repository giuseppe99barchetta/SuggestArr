/**
 * Turns GitHub release notes into a small, safe HTML subset for the changelog dialog.
 * Input is escaped first; only headings, bold, italic, bullet lists and http(s) links survive.
 */
export function releaseNotesToHtml(markdown) {
  if (!markdown) return '';

  const escaped = markdown
    .replace(/\r\n?/g, '\n')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const html = escaped
    .replace(/^### (.*)$/gm, '<h4>$1</h4>')
    .replace(/^## (.*)$/gm, '<h3>$1</h3>')
    .replace(/^# (.*)$/gm, '<h2>$1</h2>')
    // Each run of "- " or "* " lines becomes one list, before "*" can be read as emphasis.
    .replace(/(?:^[-*] .*(?:\n|$))+/gm, (block) => {
      const items = block.trim().split('\n').map(line => `<li>${line.slice(2)}</li>`);
      return `<ul>${items.join('')}</ul>\n`;
    })
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
    // Only http(s) targets, so release notes cannot smuggle in a javascript: URL.
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  return html
    .replace(/(<\/(?:h2|h3|h4|ul)>)\n/g, '$1')
    .replace(/\n/g, '<br>');
}

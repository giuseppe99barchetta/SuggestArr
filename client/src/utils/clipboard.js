/**
 * Copies text to the clipboard. Returns false when the browser refuses.
 * The clipboard API needs HTTPS or localhost; plain-HTTP LAN installs fall back to execCommand.
 */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = Object.assign(document.createElement('textarea'), { value: text });
    textarea.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    return copied;
  }
}

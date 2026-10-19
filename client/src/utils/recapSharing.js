/** Keep the locally generated PNG with every sharing path. */
export function canCopyRecapImage() {
  return typeof ClipboardItem !== 'undefined' && typeof navigator.clipboard?.write === 'function';
}

export function canShareRecapImage(blob) {
  if (!blob || typeof navigator.share !== 'function' || typeof navigator.canShare !== 'function') return false;
  try { return navigator.canShare({ files: [new File([blob], 'suggestarr-recap.png', { type: 'image/png' })] }); }
  catch { return false; }
}

export function copyRecapImage(blob) {
  return navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
}

export async function prepareRecapImage({ blob, download, save = false }) {
  // Start clipboard access in the click handler. Never overwrite the PNG with
  // writeText afterwards: social composers already receive the caption in their URL.
  let copying;
  try { if (canCopyRecapImage()) copying = Promise.resolve(copyRecapImage(blob)); }
  catch { /* A denied clipboard falls back to the local download. */ }
  if (save) download();
  try {
    if (copying) { await copying; return 'copied'; }
  } catch { /* Clipboard permission can be refused despite API availability. */ }
  if (!save) download();
  return 'downloaded';
}

// Compares numeric dot parts (3.10.0 > 3.9.0); a leading "v" and suffixes like "-nightly" are ignored.
export function isNewerVersion(latest, current) {
  const parts = (v) => String(v).replace(/^v/, "").split(/[-+]/)[0].split(".").map((n) => parseInt(n, 10) || 0);
  const a = parts(latest);
  const b = parts(current);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const diff = (a[i] || 0) - (b[i] || 0);
    if (diff) return diff > 0;
  }
  return false;
}

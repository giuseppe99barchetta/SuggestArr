/**
 * localStorage access that never throws. With site data blocked or in some private modes even
 * touching `localStorage` raises, and these values are only conveniences, so failures are ignored.
 */

/**
 * Read a stored value.
 * @param {string} key - Storage key.
 * @returns {string|null} The value, or null when missing or storage is unavailable.
 */
export function readStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Store a value; does nothing when storage is unavailable.
 * @param {string} key - Storage key.
 * @param {string} value - Value to store.
 */
export function writeStorage(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Without storage the value lasts only for this visit.
  }
}

/**
 * Remove a stored value; does nothing when storage is unavailable.
 * @param {string} key - Storage key.
 */
export function removeStorage(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Nothing stored to remove.
  }
}

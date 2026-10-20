/**
 * Light/dark theme. The choice is per browser ('system' follows the OS) and is applied
 * by setting <html data-theme>, which main.css reads. index.html applies it before the
 * app loads so a light page does not flash dark first.
 */
export const THEME_KEY = 'suggestarr_theme';
export const THEME_CHOICES = ['system', 'light', 'dark'];

// Browser chrome colour (address bar, installed-app title bar) per theme: the page canvas.
const THEME_COLORS = { dark: '#0b0d12', light: '#f4f5f9' };

/** @returns {'system'|'light'|'dark'} The saved choice; 'system' when unset or unreadable. */
export function readThemeChoice(storage = globalThis.localStorage) {
  try {
    const saved = storage?.getItem(THEME_KEY);
    return THEME_CHOICES.includes(saved) ? saved : 'system';
  } catch {
    return 'system';
  }
}

/**
 * @param {'system'|'light'|'dark'} choice
 * @param {boolean} systemPrefersDark
 * @returns {'light'|'dark'}
 */
export function resolveTheme(choice, systemPrefersDark) {
  if (choice === 'light' || choice === 'dark') return choice;
  return systemPrefersDark ? 'dark' : 'light';
}

function systemQuery() {
  return globalThis.matchMedia?.('(prefers-color-scheme: dark)');
}

/** Put the resolved theme on the page. */
export function applyTheme(choice = readThemeChoice()) {
  const theme = resolveTheme(choice, systemQuery()?.matches ?? true);
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme]);
  return theme;
}

/**
 * Apply a theme change with a short cross-fade of the whole page. The browser animates two
 * snapshots (View Transitions API), so it costs nothing per element; without support, or
 * with reduced motion requested, the change is instant.
 */
function applyThemeAnimated(choice) {
  const reduceMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (!document.startViewTransition || reduceMotion) return applyTheme(choice);
  document.documentElement.classList.add('theme-switching');
  const transition = document.startViewTransition(() => applyTheme(choice));
  transition.finished.finally(() => document.documentElement.classList.remove('theme-switching'));
  return resolveTheme(choice, systemQuery()?.matches ?? true);
}

/** Save a new choice and apply it. */
export function setThemeChoice(choice) {
  try {
    localStorage.setItem(THEME_KEY, choice);
  } catch {
    // Without storage the choice still applies until the page is reloaded.
  }
  return applyThemeAnimated(choice);
}

/** Apply the saved theme and follow OS changes while the choice is 'system'. */
export function initTheme() {
  applyTheme();
  systemQuery()?.addEventListener?.('change', () => {
    if (readThemeChoice() === 'system') applyThemeAnimated('system');
  });
}

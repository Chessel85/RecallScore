// Settings kept across visits, in localStorage. The browser's stand-in for
// the desktop's settings.json (global) and its per-score .rsc files.
//
// The shapes are Python's, not this module's: the global settings are
// web_api.global_settings_json() text (AppSettings), each score's is
// web_api.score_settings_json() text (the desktop .rsc shape, from
// models/score_config_json.py). This module only keeps them.
//
// A score is known by the SHA-256 of its bytes, not its name (the desktop
// keys by file name; a browser upload has no folder to tell two apart, and
// the same bytes under a new name are still the same score).
//
// Every storage call is wrapped: a private window, blocked site data or a
// full quota must never stop the page. Reads then find nothing and writes
// are lost, so settings last only for the session; `onFailure` is told
// once, the first time a write fails.

const GLOBAL_KEY = "recallscore.settings";
const SCORE_PREFIX = "recallscore.score.";

let failureReported = false;
let onFailure = () => {};

/** `failure(text)` is called once, on the first write that fails. */
export function initStorage({ failure } = {}) {
  onFailure = failure ?? onFailure;
}

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    if (!failureReported) {
      failureReported = true;
      onFailure("This browser is not keeping Recall Score's settings, so changes last only until the page is closed.");
    }
    return false;
  }
}

// --- global settings -----------------------------------------------------------

/** The stored global settings text, or null. */
export function loadGlobal() {
  return read(GLOBAL_KEY);
}

export function saveGlobal(text) {
  if (text) write(GLOBAL_KEY, text);
}

// --- per-score settings ------------------------------------------------------------

/** The score's key: SHA-256 of its bytes as hex, or null where the browser
 * offers no digest (an insecure page), which turns per-score settings off. */
export async function scoreKey(bytes) {
  try {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}

function readEntry(key) {
  try {
    const entry = JSON.parse(read(SCORE_PREFIX + key));
    return entry && typeof entry === "object" && entry.config && typeof entry.config === "object" ? entry : null;
  } catch {
    return null;
  }
}

/** The score's stored .rsc text, or null. */
export function loadScore(key) {
  const entry = key ? readEntry(key) : null;
  return entry ? JSON.stringify(entry.config) : null;
}

/** Keep `configText` (.rsc text) for the score `key`. The file name is
 * kept beside it only so a person looking at the stored data can tell
 * which score is which. */
export function saveScore(key, name, configText) {
  if (!key || !configText) return;
  const entry = { name, saved: new Date().toISOString(), config: JSON.parse(configText) };
  write(SCORE_PREFIX + key, JSON.stringify(entry));
}

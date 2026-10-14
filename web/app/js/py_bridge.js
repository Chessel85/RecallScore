// Boots Pyodide, unpacks the shared Python code staged by tools/stage_web.py
// into py/shared.zip, and wraps web/py/web_api.py. Promoted from the Phase 0
// spike's pyodide_boot.js; no music21 stub is needed any more.

export const PYODIDE_VERSION = "314.0.7";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const SHARED_DIR = "/home/pyodide/shared";

let api = null;

/** Boots Python once. onStatus receives short progress sentences. */
export async function boot(onStatus) {
  onStatus?.("Loading Python runtime.");
  const { loadPyodide } = await import(`${INDEX_URL}pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: INDEX_URL });

  onStatus?.("Loading Recall Score code.");
  const zipResponse = await fetch("../py/shared.zip");
  if (!zipResponse.ok) throw new Error(`../py/shared.zip: HTTP ${zipResponse.status}`);
  pyodide.FS.mkdirTree(SHARED_DIR);
  pyodide.unpackArchive(await zipResponse.arrayBuffer(), "zip", { extractDir: SHARED_DIR });

  const bridgeResponse = await fetch("../py/web_api.py");
  if (!bridgeResponse.ok) throw new Error(`../py/web_api.py: HTTP ${bridgeResponse.status}`);
  pyodide.FS.writeFile(`${SHARED_DIR}/web_api.py`, await bridgeResponse.text());
  pyodide.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(SHARED_DIR)})`);
  api = pyodide.pyimport("web_api");
}

function toJs(proxy) {
  const value = proxy.toJs({ dict_converter: Object.fromEntries });
  proxy.destroy?.();
  return value;
}

/** Returns {ok, summary, view} or {error}. Never throws for a bad score. */
export function loadScore(bytes, filename) {
  try {
    return toJs(api.load(bytes, filename));
  } catch (err) {
    return { error: `Could not open ${filename}: ${err.message}` };
  }
}

// The rest wrap web_api.py one to one; see its docstrings for the shapes.
// A Python exception comes back as {error}, so a bug shows up as a message
// rather than a dead key.
function call(name, ...args) {
  try {
    const result = api[name](...args);
    return result && typeof result.toJs === "function" ? toJs(result) : result;
  } catch (err) {
    return { error: `${name} failed: ${err.message}` };
  }
}

export const view = () => call("view");
export const regionRows = (region, selection = null) => call("region_rows", region, selection);
/** direction: "left", "right", "bar_left", "bar_right", "first", "last". */
export const move = (direction) => call("move", direction);
export const gotoBar = (measure) => call("goto_bar", measure);
export const jumpPoint = (direction) => call("jump_point", direction);
export const section = (delta) => call("section", delta);
export const selectionChanged = (selection) => call("selection_changed", selection);
export const attributeAnnouncement = (number, selection = null) =>
  call("attribute_announcement", number, selection) ?? null;
export const setUkTerms = (ukTerms) => call("set_uk_terms", ukTerms);
export const gotoInfo = () => call("goto_info");
export const appendDigit = (digit) => call("append_digit", digit);
export const commitDigits = () => call("commit_digits");
export const clearDigits = () => call("clear_digits");
/** kind: "mute" or "solo". */
export const region2Toggle = (nodeId, kind) => call("region2_toggle", nodeId, kind);
export const region2Clear = (kind) => call("region2_clear", kind);
export const synthSetup = () => call("synth_setup");
/** Sound Region 3's selection without moving; see web_api.audition. */
export const audition = (selection, withPositionCues = false) => call("audition", selection, withPositionCues);
/** kind: "metronome", "position_announcer" or "bar_line_indicator". */
export const toggle = (kind) => call("toggle", kind);
// Playback (see the "playback" section of web_api.py).
export const playToggle = () => call("play_toggle");
export const playPlan = (session, untilMs) => call("play_plan", session, untilMs);
export const playCursor = (session, index) => call("play_cursor", session, index);
export const playEnded = (session) => call("play_ended", session);
export const playPause = (session, seq) => call("play_pause", session, seq);
export const playStop = () => call("play_stop");

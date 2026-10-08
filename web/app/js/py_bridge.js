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

/** Returns {ok, summary} or {error}. Never throws for a bad score. */
export function loadScore(bytes, filename) {
  try {
    return toJs(api.load(bytes, filename));
  } catch (err) {
    return { error: `Could not open ${filename}: ${err.message}` };
  }
}

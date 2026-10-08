// Boots Pyodide and unpacks the shared models/ + parsers/ code staged by
// tools/stage_web.py into py/shared.zip. Used by spikes 1 and 5.

export const PYODIDE_VERSION = "314.0.7";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
export const SHARED_DIR = "/home/pyodide/shared";
const STUB_DIR = "/home/pyodide/stub";

/**
 * Returns { pyodide, timings } where timings holds milliseconds for each
 * stage, so the spike can report first-load against cached-load cost.
 * withMusic21Stub puts a stand-in music21 package on sys.path (spike 1);
 * spike 5 installs the real one instead.
 */
export async function bootPyodide({ withMusic21Stub, onStatus }) {
  const timings = {};
  let t = performance.now();
  const { loadPyodide } = await import(`${INDEX_URL}pyodide.mjs`);
  timings.fetchLoaderMs = performance.now() - t;

  onStatus?.("Loading Python runtime.");
  t = performance.now();
  const pyodide = await loadPyodide({ indexURL: INDEX_URL });
  timings.loadPyodideMs = performance.now() - t;

  onStatus?.("Loading Recall Score code.");
  t = performance.now();
  const response = await fetch("../py/shared.zip");
  if (!response.ok) throw new Error(`py/shared.zip: HTTP ${response.status}. Run tools/stage_web.py first.`);
  const zipBytes = await response.arrayBuffer();
  pyodide.FS.mkdirTree(SHARED_DIR);
  pyodide.unpackArchive(zipBytes, "zip", { extractDir: SHARED_DIR });
  timings.sharedCodeMs = performance.now() - t;
  timings.sharedZipBytes = zipBytes.byteLength;

  if (withMusic21Stub) {
    const stub = await (await fetch("music21_stub.py")).text();
    pyodide.FS.mkdirTree(`${STUB_DIR}/music21`);
    pyodide.FS.writeFile(`${STUB_DIR}/music21/__init__.py`, stub);
  }
  pyodide.runPython(`
import sys
for p in (${JSON.stringify(SHARED_DIR)}, ${withMusic21Stub ? JSON.stringify(STUB_DIR) : "None"}):
    if p and p not in sys.path:
        sys.path.insert(0, p)
`);
  return { pyodide, timings };
}

/** Runs a .py file next to the page as a module-level script. */
export async function runPyFile(pyodide, name) {
  const source = await (await fetch(name)).text();
  pyodide.runPython(source);
}

import { status, log, report, wireCopyButton, median, ms } from "./common.js";
import { bootPyodide, runPyFile, PYODIDE_VERSION } from "./pyodide_boot.js";

wireCopyButton();
const pageStart = performance.now();
let pyodide;
let largest = null; // { path, slices }

async function main() {
  try {
    const boot = await bootPyodide({ withMusic21Stub: true, onStatus: status });
    pyodide = boot.pyodide;
    await runPyFile(pyodide, "spike1.py");
    const imported = JSON.parse(pyodide.globals.get("import_shared")());
    const t = boot.timings;
    report(`Pyodide ${PYODIDE_VERSION}`);
    report(`Load: fetch loader ${ms(t.fetchLoaderMs)}, loadPyodide ${ms(t.loadPyodideMs)}, shared code ${ms(t.sharedCodeMs)} (${Math.round(t.sharedZipBytes / 1024)} KB zip), import MusicXML path ${ms(imported.import_ms)}, music21 stub ${imported.music21_stub ? "yes" : "no"}`);
    report(`Page open to ready: ${ms(performance.now() - pageStart)}`);
    status(`Python ready after ${ms(performance.now() - pageStart)}.`);
    for (const id of ["parse-all", "file"]) document.getElementById(id).disabled = false;
  } catch (err) {
    status(`Failed to start Python: ${err.message}`);
    report(`BOOT FAILED: ${err.message}`);
  }
}

function parseBytes(bytes, name, label) {
  const path = `/tmp/scores/${name}`;
  pyodide.FS.mkdirTree("/tmp/scores");
  pyodide.FS.writeFile(path, new Uint8Array(bytes));
  const t = performance.now();
  try {
    const result = JSON.parse(pyodide.globals.get("parse")(path));
    const roundTrip = performance.now() - t;
    report(`Parsed ${label}: ${result.slices} positions, ${result.parts} parts, Python ${ms(result.load_ms)}, round trip ${ms(roundTrip)}`);
    if (!largest || result.slices > largest.slices) largest = { path, label, slices: result.slices };
    document.getElementById("step-bench").disabled = false;
    return result;
  } catch (err) {
    report(`FAILED ${label}: ${err.message.split("\n").slice(-2).join(" ")}`);
    return null;
  }
}

document.getElementById("parse-all").addEventListener("click", async () => {
  const response = await fetch("../scores/index.json");
  if (!response.ok) {
    status("No staged scores. Run tools/stage_web.py with --scores.");
    return;
  }
  const entries = await response.json();
  status(`Parsing ${entries.length} scores.`);
  let failures = 0;
  const start = performance.now();
  for (const entry of entries) {
    const bytes = await (await fetch(`../scores/${encodeURIComponent(entry.name)}`)).arrayBuffer();
    if (!parseBytes(bytes, entry.name, entry.label)) failures += 1;
  }
  report(`Parsed ${entries.length} scores in ${ms(performance.now() - start)}, ${failures} failed.`);
  status(`Done. ${entries.length} scores, ${failures} failed.`);
});

document.getElementById("file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const result = parseBytes(await file.arrayBuffer(), file.name, file.name);
  if (result) {
    status(`Parsed ${file.name}. First position: ${result.region3.join(", ")}. ${result.status[0]}.`);
    log(`Region 1: ${JSON.stringify(result.region1)}`);
  }
});

document.getElementById("step-bench").addEventListener("click", () => {
  if (!largest) return;
  // Re-parse so the cursor starts at the top and the timing is of this score.
  pyodide.globals.get("parse")(largest.path);
  const step = pyodide.globals.get("step");
  const times = [];
  for (let i = 0; i < 200; i += 1) {
    const t = performance.now();
    const result = JSON.parse(step());
    times.push(performance.now() - t);
    if (!result.moved) break;
  }
  const sorted = [...times].sort((a, b) => a - b);
  const p95 = sorted[Math.floor(sorted.length * 0.95)];
  const line = `Right Arrow step on ${largest.label} (${times.length} steps): median ${median(times).toFixed(2)} ms, 95th percentile ${p95.toFixed(2)} ms, max ${sorted[sorted.length - 1].toFixed(2)} ms`;
  report(line);
  status(line);
});

main();

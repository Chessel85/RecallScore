import { status, log, report, wireCopyButton, ms } from "./common.js";
import { bootPyodide, PYODIDE_VERSION } from "./pyodide_boot.js";

wireCopyButton();

const FIXTURE = "../scores/tests_fixtures__chords_and_lyrics.musicxml";

async function run() {
  document.getElementById("run").disabled = true;
  try {
    const { pyodide, timings } = await bootPyodide({ withMusic21Stub: false, onStatus: status });
    report(`Pyodide ${PYODIDE_VERSION} loaded in ${ms(timings.loadPyodideMs)}`);

    status("Installing music21. This can take a while.");
    let t = performance.now();
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    try {
      await micropip.install("music21");
    } catch (err) {
      report(`micropip.install("music21") FAILED: ${err.message.split("\n").slice(-3).join(" ")}`);
      status("Installing music21 failed. See the report.");
      return;
    }
    report(`micropip.install("music21"): ${ms(performance.now() - t)} (download plus install)`);
    const packages = pyodide.runPython(`
import json, importlib.metadata as md
json.dumps(sorted(f"{d.metadata['Name']} {d.version}" for d in md.distributions()))
`);
    log(`Installed packages: ${JSON.parse(packages).join(", ")}`);

    t = performance.now();
    pyodide.runPython("from music21 import harmony");
    report(`Import music21.harmony: ${ms(performance.now() - t)}`);

    t = performance.now();
    const chord = pyodide.runPython(`
cs = harmony.ChordSymbol(root="A", kind="minor-seventh")
f"{cs.figure}: {[p.midi for p in cs.pitches]}"
`);
    report(`First ChordSymbol: ${chord}, ${ms(performance.now() - t)}`);

    // The real timeline builder resolving chord pitches with real music21.
    const response = await fetch(FIXTURE);
    if (response.ok) {
      pyodide.FS.writeFile("/tmp/chords.musicxml", new Uint8Array(await response.arrayBuffer()));
      t = performance.now();
      const summary = pyodide.runPython(`
import json
from models.music_data import MusicData
from models.synthetic_parts import CHORDS_PART_ID
md = MusicData(file_path="/tmp/chords.musicxml")
chords = [n for s in md.timeline_slices for n in s.notes if n.part_id == CHORDS_PART_ID]
json.dumps({"chords": len(chords), "with_pitches": sum(1 for n in chords if n.midi_pitch)})
`);
      const result = JSON.parse(summary);
      report(`chords_and_lyrics fixture via the real timeline builder: ${ms(performance.now() - t)}, ${result.chords} chord notes, ${result.with_pitches} with pitches`);
    } else {
      report("chords_and_lyrics fixture not staged (run tools/stage_web.py with --scores); skipped the timeline check");
    }

    const heap = performance.memory ? `${Math.round(performance.memory.usedJSHeapSize / 1048576)} MB JS heap` : "heap size not reported by this browser";
    report(`Memory: ${heap}`);
    status("Done. Copy the report.");
  } catch (err) {
    report(`FAILED: ${err.message.split("\n").slice(-3).join(" ")}`);
    status(`Failed: ${err.message}`);
  }
}

document.getElementById("run").addEventListener("click", run);

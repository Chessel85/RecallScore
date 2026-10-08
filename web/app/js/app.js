import { announce, announceUrgent } from "./announcer.js";
import { bind } from "./keymap.js";
import { initFocus, focusRegion } from "./focus.js";
import { initRegions, render, moveRow, selection, selectAll, rowAt, currentRow } from "./regions.js";
import * as py from "./py_bridge.js";

const status = document.getElementById("status");
const errorBox = document.getElementById("error");
const picker = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const menuButton = document.getElementById("menu-button");
const regionElements = [1, 2, 3, 4, 5, 6].map((n) => document.getElementById(`region-${n}`));

initRegions(regionElements);
initFocus({ menuButton, regions: regionElements });

// The status line is visual only; the announcer speaks, so no double speech.
function say(text) {
  status.textContent = text;
  announce(text);
}

function showError(text) {
  errorBox.textContent = text;
  errorBox.hidden = false;
  errorBox.focus();
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

// Task 2.5 builds the real menu from keymap.js.
menuButton.addEventListener("click", () => announceUrgent("The menu is not built yet."));

// --- drawing bridge results --------------------------------------------------

function showRegions(regions, regionThreeSelection) {
  for (const [key, rows] of Object.entries(regions)) {
    const n = Number(key);
    render(n, rows, n === 3 ? { selection: regionThreeSelection } : {});
  }
}

/** Apply a web_api move result. Speech first, then the redraw, so "Measure
 * 6." is heard before the note list reads the new note (the desktop's
 * RegionPresenter._announce_measure_change order). */
function applyMove(result, { speak = true } = {}) {
  if (result?.error) {
    showError(result.error);
    return;
  }
  if (speak && result.announce) announceUrgent(result.announce);
  if (result.moved) showRegions(result.regions, result.selection);
  // Phase 3 sounds result.boundary (the boundary cue) and result.barline
  // (the bar line indicator, Ctrl+B).
}

function refreshRegionFour() {
  const result = py.selectionChanged(selection());
  if (result?.error) showError(result.error);
  else render(4, result.regions["4"]);
}

// --- commands ----------------------------------------------------------------

let scoreLoaded = false;
const withScore = (fn) => (event, key) => (scoreLoaded ? fn(event, key) : undefined);

bind("nav.left", withScore(() => applyMove(py.move("left"))));
bind("nav.right", withScore(() => applyMove(py.move("right"))));
bind("nav.barLeft", withScore(() => applyMove(py.move("bar_left"))));
bind("nav.barRight", withScore(() => applyMove(py.move("bar_right"))));
bind("nav.first", withScore(() => applyMove(py.move("first"))));
bind("nav.last", withScore(() => applyMove(py.move("last"))));
bind("nav.jumpPrevious", withScore(() => applyMove(py.jumpPoint(-1))));
bind("nav.jumpNext", withScore(() => applyMove(py.jumpPoint(1))));

// Left/Right step sections only on Region 1's section row; elsewhere in
// Region 1 the key declines. Region 1 itself reads the new section row, so
// the bridge's spoken message would only say it twice.
function stepSection(delta) {
  if (!scoreLoaded || rowAt(1, currentRow(1))?.kind !== "section") return false;
  applyMove(py.section(delta), { speak: false });
  return true;
}
bind("nav.sectionPrevious", () => stepSection(-1));
bind("nav.sectionNext", () => stepSection(1));

for (const [id, where] of [["list.previous", "previous"], ["list.next", "next"], ["list.top", "top"], ["list.bottom", "bottom"]]) {
  bind(id, () => {
    const n = regionElements.indexOf(document.activeElement) + 1;
    if (n < 1) return false;
    if (moveRow(n, where) && n === 3 && scoreLoaded) refreshRegionFour();
    return true;
  });
}

bind("notes.selectAll", withScore(() => {
  selectAll();
  refreshRegionFour();
}));

bind("attributes.speak", withScore((event, key) => {
  const text = py.attributeAnnouncement(Number(key.slice(-1)), selection());
  if (text) announceUrgent(text);
}));

// --- loading -------------------------------------------------------------------

let ready = false;

async function openFile(file) {
  if (!ready) {
    showError("Still starting up. Try again in a moment.");
    return;
  }
  clearError();
  say(`Loading ${file.name}.`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  await new Promise((resolve) => setTimeout(resolve, 0)); // let the message paint
  const result = py.loadScore(bytes, file.name);
  if (result.error) {
    showError(result.error);
    return;
  }
  scoreLoaded = true;
  showRegions(result.view.regions, result.view.selection);
  say(`Loaded ${file.name}. ${result.summary.parts.length} parts, ${result.summary.slices} notes and chords.`);
  focusRegion(3);
}

picker.addEventListener("change", () => {
  if (picker.files[0]) openFile(picker.files[0]);
  picker.value = "";
});
dropZone.addEventListener("dragover", (event) => event.preventDefault());
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  if (event.dataTransfer.files[0]) openFile(event.dataTransfer.files[0]);
});

picker.disabled = true;
say("Starting Recall Score.");
py.boot(say)
  .then(() => {
    ready = true;
    picker.disabled = false;
    say("Ready. Choose a score file.");
  })
  .catch((err) => showError(`Could not start: ${err.message}`));

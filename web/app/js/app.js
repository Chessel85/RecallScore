import "./debug.js";
import { announce, announceUrgent } from "./announcer.js";
import { bind } from "./keymap.js";
import { initFocus, focusRegion, focusedRegion, focusMenuButton } from "./focus.js";
import {
  initRegions, render, moveRow, extendSelection, selection, selectAll, rowAt, currentRow, treeExpand, treeCollapse,
} from "./regions.js";
import { showHelp, showGotoBar, showPlaySettings } from "./dialogs.js";
import { initMenu, showContextMenu } from "./menu.js";
import { initAudio, prefetchSoundFonts, play } from "./audio.js";
import { initScheduler, startSession, stopSession, pauseSession, isScheduling } from "./scheduler.js";
import * as py from "./py_bridge.js";

const status = document.getElementById("status");
const errorBox = document.getElementById("error");
const picker = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const menuButton = document.getElementById("menu-button");
const regionElements = [1, 2, 3, 4, 5, 6].map((n) => document.getElementById(`region-${n}`));

prefetchSoundFonts();
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

initMenu({
  menuButton,
  extra: { open: { label: "Open a score", run: () => picker.click() } },
  returnFocus: (n) => (n && scoreLoaded ? focusRegion(n) : focusMenuButton()),
  disabled: () => (scoreLoaded ? py.disabledCommands() : []),
});

// --- drawing bridge results --------------------------------------------------

/** `follow`: a playback result. Regions other than 3 then change their
 * text in place, so the reader stays on the row they are reading (Region
 * 6's position line changes with every note). */
function showRegions(regions, regionThreeSelection, { loaded = false, follow = false } = {}) {
  for (const [key, rows] of Object.entries(regions)) {
    const n = Number(key);
    if (n === 3) render(n, rows, { selection: regionThreeSelection });
    else if (follow && n !== 2) render(n, rows, { inPlace: true });
    // A mute or solo redraws Region 2 and must keep the cursor on its row
    // and the open nodes; a fresh score starts collapsed.
    else if (n === 2) render(n, rows, loaded ? { reset: true, force: true } : { keepCurrent: true });
    else render(n, rows);
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
  // Sound first: the audition is the latency-critical part (Ref 9), and
  // speech and drawing do not delay it.
  play(result.sound);
  // A move while paused drops playback to Stopped (revert_pause_on_move).
  if (result.transport === "stopped") stopSession();
  if (speak && result.announce) announceUrgent(result.announce);
  // `regions` also comes back on a failed jump, to clear a typed number from Region 6.
  if (result.regions) showRegions(result.regions, result.selection);
}

function refreshRegionFour() {
  const result = py.selectionChanged(selection());
  if (result?.error) showError(result.error);
  else render(4, result.regions["4"], { keepCurrent: true });
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

function activeRegion() {
  return focusedRegion() ?? 0;
}

// Up/Down in Region 3 sound the new row (notes only: the cursor has not
// moved, so no click or spoken beat), even at an end, where the desktop
// still collapses a chord to one note and sounds it. Home/End do not sound,
// as on the desktop.
for (const [id, where] of [["list.previous", "previous"], ["list.next", "next"], ["list.top", "top"], ["list.bottom", "bottom"]]) {
  bind(id, () => {
    const n = activeRegion();
    if (n < 1) return false;
    const moved = moveRow(n, where);
    if (n !== 3 || !scoreLoaded) return true;
    if (where === "previous" || where === "next") play(py.audition(selection(), false).sound);
    if (moved || where === "previous" || where === "next") refreshRegionFour();
    return true;
  });
}

for (const [id, where] of [
  ["list.extendPrevious", "previous"], ["list.extendNext", "next"],
  ["list.extendTop", "top"], ["list.extendBottom", "bottom"],
]) {
  bind(id, () => {
    if (extendSelection(where) && scoreLoaded) refreshRegionFour();
    return true;
  });
}

bind("tree.expand", () => { treeExpand(); return true; });
bind("tree.collapse", () => { treeCollapse(); return true; });

// --- Region 2 mute and solo ----------------------------------------------------

function applyRegion2(result) {
  if (result?.error) {
    showError(result.error);
    return;
  }
  if (result.announce) announceUrgent(result.announce);
  showRegions(result.regions, result.selection);
}

function toggleRegion2(kind) {
  const node = rowAt(2, currentRow(2));
  if (node?.id) applyRegion2(py.region2Toggle(node.id, kind));
}

bind("region2.mute", withScore(() => toggleRegion2("mute")));
bind("region2.solo", withScore(() => toggleRegion2("solo")));
bind("region2.unmuteAll", withScore(() => applyRegion2(py.region2Clear("mute"))));
bind("region2.unsoloAll", withScore(() => applyRegion2(py.region2Clear("solo"))));

// --- go to bar -----------------------------------------------------------------

bind("goto.bar", withScore(async () => {
  const number = await showGotoBar(py.gotoInfo());
  if (number !== null) applyMove(py.gotoBar(number));
}));

// Typed bar number: digits build up (Region 6 shows them), Enter jumps. The
// page remembers only whether something is pending, so Enter falls through
// to a focused button when nothing is.
let digitsPending = false;

function applyDigits(result) {
  if (result?.error) showError(result.error);
  else if (result?.regions) showRegions(result.regions, result.selection);
}

bind("digits.type", withScore((event, key) => {
  digitsPending = true;
  applyDigits(py.appendDigit(key));
}));
bind("digits.commit", () => {
  if (!scoreLoaded || !digitsPending) return false;
  digitsPending = false;
  const result = py.commitDigits();
  if (result.error) showError(result.error);
  else applyMove(result);
  return result.pending !== false;
});
// Ctrl+Enter: the typed number becomes the loop length instead.
bind("digits.loopLength", () => {
  if (!scoreLoaded || !digitsPending) return false;
  digitsPending = false;
  const result = py.commitLoopLength();
  if (result.error) showError(result.error);
  else if (result.pending !== false) {
    announceUrgent(result.announce);
    showRegions(result.regions);
  }
});
bind("digits.clear", () => {
  if (!scoreLoaded || !digitsPending) return false;
  digitsPending = false;
  applyDigits(py.clearDigits());
});

bind("help.keys", () => showHelp());

// --- playback (Space, Ctrl+Space) ------------------------------------------------

initScheduler({
  cursor: (result) => showRegions(result.regions, result.selection, { follow: true }),
  ended: (result) => result?.regions && showRegions(result.regions, result.selection, { follow: true }),
  error: showError,
});

// Space on a focused button presses it, as everywhere else on the web.
const onButton = () => ["BUTTON", "INPUT"].includes(document.activeElement?.tagName);

/** A play_toggle or play_metronome result. */
function applyTransport(result) {
  if (result?.error) return showError(result.error);
  if (result.action === "boundary") play(result.sound);
  else if (result.action === "stop") {
    stopSession();
    showRegions(result.regions, result.selection, { follow: true });
  } else if (result.action === "start" || result.action === "resume") {
    showRegions(result.regions, null, { follow: true });
    startSession(result.session);
  }
}

bind("play.toggle", () => {
  if (!scoreLoaded || onButton()) return false;
  applyTransport(py.playToggle());
});

bind("play.metronome", withScore(() => applyTransport(py.playMetronome())));

// Shift+Space (Ref 13): sound the selected notes again, with the position
// cues, as the desktop's chord audition does.
bind("notes.audition", () => {
  if (!scoreLoaded || onButton()) return false;
  play(py.audition(selection(), true).sound);
});

// F, S, D, Ctrl+L, Ctrl+I, Ctrl+R, Alt+PageUp/PageDown: a setting changes,
// its new value is spoken and Region 6 redrawn.
function applySetting(result) {
  if (result?.error) return showError(result.error);
  if (result.announce) announceUrgent(result.announce);
  if (result.regions) showRegions(result.regions);
}

for (const [id, kind] of [["tempo.faster", "faster"], ["tempo.slower", "slower"], ["tempo.reset", "reset"]]) {
  bind(id, withScore(() => applySetting(py.tempo(kind))));
}
for (const [id, command] of [
  ["play.mode", "play_mode"], ["play.leadIn", "lead_in"], ["play.loopRepeat", "loop_repeat"],
  ["play.loopLonger", "loop_longer"], ["play.loopShorter", "loop_shorter"],
]) {
  bind(id, withScore(() => applySetting(py.playSetting(command))));
}

bind("play.settings", withScore(async () => {
  const form = py.playSettingsForm();
  if (form?.error) return showError(form.error);
  const values = await showPlaySettings(form, py.playSettingsEnabled);
  if (values) applySetting(py.applyPlaySettings(values));
}));

bind("play.pause", withScore(() => {
  const result = pauseSession();
  if (result?.error) showError(result.error);
  else if (result?.paused) showRegions(result.regions, result.selection, { follow: true });
}));

bind("notes.selectAll", withScore(() => {
  selectAll();
  play(py.audition(selection(), true).sound);
  refreshRegionFour();
}));

// Ctrl+M, Ctrl+P, Ctrl+B. Only Region 6 is redrawn, so the spoken state is
// not talked over by the note list.
for (const [id, kind] of [
  ["options.metronome", "metronome"],
  ["options.positionAnnouncer", "position_announcer"],
  ["options.barLineIndicator", "bar_line_indicator"],
]) {
  bind(id, withScore(() => {
    const result = py.toggle(kind);
    if (result?.error) return showError(result.error);
    announceUrgent(result.announce);
    showRegions(result.regions);
  }));
}

bind("attributes.speak", withScore((event, key) => {
  const text = py.attributeAnnouncement(Number(key.slice(-1)), selection());
  if (text) announceUrgent(text);
}));

// --- Region 4 scope menu (Shift+F10, Ref 15 AC4) ---------------------------------
// Add or remove the current row's attribute in the note list, at voice,
// stave, part or score scope. The bridge words and filters the choices
// (models/attribute_scopes.py, as the desktop's context menu); nothing is
// spoken, focus goes back to the Region 4 row, which reads it.

function openScopeMenu() {
  const row = currentRow(4);
  const chosen = selection();
  const menu = py.region4Menu(row, chosen);
  if (menu?.error) return showError(menu.error);
  if (!menu.items.length) return; // nothing to act on: no menu, as on the desktop
  showContextMenu({
    anchor: regionElements[3],
    label: menu.title,
    entries: menu.items.map((item) => ({ label: item.label, run: () => applyScope(row, chosen, item.scope) })),
    back: () => focusRegion(4),
  });
}

function applyScope(row, chosen, scope) {
  const result = py.region4Apply(row, chosen, scope);
  if (result?.error) {
    showError(result.error);
    return;
  }
  // Region 3's text changes under its own selection (refresh_region_3_labels).
  render(3, result.regions["3"], { selection: chosen, keepCurrent: true });
  render(4, result.regions["4"], { keepCurrent: true });
  focusRegion(4);
}

bind("attributes.scopeMenu", withScore(() => openScopeMenu()));

// The ContextMenu key reaches the page only as this event in some browsers,
// and a right click lands here too. One that follows Shift+F10 arrives at
// the menu the key already opened, so it is only swallowed there.
document.addEventListener("contextmenu", (event) => {
  if (event.target?.closest?.("[role='menu']")) event.preventDefault();
  else if (scoreLoaded && regionElements[3].contains(event.target)) {
    event.preventDefault();
    openScopeMenu();
  }
});

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
  if (isScheduling()) stopSession(); // the bridge stopped it with the old score
  scoreLoaded = true;
  digitsPending = false;
  showRegions(result.view.regions, result.view.selection, { loaded: true });
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
    initAudio({ synthSetup: py.synthSetup(), status: (text) => (text.startsWith("Sound could not") ? showError(text) : announce(text)) });
    say("Ready. Choose a score file. Sound starts at your first key press.");
  })
  .catch((err) => showError(`Could not start: ${err.message}`));

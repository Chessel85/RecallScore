import "./debug.js";
import { announce, announceUrgent } from "./announcer.js";
import { bind } from "./keymap.js";
import { initFocus, focusRegion, focusedRegion, focusMenuButton } from "./focus.js";
import {
  initRegions, render, moveRow, extendSelection, selection, selectAll, rowAt, currentRow, treeExpand, treeCollapse,
} from "./regions.js";
import { showHelp, showGotoBar, showFind, showPlaySettings, showMixer } from "./dialogs.js";
import { initMenu, showContextMenu, openMenu } from "./menu.js";
import { initAudio, prefetchSoundFonts, play, setMixerLevels, mixerChange } from "./audio.js";
import { initScheduler, startSession, stopSession, pauseSession, isScheduling } from "./scheduler.js";
import * as storage from "./storage.js";
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
  extra: {
    open: { label: "Open a score", run: () => picker.click() },
    // Published beside the app by tools/stage_web.py (docs/*.html).
    userGuide: { label: "User guide", run: () => window.open("../user_guide_web.html", "_blank") },
    ukTerms: { label: "UK terminology", radio: true, run: () => setTerminology(true) },
    usTerms: { label: "US terminology", radio: true, run: () => setTerminology(false) },
    indicatorOff: { label: "Performance indicator off", radio: true, run: () => setIndicator("off") },
    indicatorExceptPlaying: {
      label: "Performance indicator on except when playing", radio: true, run: () => setIndicator("on_except_when_playing"),
    },
    indicatorAlways: { label: "Performance indicator always on", radio: true, run: () => setIndicator("always_on") },
  },
  returnFocus: (n) => (n && scoreLoaded ? focusRegion(n) : focusMenuButton()),
  disabled: () => (scoreLoaded ? py.disabledCommands() : []),
  checked: () => optionsChecked(),
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

// --- find ------------------------------------------------------------------------

// Ctrl+F (or Ctrl+Shift+F, which Firefox passes on): OK arms the chosen
// target and jumps to its next occurrence; focus then goes to Region 3, as
// on the desktop. Alt+Right/Left step through the rest from any region.
bind("find.open", withScore(async () => {
  const form = py.findForm();
  if (form?.error) return showError(form.error);
  const row = await showFind(form);
  focusRegion(3);
  if (row !== null) applyMove(py.findChoose(row));
}));
bind("find.next", withScore(() => applyMove(py.findStep(1))));
bind("find.previous", withScore(() => applyMove(py.findStep(-1))));

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

// M opens the Menu from anywhere in the cycle; closing it without a choice
// goes back to the region M was pressed in.
bind("menu.open", () => {
  const n = focusedRegion();
  openMenu(() => (n ? focusRegion(n) : focusMenuButton()));
});

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

// Mixer (Ctrl+Shift+X): volume and pan per part and app sound, heard as
// they change. Python keeps the edit; OK keeps it with the score, Cancel
// puts every channel back. Preview playback stops when the dialog closes.
// Focus goes back to the region it came from: Preview redraws the regions,
// so the row that had focus may no longer exist for the browser to return to.
bind("play.mixer", withScore(async () => {
  const form = py.mixerForm();
  if (form?.error) return showError(form.error);
  const back = focusedRegion();
  const accepted = await showMixer(form, {
    change: (key, field, percent) => {
      const result = py.mixerSet(key, field, percent);
      if (result?.error) showError(result.error);
      else mixerChange(result.change);
    },
    preview: () => applyTransport(py.playToggle()),
  });
  const result = py.mixerEnd(accepted);
  if (result?.error) return showError(result.error);
  setMixerLevels(result.levels);
  if (result.stopped?.stopped) {
    stopSession();
    showRegions(result.stopped.regions, result.stopped.selection, { follow: true });
  }
  if (back) focusRegion(back);
  else focusMenuButton();
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

// --- performance indicator and marking categories ----------------------------------
// Ctrl+C cycles the performance indicator (whether the cue sounds on a
// marking row; the bridge puts it in each move's sound plan). Alt+N, or the
// one-item menu on Shift+F10, adds or removes the Region 5 row's marking
// category in the note list (Ctrl+N on the desktop, which browsers keep).

bind("options.performanceIndicator", () => {
  const result = py.cyclePerformanceIndicator();
  if (result?.error) return showError(result.error);
  announceUrgent(result.announce);
  saveGlobalSettings();
});

/** Ctrl+N's toggle for Region 5's row `row`. Region 5 keeps its rows and
 * only their "* " prefix changes, so it changes in place and the reader
 * stays on the row; the spoken state says what happened. Returns false for
 * a row with no category (the key then does nothing). */
function toggleCategory(row) {
  const result = py.toggleMarkingCategory(row);
  if (result?.error) {
    showError(result.error);
    return true;
  }
  if (!result.done) return false;
  saveGlobalSettings(); // the desktop writes the choice through to its settings.json
  const { "5": regionFive, ...others } = result.regions;
  showRegions(others, result.selection);
  render(5, regionFive, { inPlace: true, keepCurrent: true });
  announceUrgent(result.announce);
  return true;
}

function openCategoryMenu() {
  const row = currentRow(5);
  const menu = py.region5Menu(row);
  if (menu?.error) return showError(menu.error);
  if (!menu.items.length) return; // a row with no category: no menu, as on the desktop
  showContextMenu({
    anchor: regionElements[4],
    label: menu.title,
    entries: menu.items.map((item) => ({
      label: item.label,
      // Changed first, so going back to the row reads its new text.
      run: () => {
        toggleCategory(row);
        focusRegion(5);
      },
    })),
    back: () => focusRegion(5),
  });
}

bind("performance.toggleCategory", withScore(() => toggleCategory(currentRow(5))));
bind("performance.categoryMenu", withScore(() => openCategoryMenu()));

// The ContextMenu key reaches the page only as this event in some browsers,
// and a right click lands here too. One that follows Shift+F10 arrives at
// the menu the key already opened, so it is only swallowed there.
document.addEventListener("contextmenu", (event) => {
  if (event.target?.closest?.("[role='menu']")) event.preventDefault();
  else if (scoreLoaded && regionElements[3].contains(event.target)) {
    event.preventDefault();
    openScopeMenu();
  } else if (scoreLoaded && regionElements[4].contains(event.target)) {
    event.preventDefault();
    openCategoryMenu();
  }
});

// --- Options menu: terminology, performance indicator choices, Ctrl+V ----------------
// Global settings, so they work with no score and are saved as they change.
// A choice made on the Menu is spoken: the menu closes onto a region, so
// the item's checked state is not heard there.

/** The Options menu's checked states (web_api.options_state), keyed by
 * MENUS entry. The score's own toggles appear only with a score loaded. */
function optionsChecked() {
  const state = ready ? py.optionsState() : null;
  if (!state || state.error) return {};
  const checked = {
    "extra:ukTerms": state.uk_terms,
    "extra:usTerms": !state.uk_terms,
    "extra:indicatorOff": state.performance_indicator === "off",
    "extra:indicatorExceptPlaying": state.performance_indicator === "on_except_when_playing",
    "extra:indicatorAlways": state.performance_indicator === "always_on",
    "options.engravingDetails": state.show_engraving_details,
  };
  if ("metronome" in state) {
    checked["options.metronome"] = state.metronome;
    checked["options.positionAnnouncer"] = state.position_announcer;
    checked["options.barLineIndicator"] = state.bar_line_indicator;
  }
  return checked;
}

function setTerminology(ukTerms) {
  const chosen = scoreLoaded ? selection() : null;
  const result = py.setUkTerms(ukTerms, chosen);
  if (result?.error) return showError(result.error);
  saveGlobalSettings();
  announceUrgent(result.announce);
  // The words change, not the rows: every region keeps its place, and
  // Region 3 keeps its selection (the desktop's refresh_region_3_labels).
  for (const [key, rows] of Object.entries(result.regions ?? {})) {
    const n = Number(key);
    render(n, rows, n === 3 ? { selection: chosen, keepCurrent: true } : { keepCurrent: true });
  }
}

function setIndicator(mode) {
  const result = py.setPerformanceIndicator(mode);
  if (result?.error) return showError(result.error);
  saveGlobalSettings();
  announceUrgent(result.announce);
}

bind("options.engravingDetails", () => {
  if (!ready) return false;
  const result = py.toggleEngravingDetails();
  if (result?.error) return showError(result.error);
  saveGlobalSettings();
  announceUrgent(result.announce);
  if (result.regions) showRegions(result.regions, result.selection);
});

// --- stored settings (storage.js) -----------------------------------------------
// Global settings are written as they change, as the desktop writes its
// settings.json. A score's settings are written when another score is
// opened and when the page is hidden or closed: the desktop's two points
// (swapping files and shutting down), not every toggle.

/** The open score: {key (SHA-256, or null), name}, or null. */
let current = null;

storage.initStorage({ failure: (text) => announce(text) });

function saveGlobalSettings() {
  const text = py.globalSettingsJson();
  if (typeof text === "string") storage.saveGlobal(text);
}

function saveScoreSettings() {
  if (!current?.key) return;
  const text = py.scoreSettingsJson();
  if (typeof text === "string") storage.saveScore(current.key, current.name, text);
}

function saveEverything() {
  if (!ready) return;
  saveScoreSettings();
  saveGlobalSettings();
}

// pagehide covers closing and leaving; visibilitychange covers a mobile
// browser, or a tab the browser discards later without either.
window.addEventListener("pagehide", saveEverything);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") saveEverything();
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
  const key = await storage.scoreKey(bytes);
  await new Promise((resolve) => setTimeout(resolve, 0)); // let the message paint
  saveScoreSettings(); // the score being replaced, as the desktop saves on a swap
  const result = py.loadScore(bytes, file.name, storage.loadScore(key));
  if (result.error) {
    showError(result.error);
    return;
  }
  current = { key, name: file.name };
  if (isScheduling()) stopSession(); // the bridge stopped it with the old score
  setMixerLevels(result.mixer);
  scoreLoaded = true;
  digitsPending = false;
  showRegions(result.view.regions, result.view.selection, { loaded: true });
  const loaded = `Loaded ${file.name}. ${result.summary.parts.length} parts, ${result.summary.slices} notes and chords.`;
  say(result.settings_error ? `${loaded} ${result.settings_error}` : loaded);
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

/** The browser's region ("GB", "US"), or "" when its language names none:
 * the default terminology's only input (UK unless "US", as on the desktop).
 * Not maximized, so a bare "en" stays unknown rather than becoming US. */
function browserTerritory() {
  try {
    return new Intl.Locale(navigator.language).region ?? "";
  } catch {
    return "";
  }
}

picker.disabled = true;
say("Starting Recall Score.");
py.boot(say)
  .then(() => {
    const applied = py.applyGlobalSettings(storage.loadGlobal(), browserTerritory());
    if (applied?.error) showError(applied.error);
    ready = true;
    picker.disabled = false;
    initAudio({ synthSetup: py.synthSetup(), status: (text) => (text.startsWith("Sound could not") ? showError(text) : announce(text)) });
    say("Ready. Choose a score file. Sound starts at your first key press.");
  })
  .catch((err) => showError(`Could not start: ${err.message}`));

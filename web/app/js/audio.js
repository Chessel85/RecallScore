// The page's synth: js-synthesizer (FluidSynth in WebAssembly) in an
// AudioWorklet, promoted from Phase 0 spike 4. It plays the bridge's sound
// plans (web_api.py, "sound") and decides nothing itself: which notes,
// which cues, programs (already 0-indexed, invariant 9) and pans all come
// from Python. What lives here is SynthEngine's mechanics: retrigger, one
// note-off timer per group, the grace pre-note, and one-shot slots.
//
// Browsers only let sound start after the user does something, so the
// synth starts on the first key press or click anywhere on the page. That
// listener is an unlock hook, not a command: keymap.js still owns every
// command key. The SoundFonts are downloaded at boot so starting is quick;
// a plan that arrives before the synth is ready is dropped, never played
// late.

const LIB = "https://cdn.jsdelivr.net/npm/js-synthesizer@1.13.0";
const LIBFLUIDSYNTH = `${LIB}/externals/libfluidsynth-2.4.6.js`;
const MAIN = `${LIB}/dist/js-synthesizer.min.js`; // defines the JSSynth global
const WORKLET = `${LIB}/dist/js-synthesizer.worklet.min.js`;
const APP_SOUNDS = "recall_score_sounds.sf2";
// SynthEngine's settings: 256 channels (the app sounds sit on 249 to 255)
// and its master gain.
const SETTINGS = { midiChannelCount: 256, initialGain: 0.7 };
const NOTE_VELOCITY = 90; // SynthEngine.play_chord
const PAN_CC = 10;

let state = "idle"; // idle, starting, ready, failed
let ctx = null;
let synth = null;
let gmSfont = null;
let appSfont = null;
let fontBytes = null; // Promise of {gm, app} ArrayBuffers
let library = null; // Promise: the main-thread js-synthesizer script
let setup = null;
let onStatus = () => {};

// SynthEngine's bookkeeping. `active` may hold a (channel, key) pair more
// than once (two voices in unison on one part's channel), so a group's
// note-off only releases a key no other live group still holds.
let active = [];
let timers = new Set();
const slots = new Map(); // slot name -> [channel, key]

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`could not load ${src}`));
    document.head.append(script);
  });
}

async function fetchBytes(name) {
  const response = await fetch(`../sf/${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error(`sf/${name}: HTTP ${response.status}`);
  return response.arrayBuffer();
}

/** Start downloading the synth library and the SoundFonts, while Python
 * boots. */
export function prefetchSoundFonts() {
  if (fontBytes) return;
  library = loadScript(MAIN);
  library.catch(() => {}); // reported when the synth starts
  fontBytes = (async () => {
    const names = await (await fetch("../sf/index.json")).json();
    const gmName = names.find((n) => n !== APP_SOUNDS && n.endsWith(".sf2"));
    if (!gmName) throw new Error("no instrument SoundFont is staged");
    const [gm, app] = await Promise.all([fetchBytes(gmName), fetchBytes(APP_SOUNDS)]);
    return { gm, app };
  })();
  fontBytes.catch(() => {}); // reported when the synth starts
}

// Keys the browser does not count as a gesture that allows sound. Starting
// on one of these made a context that never ran (a first Shift+Tab or
// Ctrl+key left the page silent for good).
const NOT_A_GESTURE = new Set([
  "Shift", "Control", "Alt", "AltGraph", "Meta", "OS", "Fn", "CapsLock", "NumLock", "ScrollLock", "Escape",
]);

/** Arm the gesture start. `synthSetup` is web_api.synth_setup();
 * `status(text)` reports "Sound ready." or a failure in words. The
 * listeners stay for the page's life: every gesture also resumes a context
 * the browser has suspended. A screen reader's activation can arrive as a
 * bare click, hence click too. */
export function initAudio({ synthSetup, status }) {
  setup = synthSetup;
  onStatus = status ?? onStatus;
  prefetchSoundFonts();
  const gesture = (event) => {
    if (event.type === "keydown" && NOT_A_GESTURE.has(event.key)) return;
    if (state === "idle") startSynth();
    else if (ctx && ctx.state === "suspended") ctx.resume();
  };
  for (const type of ["keydown", "pointerdown", "click"]) document.addEventListener(type, gesture, true);
}

async function startSynth() {
  if (state !== "idle") return;
  state = "starting";
  try {
    ctx = new AudioContext({ latencyHint: "interactive" });
    ctx.resume(); // inside the gesture, or the browser refuses
    await ctx.audioWorklet.addModule(LIBFLUIDSYNTH);
    await ctx.audioWorklet.addModule(WORKLET);
    await library;
    try {
      synth = new JSSynth.AudioWorkletNodeSynthesizer();
    } catch {
      // Spike 4: some builds need libfluidsynth on the main thread too.
      await loadScript(LIBFLUIDSYNTH);
      await JSSynth.waitForReady();
      synth = new JSSynth.AudioWorkletNodeSynthesizer();
    }
    synth.init(ctx.sampleRate, SETTINGS);
    // The worklet synth ignores init()'s settings: they must go to
    // createAudioNode, or it has 16 channels and every app sound (251 to
    // 255) is dropped.
    synth.createAudioNode(ctx, SETTINGS).connect(ctx.destination);
    const { gm, app } = await fontBytes;
    gmSfont = await synth.loadSFont(gm);
    appSfont = await synth.loadSFont(app);
    for (const [channel, value] of setup?.pans ?? []) synth.midiControl(channel, PAN_CC, value);
    state = "ready";
    // Never wait on resume(): it stays pending, with no error, for as long
    // as the browser withholds permission. Say ready once it is running.
    if (ctx.state === "running") onStatus("Sound ready.");
    else {
      const ran = () => {
        if (ctx.state !== "running") return;
        ctx.removeEventListener("statechange", ran);
        onStatus("Sound ready.");
      };
      ctx.addEventListener("statechange", ran);
    }
  } catch (err) {
    state = "failed";
    onStatus(`Sound could not start: ${err.message}`);
  }
}

// A suspended context would queue the notes and play them all at once on
// resume, so a plan is only played while it runs.
export const audioReady = () => state === "ready" && ctx.state === "running";

/** What scheduler.js needs to put sounds on the synth's own sequencer, or
 * null before the synth is ready. */
export const synthParts = () => (state === "ready" ? { ctx, synth, gmSfont, appSfont } : null);

/** Resolves true once sound can play, false if it failed or did not start
 * within `timeoutMs`. Playback waits on this: the key press that starts it
 * may be the one that starts the synth, and keymap.js sees it first. */
export function whenSoundReady(timeoutMs = 10000) {
  const started = performance.now();
  return new Promise((resolve) => {
    const check = () => {
      if (audioReady()) return resolve(true);
      if (state === "failed" || performance.now() - started > timeoutMs) return resolve(false);
      setTimeout(check, 50);
    };
    check();
  });
}

function later(ms, fn) {
  const id = setTimeout(() => {
    timers.delete(id);
    fn();
  }, ms);
  timers.add(id);
}

/** Release everything sounding and cancel every pending note-on/off
 * (SynthEngine.stop_all_notes). One-shot slots are released too. */
export function stopAll() {
  if (state !== "ready") return;
  for (const id of timers) clearTimeout(id);
  timers.clear();
  for (const [channel, key] of active) synth.midiNoteOff(channel, key);
  active = [];
  for (const [channel, key] of slots.values()) synth.midiNoteOff(channel, key);
  slots.clear();
}

function playGroups(groups, { gmBank = true } = {}) {
  for (const group of groups) {
    if (!group.pitches.length) continue;
    const { channel } = group;
    if (group.program !== null && group.program !== undefined) {
      synth.midiProgramSelect(channel, gmSfont, gmBank ? group.bank ?? 0 : 0, group.program);
    }
    const held = group.pitches.map((key) => [channel, key]);
    for (const [, key] of held) synth.midiNoteOn(channel, key, NOTE_VELOCITY);
    active.push(...held);
    if (group.ms > 0) later(group.ms, () => releaseGroup(held));
  }
}

function releaseGroup(held) {
  for (const [channel, key] of held) {
    const i = active.findIndex(([c, k]) => c === channel && k === key);
    if (i === -1) continue;
    active.splice(i, 1);
    if (!active.some(([c, k]) => c === channel && k === key)) synth.midiNoteOff(channel, key);
  }
}

/** A one-shot on the app SoundFont. Never released on a timer: the sample
 * ends by itself. A new one-shot in the same slot cuts the previous one
 * (SynthEngine.play_click and friends). */
function playOneShot(slot, [channel, bank, program, key, velocity]) {
  const previous = slots.get(slot);
  if (previous) synth.midiNoteOff(previous[0], previous[1]);
  synth.midiProgramSelect(channel, appSfont, bank, program);
  synth.midiNoteOn(channel, key, velocity);
  slots.set(slot, [channel, key]);
}

/** Play a web_api sound plan. Silently does nothing until the synth is
 * ready, or for a null plan. */
export function play(sound) {
  if (!sound || !audioReady()) return;
  if (sound.stop) stopAll();
  if (sound.grace?.length) {
    // play_chord_with_grace: the grace notes ring briefly, then the main
    // notes start; neither re-stops what the other started.
    playGroups(sound.grace.map((g) => ({ ...g, bank: 0, ms: sound.grace_ms })), { gmBank: false });
    later(sound.grace_ms, () => playGroups(sound.notes));
  } else {
    playGroups(sound.notes);
  }
  for (const shot of sound.oneshots) {
    // A later bar line step is a plain timer, as PlaybackController's
    // QTimer.singleShot: not cancelled by the next move.
    if (shot.delay_ms > 0) setTimeout(() => audioReady() && playOneShot(shot.slot, shot.event), shot.delay_ms);
    else playOneShot(shot.slot, shot.event);
  }
}

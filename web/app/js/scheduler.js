// Playback: the lookahead scheduler (RSBV 4.2). Python plans the whole run
// (web_api.play_*, models/play_plan.py's PlayTimeline: count-in, steps,
// loop restarts, with the desktop's timing); this module asks for it a
// chunk at a time and puts each entry's sound on FluidSynth's own sequencer
// inside the AudioWorklet, timed in its ticks (1 ms each). The notes are
// then clocked by the audio itself, so a busy page or a hidden tab cannot
// make them late; only the refills and the cursor run on page timers.
//
// Like audio.js it decides nothing: what sounds, when, and where the cursor
// goes all come from the bridge. What lives here is SynthEngine's note
// bookkeeping, done ahead of time: a group's note-off only releases a key
// no other planned group still holds, a stop silences what is held at that
// moment, and a one-shot slot cuts its previous sample.

import { synthParts, whenSoundReady, stopAll } from "./audio.js";
import * as py from "./py_bridge.js";

const NOTE_VELOCITY = 90; // SynthEngine.play_chord, as audio.js
// The first sound lands this long after the start, so the first events
// reach the worklet in time.
const START_MS = 30;
// How far ahead to plan. A tempo change lands at the next chunk, so this
// is kept short while the page is visible. A hidden tab's timers may run
// only once a second, so it plans further ahead then.
const AHEAD_VISIBLE_MS = 600;
const AHEAD_HIDDEN_MS = 3000;
const REFILL_MS = 150;

let seq = null;
let seqPromise = null;
let handlers = { cursor: () => {}, ended: () => {}, error: () => {} };

// The running session, or null. `paused` is kept by Python; the page only
// needs to know whether anything is scheduled.
let session = null;
let tick0 = 0; // sequencer tick of timeline time 0
let perf0 = 0; // performance.now() of timeline time 0 (sequencer clock)
let uiDelay = 0; // output latency: the cursor moves when the note is heard
let planned = 0; // timeline ms planned up to
let refill = null;
let lastHeard = null; // the last entry whose moment has come
const uiTimers = new Set();

// Note bookkeeping, in timeline ms: every planned group's interval per
// "channel:key", and the note-offs not yet sent.
let held = new Map();
let pendingOffs = [];
let slots = new Map(); // one-shot slot -> {channel, key}

/** `cursor(result)` redraws the regions a play_cursor/play_pause result
 * carries; `ended(result)` does the same when the run ends or stops;
 * `error(text)` reports a failure. */
export function initScheduler(callbacks) {
  handlers = { ...handlers, ...callbacks };
}

export const isScheduling = () => session !== null;

async function sequencer() {
  if (seq) return seq;
  if (!seqPromise) {
    seqPromise = (async () => {
      const { synth } = synthParts();
      const created = await synth.createSequencer();
      await created.registerSynthesizer(synth);
      seq = created;
      return seq;
    })();
    seqPromise.catch(() => { seqPromise = null; });
  }
  return seqPromise;
}

/** Begin scheduling a session web_api.play_toggle just started or resumed.
 * Waits for the synth if the key press that started playback is also what
 * starts the sound. */
export async function startSession(id) {
  teardown();
  session = id;
  try {
    if (!(await whenSoundReady())) throw new Error("sound is not ready");
    await sequencer();
  } catch (err) {
    if (session === id) {
      session = null;
      handlers.ended(py.playStop());
      handlers.error(`Playback could not start: ${err.message}`);
    }
    return;
  }
  if (session !== id) return; // stopped while waiting
  const { ctx } = synthParts();
  const tick = await seq.getTick();
  if (session !== id) return;
  tick0 = tick + START_MS;
  perf0 = performance.now() + START_MS;
  uiDelay = Math.round(((ctx.baseLatency || 0) + (ctx.outputLatency || 0)) * 1000);
  planned = 0;
  fill();
  refill = setInterval(fill, REFILL_MS);
}

function fill() {
  if (session === null) return;
  const ahead = document.hidden ? AHEAD_HIDDEN_MS : AHEAD_VISIBLE_MS;
  const until = Math.max(planned, Math.round(performance.now() - perf0 + ahead));
  if (until <= planned && planned > 0) return;
  const result = py.playPlan(session, until);
  if (result?.error) {
    handlers.error(result.error);
    stopSession();
    return;
  }
  if (result.stale) return;
  for (const entry of result.entries) {
    if (entry.sound) scheduleSound(entry.sound, entry.at);
    scheduleMoment(entry);
  }
  planned = until;
  commitNoteOffs(until);
}

// --- sounds on the sequencer ----------------------------------------------------

function send(event, at) {
  seq.sendEventAt(event, Math.round(tick0 + Math.max(0, at)), true);
}

const keyOf = (channel, key) => `${channel}:${key}`;

function scheduleSound(sound, at) {
  if (sound.stop) silenceAt(at);
  if (sound.grace?.length) {
    // play_chord_with_grace: the grace notes ring briefly, then the notes.
    playGroups(sound.grace.map((g) => ({ ...g, bank: 0, ms: sound.grace_ms })), at, false);
    playGroups(sound.notes, at + sound.grace_ms, true);
  } else {
    playGroups(sound.notes, at, true);
  }
  for (const shot of sound.oneshots) oneShot(shot.slot, shot.event, at + (shot.delay_ms || 0));
}

function playGroups(groups, at, gmBank) {
  const { gmSfont } = synthParts();
  for (const group of groups) {
    if (!group.pitches.length) continue;
    const { channel } = group;
    if (group.program !== null && group.program !== undefined) {
      send({ type: "programselect", channel, sfontId: gmSfont, bank: gmBank ? group.bank ?? 0 : 0, preset: group.program }, at);
    }
    for (const key of group.pitches) {
      send({ type: "noteon", channel, key, vel: NOTE_VELOCITY }, at);
      const span = { start: at, end: group.ms > 0 ? at + group.ms : Infinity, cut: false };
      const k = keyOf(channel, key);
      if (!held.has(k)) held.set(k, []);
      held.get(k).push(span);
      if (group.ms > 0) pendingOffs.push({ at: span.end, channel, key, span });
    }
  }
}

// A note-off goes 1 ms before its moment, so a note-on at that same moment
// (the next note on the same key) is not cut by it.
const offAt = (at, span) => Math.max(span.start, at - 1);

/** Send the note-offs due by `until`, once everything starting before then
 * is planned: a key another group still holds keeps sounding, as
 * SynthEngine's group note-off does. */
function commitNoteOffs(until) {
  pendingOffs.sort((a, b) => a.at - b.at);
  const keep = [];
  for (const off of pendingOffs) {
    if (off.at > until) {
      keep.push(off);
      continue;
    }
    const k = keyOf(off.channel, off.key);
    const spans = held.get(k) ?? [];
    held.set(k, spans.filter((s) => s !== off.span));
    if (off.span.cut) continue;
    const stillHeld = spans.some((s) => s !== off.span && !s.cut && s.start < off.at && s.end > off.at);
    if (!stillHeld) send({ type: "noteoff", channel: off.channel, key: off.key }, offAt(off.at, off.span));
  }
  pendingOffs = keep;
  for (const [k, spans] of held) if (!spans.length) held.delete(k);
}

/** SynthEngine.stop_all_notes at `at`: everything held then, and the
 * one-shots. */
function silenceAt(at) {
  for (const [k, spans] of held) {
    const live = spans.filter((s) => !s.cut && s.start < at && s.end > at);
    if (!live.length) continue;
    const [channel, key] = k.split(":").map(Number);
    send({ type: "noteoff", channel, key }, offAt(at, live[0]));
    for (const s of live) s.cut = true;
  }
  for (const { channel, key } of slots.values()) send({ type: "noteoff", channel, key }, at - 1);
  slots.clear();
}

function oneShot(slot, [channel, bank, program, key, velocity], at) {
  const { appSfont } = synthParts();
  const previous = slots.get(slot);
  if (previous) send({ type: "noteoff", channel: previous.channel, key: previous.key }, at - 1);
  send({ type: "programselect", channel, sfontId: appSfont, bank, preset: program }, at);
  send({ type: "noteon", channel, key, vel: velocity }, at);
  slots.set(slot, { channel, key });
}

// --- the cursor -----------------------------------------------------------------

function scheduleMoment(entry) {
  const id = setTimeout(() => {
    uiTimers.delete(id);
    if (session === null) return;
    lastHeard = entry;
    if (entry.kind === "end") {
      const result = py.playEnded(session);
      teardown();
      if (!result.stale) handlers.ended(result);
    } else if (entry.cursor !== null && entry.cursor !== undefined) {
      const result = py.playCursor(session, entry.cursor);
      if (!result.stale) handlers.cursor(result);
    }
  }, Math.max(0, perf0 + entry.at + uiDelay - performance.now()));
  uiTimers.add(id);
}

// --- stopping -------------------------------------------------------------------

/** Cancel everything scheduled and silence what is sounding now. */
function teardown() {
  session = null;
  lastHeard = null;
  if (refill !== null) clearInterval(refill);
  refill = null;
  for (const id of uiTimers) clearTimeout(id);
  uiTimers.clear();
  const parts = synthParts();
  if (seq) seq.removeAllEvents();
  // Every channel, not just `held`: a note whose note-off was already
  // queued has left `held`, and removeAllEvents just dropped that note-off.
  if (parts) parts.synth.midiAllNotesOff();
  held = new Map();
  pendingOffs = [];
  slots = new Map();
  stopAll();
}

/** Stop scheduling: Python has already stopped (a Space stop, a load, a
 * move while paused). */
export function stopSession() {
  teardown();
}

/** Ctrl+Space: pause on the step last heard. Returns web_api.play_pause's
 * result, or null when nothing is playing. */
export function pauseSession() {
  if (session === null || !lastHeard) return null;
  const result = py.playPause(session, lastHeard.seq);
  if (result.paused) teardown();
  return result;
}

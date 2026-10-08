import { status, log, report, renderReport, wireCopyButton, median, ms } from "./common.js";

const LIB = "https://cdn.jsdelivr.net/npm/js-synthesizer@1.13.0";
const LIBFLUIDSYNTH = `${LIB}/externals/libfluidsynth-2.4.6.js`;
const WORKLET = `${LIB}/dist/js-synthesizer.worklet.min.js`;
const APP_SOUNDS = "recall_score_sounds.sf2";

// Channel layout for this spike only. The desktop app reserves high
// channel numbers for its own sounds; one app-sounds channel is enough here.
const NOTE_CHANNEL = 0;
const DRUM_CHANNEL = 9;
const APP_SOUND_CHANNEL = 14;
const METRONOME_PROGRAM = 1; // [preset:click_default], audio/metronome.py
const BARLINE_PROGRAM = 7; // [preset:barline_patterns], audio/barline_patterns.py

let ctx;
let synth;
let gmSfont = null;
let appSfont = null;
const handlerTimes = [];

const SCALE = [
  ["C", 60], ["D", 62], ["E", 64], ["F", 65], ["G", 67], ["A", 69], ["B", 71], ["C", 72],
];

function extraLines() {
  if (!ctx) return [];
  const base = (ctx.baseLatency || 0) * 1000;
  const output = (ctx.outputLatency || 0) * 1000;
  const quantum = (128 / ctx.sampleRate) * 1000;
  const lines = [
    `AudioContext: ${ctx.sampleRate} Hz, baseLatency ${base.toFixed(1)} ms, outputLatency ${ctx.outputLatency === undefined ? "not reported" : `${output.toFixed(1)} ms`}, render quantum ${quantum.toFixed(1)} ms`,
  ];
  if (handlerTimes.length) {
    const handler = median(handlerTimes);
    lines.push(`Audition: ${handlerTimes.length} key presses, key event to note-on sent median ${handler.toFixed(1)} ms. Estimated key-to-sound: ${(handler + quantum + base + output).toFixed(1)} ms (handler + one render quantum + base + output latency; excludes the audio driver and speakers).`);
  }
  lines.push("By ear (fill in): audition feels instant? / SoundFont quality / background playback even?");
  return lines;
}

function refreshReport() {
  renderReport(extraLines());
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`could not load ${src}`));
    document.head.appendChild(script);
  });
}

async function populateSoundFonts() {
  const select = document.getElementById("sf-choice");
  let names = [];
  try {
    names = (await (await fetch("../sf/index.json")).json()).filter((n) => n !== APP_SOUNDS);
  } catch {
    // No staged SoundFonts; the file picker still works.
  }
  for (const name of names) select.add(new Option(name, name));
  if (!names.length) select.add(new Option("none staged, use the file picker", ""));
}

async function gmSoundFontBytes() {
  const file = document.getElementById("sf-file").files[0];
  if (file) return { name: file.name, bytes: await file.arrayBuffer() };
  const name = document.getElementById("sf-choice").value;
  if (!name) return null;
  const response = await fetch(`../sf/${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error(`sf/${name}: HTTP ${response.status}`);
  return { name, bytes: await response.arrayBuffer() };
}

function selectProgram(channel, program) {
  // program is 1-indexed, as in the model (invariant 9); the wire is 0-indexed.
  synth.midiProgramSelect(channel, gmSfont, 0, program - 1);
}

async function start() {
  const button = document.getElementById("start");
  button.disabled = true;
  try {
    const t0 = performance.now();
    ctx = new AudioContext({ latencyHint: document.getElementById("latency-hint").value });
    await ctx.resume();
    status("Loading the synthesizer.");
    await ctx.audioWorklet.addModule(LIBFLUIDSYNTH);
    await ctx.audioWorklet.addModule(WORKLET);
    try {
      synth = new JSSynth.AudioWorkletNodeSynthesizer();
    } catch (err) {
      log(`AudioWorkletNodeSynthesizer needed libfluidsynth on the main thread too (${err.message}); loading it.`);
      await loadScript(LIBFLUIDSYNTH);
      await JSSynth.waitForReady();
      synth = new JSSynth.AudioWorkletNodeSynthesizer();
    }
    synth.init(ctx.sampleRate);
    const node = synth.createAudioNode(ctx);
    node.connect(ctx.destination);
    const tSynth = performance.now();
    report(`Synth ready in ${ms(tSynth - t0)} (latency setting: ${document.getElementById("latency-hint").value})`);

    const gm = await gmSoundFontBytes();
    if (!gm) throw new Error("choose an instrument SoundFont first");
    status(`Loading ${gm.name}.`);
    let t = performance.now();
    gmSfont = await synth.loadSFont(gm.bytes);
    report(`Instrument SoundFont ${gm.name}: ${(gm.bytes.byteLength / 1048576).toFixed(1)} MB, loaded into the synth in ${ms(performance.now() - t)} (download time not included)`);

    t = performance.now();
    const app = await fetch(`../sf/${APP_SOUNDS}`);
    if (app.ok) {
      appSfont = await synth.loadSFont(await app.arrayBuffer());
      report(`App sounds SoundFont loaded in ${ms(performance.now() - t)}`);
    } else {
      report("App sounds SoundFont not staged; click test unavailable");
    }

    selectProgram(NOTE_CHANNEL, Number(document.getElementById("program").value));
    synth.midiProgramSelect(DRUM_CHANNEL, gmSfont, 128, 0);
    status(`Sound ready after ${ms(performance.now() - t0)}. Focus the note list and press Down Arrow.`);
    refreshReport();
  } catch (err) {
    status(`Sound failed to start: ${err.message}`);
    report(`START FAILED: ${err.message}`);
    button.disabled = false;
  }
}

// --- audition latency -----------------------------------------------------------

const notesList = document.getElementById("notes");
SCALE.forEach(([name], i) => {
  const option = document.createElement("div");
  option.setAttribute("role", "option");
  option.id = `note-${i}`;
  option.textContent = `${name}`;
  option.setAttribute("aria-selected", i === 0 ? "true" : "false");
  notesList.appendChild(option);
});
let activeNote = 0;
let soundingKey = null;

notesList.addEventListener("keydown", (event) => {
  const delta = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
  if (!delta) return;
  event.preventDefault();
  activeNote = (activeNote + delta + SCALE.length) % SCALE.length;
  if (synth) {
    if (soundingKey !== null) synth.midiNoteOff(NOTE_CHANNEL, soundingKey);
    soundingKey = SCALE[activeNote][1];
    synth.midiNoteOn(NOTE_CHANNEL, soundingKey, 100);
    handlerTimes.push(performance.now() - event.timeStamp);
  }
  // Move the cursor after sounding, as the app should: sound first, speech second.
  notesList.querySelectorAll('[role="option"]').forEach((o, i) => o.setAttribute("aria-selected", i === activeNote ? "true" : "false"));
  notesList.setAttribute("aria-activedescendant", `note-${activeNote}`);
  if (handlerTimes.length % 10 === 0) refreshReport();
});

// --- demos ------------------------------------------------------------------------

function playSequence(channel, steps, stepMs) {
  steps.forEach((keys, i) => {
    setTimeout(() => {
      for (const key of [].concat(keys)) synth.midiNoteOn(channel, key, 100);
      setTimeout(() => { for (const key of [].concat(keys)) synth.midiNoteOff(channel, key); }, stepMs * 0.9);
    }, i * stepMs);
  });
}

document.getElementById("program").addEventListener("change", (event) => {
  if (synth) selectProgram(NOTE_CHANNEL, Number(event.target.value));
});
document.getElementById("demo").addEventListener("click", () => {
  if (!synth) return status("Start sound first.");
  playSequence(NOTE_CHANNEL, [60, 64, 67, 72, 71, 67, 65, 62, [60, 64, 67]], 300);
});
document.getElementById("drums").addEventListener("click", () => {
  if (!synth) return status("Start sound first.");
  playSequence(DRUM_CHANNEL, [[36, 42], 42, [38, 42], 42, [36, 42], [36, 42], [38, 42], 46], 220);
});
document.getElementById("clicks").addEventListener("click", () => {
  if (!synth || appSfont === null) return status("App sounds are not loaded.");
  synth.midiProgramSelect(APP_SOUND_CHANNEL, appSfont, 0, METRONOME_PROGRAM);
  playSequence(APP_SOUND_CHANNEL, [62, 63, 63, 63, 62, 63, 63, 63], 500);
  setTimeout(() => {
    synth.midiProgramSelect(APP_SOUND_CHANNEL, appSfont, 0, BARLINE_PROGRAM);
    synth.midiNoteOn(APP_SOUND_CHANNEL, 60, 127);
  }, 4200);
});

// --- background playback ----------------------------------------------------------

const TEST_MS = 60000;
const STEP_MS = 250;
let stopCurrent = null;
let hiddenSince = null;
let hiddenTotal = 0;

document.addEventListener("visibilitychange", () => {
  if (document.hidden) hiddenSince = performance.now();
  else if (hiddenSince !== null) {
    hiddenTotal += performance.now() - hiddenSince;
    hiddenSince = null;
  }
});

function beginBackgroundTest(name) {
  stopCurrent?.();
  hiddenTotal = 0;
  status(`${name} running for 60 seconds. Switch away now.`);
}

function finishBackgroundTest(name, details) {
  report(`${name}: hidden for ${ms(hiddenTotal)} of the run. ${details}`);
  refreshReport();
  status(`${name} finished.`);
  stopCurrent = null;
}

document.getElementById("bg-timer").addEventListener("click", () => {
  if (!synth) return status("Start sound first.");
  const name = "Background test A (page timer)";
  beginBackgroundTest(name);
  const startAt = performance.now();
  let expected = startAt;
  let step = 0;
  let timer;
  let maxLateHidden = 0;
  let maxLateVisible = 0;
  let lateHidden = 0;
  let previousKey = null;
  const tick = () => {
    const now = performance.now();
    const late = now - expected;
    if (document.hidden) {
      maxLateHidden = Math.max(maxLateHidden, late);
      if (late > 30) lateHidden += 1;
    } else {
      maxLateVisible = Math.max(maxLateVisible, late);
    }
    if (previousKey !== null) synth.midiNoteOff(NOTE_CHANNEL, previousKey);
    previousKey = SCALE[step % SCALE.length][1];
    synth.midiNoteOn(NOTE_CHANNEL, previousKey, 90);
    step += 1;
    expected += STEP_MS;
    if (now - startAt >= TEST_MS) return stop();
    timer = setTimeout(tick, Math.max(0, expected - performance.now()));
  };
  const stop = () => {
    clearTimeout(timer);
    if (previousKey !== null) synth.midiNoteOff(NOTE_CHANNEL, previousKey);
    finishBackgroundTest(name, `${step} notes. Worst lateness: visible ${ms(maxLateVisible)}, hidden ${ms(maxLateHidden)}; ${lateHidden} notes more than 30 ms late while hidden.`);
  };
  stopCurrent = stop;
  tick();
});

document.getElementById("bg-seq").addEventListener("click", async () => {
  if (!synth) return status("Start sound first.");
  const name = "Background test B (FluidSynth sequencer)";
  beginBackgroundTest(name);
  let seq;
  try {
    seq = await synth.createSequencer();
    await seq.registerSynthesizer(synth);
  } catch (err) {
    report(`${name}: could not create the sequencer: ${err.message}`);
    refreshReport();
    return;
  }
  const LOOKAHEAD_TICKS = 3000; // default time scale is 1000 ticks per second
  const startTick = (await seq.getTick()) + 200;
  let nextTick = startTick;
  let step = 0;
  let underruns = 0;
  let lastRefill = performance.now();
  let maxRefillGapHidden = 0;
  let maxRefillGapVisible = 0;
  const refill = async () => {
    const now = performance.now();
    const gap = now - lastRefill;
    lastRefill = now;
    if (document.hidden) maxRefillGapHidden = Math.max(maxRefillGapHidden, gap);
    else maxRefillGapVisible = Math.max(maxRefillGapVisible, gap);
    const tick = await seq.getTick();
    if (tick > nextTick) underruns += 1;
    while (nextTick < tick + LOOKAHEAD_TICKS && nextTick - startTick < TEST_MS) {
      seq.sendEventAt({ type: "note", channel: NOTE_CHANNEL, key: SCALE[step % SCALE.length][1], vel: 90, duration: STEP_MS - 20 }, nextTick, true);
      nextTick += STEP_MS;
      step += 1;
    }
    if (tick - startTick >= TEST_MS) stop();
  };
  const interval = setInterval(refill, 500);
  const stop = () => {
    clearInterval(interval);
    seq.removeAllEvents();
    seq.close();
    finishBackgroundTest(name, `${step} notes scheduled. Longest gap between refills: visible ${ms(maxRefillGapVisible)}, hidden ${ms(maxRefillGapHidden)} (a gap over 3000 ms would starve the sequencer); ${underruns} underruns.`);
  };
  stopCurrent = stop;
  refill();
});

document.getElementById("bg-stop").addEventListener("click", () => stopCurrent?.());
document.getElementById("start").addEventListener("click", start);

wireCopyButton(extraLines);
populateSoundFonts().then(() => {
  document.getElementById("start").disabled = false;
  status("Ready. Press Start sound.");
});

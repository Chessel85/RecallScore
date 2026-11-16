// Live MIDI input: the browser's Web MIDI API. It lists the input devices,
// opens the one the settings name and passes its note-on and note-off
// messages to audio.js. What is stored, the instrument and the wording are
// web_api.py's (live_midi_*); the desktop's controller is
// LiveMidiInputController, and like it this plays notes and nothing else
// (sustain, pitch bend and aftertouch are ignored, audio/midi_input.py).
//
// Web MIDI is in Chrome, Edge and Firefox on Windows and macOS, not in
// Safari. The permission prompt appears the first time a page asks, so
// access is asked for only when live input is switched on or its settings
// are opened, never at page load without it.
import { liveAllNotesOff, liveNoteOff, liveNoteOn } from "./audio.js";

const NOTE_OFF = 0x80;
const NOTE_ON = 0x90;

let access = null; // MIDIAccess once granted
let asking = null; // Promise of the request, so it is made once
let input = null; // the open MIDIInput
let wanted = null; // device name to keep open, or null

export const midiSupported = () => typeof navigator !== "undefined" && typeof navigator.requestMIDIAccess === "function";

/** Resolves {ok: true} or {ok: false, problem: "unsupported" | "denied"}. */
export function requestAccess() {
  if (!midiSupported()) return Promise.resolve({ ok: false, problem: "unsupported" });
  if (access) return Promise.resolve({ ok: true });
  asking ??= navigator
    .requestMIDIAccess({ sysex: false })
    .then((granted) => {
      access = granted;
      // A device plugged in (or removed) later: reopen the wanted one when
      // it appears, as the desktop reconnects at start-up only.
      access.addEventListener("statechange", () => {
        if (wanted && !input) open(wanted);
        else if (input && input.state !== "connected") close();
      });
      return { ok: true };
    })
    .catch(() => {
      asking = null;
      return { ok: false, problem: "denied" };
    });
  return asking;
}

/** The input names the browser lists now; [] before access is granted. */
export function devices() {
  return access ? [...access.inputs.values()].map((port) => port.name) : [];
}

function onMessage(event) {
  const data = event.data;
  if (!data || data.length < 3) return;
  const status = data[0] & 0xf0;
  const [, key, velocity] = data;
  // A note-on with velocity 0 is a note-off (running status).
  if (status === NOTE_ON && velocity > 0) liveNoteOn(key, velocity);
  else if (status === NOTE_ON || status === NOTE_OFF) liveNoteOff(key);
}

function close() {
  if (input) {
    input.onmidimessage = null;
    input = null;
  }
  liveAllNotesOff();
}

function open(name) {
  const port = access && [...access.inputs.values()].find((p) => p.name === name && p.state === "connected");
  if (!port) return false;
  close();
  input = port;
  port.onmidimessage = onMessage;
  return true;
}

/** Connect to the device called `name`, or disconnect for null. Returns
 * true when a device is open. A device that is not there now is opened
 * when it appears. */
export function connect(name) {
  wanted = name || null;
  if (!wanted) {
    close();
    return false;
  }
  return open(wanted);
}

export const isOpen = () => input !== null;

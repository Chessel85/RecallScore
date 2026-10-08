// The one way the page speaks a message that is not the focused item's own
// text (Phase 0 spike 3, docs/rsbv_spike_findings.md):
//
// * Every message goes through this queue. Rapid direct calls lose messages
//   with either delivery method; queued at a gap, all of them were heard in
//   Chrome and Firefox with NVDA.
// * document.ariaNotify where the browser has it (Chrome 154, Firefox 157),
//   else two alternating live regions per priority, cleared and written in
//   turn so identical consecutive text still counts as a change. Never one
//   live region: it drops repeats and loses the polite half of an
//   urgent-then-polite pair.
//
// Priorities: ASSERTIVE for toggles and anything the user just asked for
// (mode changes, "Measure 6.", errors); POLITE for background information
// (the position announcer, loading progress). An assertive message goes
// ahead of any polite ones still waiting, never ahead of earlier assertive
// ones, so nothing is reordered within a priority.
//
// Do not write to a live region anywhere else on the page. The focused
// widget's own reading (a listbox's aria-activedescendant) is the other
// speech path, and it is not this module's business.

export const ASSERTIVE = "assertive";
export const POLITE = "polite";

// The gap spike 3 was run with (its default); every queued message was heard.
const GAP_MS = 250;

const hasAriaNotify = typeof document.ariaNotify === "function";
const queue = []; // [text, priority]
let timer = null;
const flips = { [ASSERTIVE]: false, [POLITE]: false };

/** Speak `text`. The first message after a quiet spell goes out at once, so
 * a caller that speaks and then moves focus is heard in that order. */
export function announce(text, priority = POLITE) {
  if (!text) return;
  const entry = [String(text), priority === ASSERTIVE ? ASSERTIVE : POLITE];
  if (entry[1] === ASSERTIVE) {
    const firstPolite = queue.findIndex(([, p]) => p === POLITE);
    queue.splice(firstPolite === -1 ? queue.length : firstPolite, 0, entry);
  } else {
    queue.push(entry);
  }
  if (timer === null) drain();
}

/** Shorthand for a toggle or a direct answer to a key press. */
export function announceUrgent(text) {
  announce(text, ASSERTIVE);
}

/** Drop polite messages not yet spoken, e.g. stale position announcements
 * once playback stops. Assertive ones are always delivered. */
export function dropPolite() {
  for (let i = queue.length - 1; i >= 0; i -= 1) {
    if (queue[i][1] === POLITE) queue.splice(i, 1);
  }
}

function drain() {
  const next = queue.shift();
  if (next === undefined) {
    timer = null;
    return;
  }
  deliver(...next);
  timer = setTimeout(drain, GAP_MS);
}

function deliver(text, priority) {
  if (hasAriaNotify) {
    try {
      document.ariaNotify(text, { priority: priority === ASSERTIVE ? "high" : "normal" });
      return;
    } catch {
      // Fall through to the live regions.
    }
  }
  flips[priority] = !flips[priority];
  const [now, previous] = flips[priority] ? ["a", "b"] : ["b", "a"];
  regionFor(priority, previous).textContent = "";
  regionFor(priority, now).textContent = text;
}

// The four regions are created here, once, so no page can forget one or add
// a fifth. Created at import time, i.e. before any message is spoken: a live
// region must already be in the document when its text changes.
const regions = {};
for (const priority of [ASSERTIVE, POLITE]) {
  for (const side of ["a", "b"]) {
    const el = document.createElement("div");
    el.className = "visually-hidden";
    el.setAttribute("aria-live", priority);
    el.setAttribute("aria-atomic", "true");
    el.id = `live-${priority}-${side}`;
    document.body.append(el);
    regions[`${priority}-${side}`] = el;
  }
}

function regionFor(priority, side) {
  return regions[`${priority}-${side}`];
}

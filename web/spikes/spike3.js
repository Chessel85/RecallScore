import { wireCopyButton, renderReport } from "./common.js";

const METHODS = ["ariaNotify", "alternating", "single"];
const TESTS = [
  "1 Once",
  "2 Same text twice",
  "3 Five at once",
  "4 Five queued",
  "5 Urgent then polite",
  "6 While navigating",
];
const OUTCOMES = ["not tried", "all heard", "some heard", "none heard", "heard, but garbled or cut off"];
const hasAriaNotify = "ariaNotify" in document;

document.getElementById("support").textContent = hasAriaNotify
  ? "This browser supports ariaNotify."
  : "This browser does not support ariaNotify. Skip that column.";

const method = () => document.querySelector('input[name="method"]:checked').value;
const gapMs = () => Number(document.getElementById("gap").value);

// --- the three delivery methods --------------------------------------------

const flips = { assertive: false, polite: false };

function deliver(text, priority) {
  const m = method();
  if (m === "ariaNotify") {
    if (!hasAriaNotify) return;
    document.ariaNotify(text, { priority: priority === "assertive" ? "high" : "normal" });
  } else if (m === "alternating") {
    // Clear the other region and write this one, so identical consecutive
    // text is still a change the screen reader notices.
    flips[priority] = !flips[priority];
    const [now, previous] = flips[priority] ? ["a", "b"] : ["b", "a"];
    document.getElementById(`${priority}-${previous}`).textContent = "";
    document.getElementById(`${priority}-${now}`).textContent = text;
  } else {
    document.getElementById(`single-${priority}`).textContent = text;
  }
}

// A minimal queue: messages go out one per gap, never merged or dropped.
const queue = [];
let draining = false;
function enqueue(text, priority = "assertive") {
  queue.push([text, priority]);
  if (!draining) drain();
}
function drain() {
  const next = queue.shift();
  if (!next) {
    draining = false;
    return;
  }
  draining = true;
  deliver(...next);
  setTimeout(drain, gapMs());
}

// --- tests -------------------------------------------------------------------

const WORDS = ["one", "two", "three", "four", "five"];
const RUNNERS = {
  1: () => deliver("Metronome on", "assertive"),
  2: () => {
    deliver("Loop bar", "assertive");
    setTimeout(() => deliver("Loop bar", "assertive"), 500);
  },
  3: () => WORDS.forEach((w) => deliver(w, "assertive")),
  4: () => WORDS.forEach((w) => enqueue(w, "assertive")),
  5: () => {
    deliver("Playing", "assertive");
    deliver("Bar 3", "polite");
  },
  6: () => document.getElementById("test-list").focus(),
};

document.querySelectorAll("button[data-test]").forEach((button) => {
  button.addEventListener("click", () => RUNNERS[button.dataset.test]());
});

// Test list: a real listbox, so Down Arrow moves and the screen reader
// reads the new option while the page also announces "bar line".
const list = document.getElementById("test-list");
const NOTES = ["C quarter note", "D quarter note", "E quarter note", "F quarter note", "G half note", "A quarter note", "B quarter note", "C whole note"];
NOTES.forEach((text, i) => {
  const option = document.createElement("div");
  option.setAttribute("role", "option");
  option.id = `opt-${i}`;
  option.textContent = text;
  option.setAttribute("aria-selected", i === 0 ? "true" : "false");
  list.appendChild(option);
});
let active = 0;
list.addEventListener("keydown", (event) => {
  if (/^Digit[1-6]$/.test(event.code)) {
    event.preventDefault();
    const n = event.code.slice(5);
    if (n !== "6") RUNNERS[n]();
    return;
  }
  const delta = { ArrowDown: 1, ArrowUp: -1 }[event.key];
  if (!delta) return;
  event.preventDefault();
  const next = Math.max(0, Math.min(NOTES.length - 1, active + delta));
  if (next === active) return;
  document.getElementById(`opt-${active}`).setAttribute("aria-selected", "false");
  active = next;
  const option = document.getElementById(`opt-${active}`);
  option.setAttribute("aria-selected", "true");
  list.setAttribute("aria-activedescendant", option.id);
  enqueue("bar line", "assertive");
});

// --- results table -------------------------------------------------------------

const results = {};
const body = document.getElementById("results");
for (const test of TESTS) {
  const tr = document.createElement("tr");
  const th = document.createElement("th");
  th.scope = "row";
  th.textContent = test;
  tr.appendChild(th);
  for (const m of METHODS) {
    const td = document.createElement("td");
    const select = document.createElement("select");
    select.setAttribute("aria-label", `${test}, ${m}`);
    for (const outcome of OUTCOMES) select.add(new Option(outcome));
    select.addEventListener("change", () => {
      results[`${test}|${m}`] = select.value;
      renderReport(reportLines());
    });
    td.appendChild(select);
    tr.appendChild(td);
  }
  body.appendChild(tr);
}

function reportLines() {
  const lines = [`Queue gap: ${gapMs()} ms`, "Test | ariaNotify | alternating | single"];
  for (const test of TESTS) {
    lines.push(`${test} | ${METHODS.map((m) => results[`${test}|${m}`] || "not tried").join(" | ")}`);
  }
  lines.push("Screen reader and version: (fill in)");
  return lines;
}

wireCopyButton(reportLines);
renderReport(reportLines());

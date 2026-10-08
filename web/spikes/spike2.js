import { status, wireCopyButton, renderReport } from "./common.js";

// Every key the POC plans to use (plan: Phase 0, spike 2), plus the
// navigation keys the regions need. Tab and Escape are recorded but never
// blocked, so the tester can still move between widgets and close menus.
const PLANNED = [
  "Space", "Ctrl+Space", "Ctrl+Alt+Space", "Pause",
  "Ctrl+L", "Ctrl+B", "Ctrl+M", "Ctrl+G", "Ctrl+P", "Ctrl+R", "Ctrl+H",
  "Ctrl+O", "Ctrl+F", "Ctrl+A",
  "Alt+Left", "Alt+Right", "F10", "Alt", "Shift+F10", "ContextMenu", "F1",
  "Z", "X", "C", "V", "B", "N",
  "Left", "Right", "Up", "Down", "Ctrl+Left", "Ctrl+Right", "Ctrl+Home", "Ctrl+End",
  "Tab", "Shift+Tab", "Escape",
];
const NEVER_BLOCK = new Set(["Tab", "Shift+Tab", "Escape"]);
const WIDGETS = ["listbox", "tree", "application"];
const SPOKEN = { Ctrl: "Control", Left: "Left Arrow", Right: "Right Arrow", Up: "Up Arrow", Down: "Down Arrow", ContextMenu: "Applications key" };

const reached = new Map(PLANNED.map((key) => [key, new Set()]));
const other = [];

function keyName(event) {
  const code = event.code;
  if (/^Key[A-Z]$/.test(code)) return code.slice(3);
  if (/^Digit\d$/.test(code)) return code.slice(5);
  if (code.startsWith("Arrow")) return code.slice(5);
  if (code === "AltLeft" || code === "AltRight") return "Alt";
  if (code.startsWith("Control") || code.startsWith("Shift") || code.startsWith("Meta")) return null;
  return code || event.key;
}

function combo(event) {
  const name = keyName(event);
  if (name === null) return null;
  if (name === "Alt") return event.ctrlKey || event.shiftKey ? null : "Alt";
  const mods = [];
  if (event.ctrlKey) mods.push("Ctrl");
  if (event.altKey) mods.push("Alt");
  if (event.shiftKey) mods.push("Shift");
  if (event.metaKey) mods.push("Meta");
  return [...mods, name].join("+");
}

function spoken(text) {
  return text.split("+").map((part) => SPOKEN[part] || part).join(" ");
}

let flip = false;
function announce(text) {
  // Two alternating live regions, so pressing the same key twice is still read.
  flip = !flip;
  const now = document.getElementById(flip ? "announce-a" : "announce-b");
  const previous = document.getElementById(flip ? "announce-b" : "announce-a");
  previous.textContent = "";
  now.textContent = text;
}

function currentWidget() {
  return document.activeElement?.closest?.("[data-widget]")?.dataset.widget || "page";
}

let altAlone = false;
document.addEventListener("keydown", (event) => {
  const name = combo(event);
  altAlone = name === "Alt";
  if (name === null || name === "Alt") {
    if (name === "Alt") event.preventDefault();
    return;
  }
  record(name, event);
}, true);

document.addEventListener("keyup", (event) => {
  if (combo(event) === "Alt" && altAlone) {
    event.preventDefault();
    record("Alt", event);
  }
  altAlone = false;
}, true);

function record(name, event) {
  const widget = currentWidget();
  if (reached.has(name)) {
    if (!NEVER_BLOCK.has(name)) event.preventDefault();
    if (widget !== "page") reached.get(name).add(widget);
    announce(`reached: ${spoken(name)}`);
    renderTable();
  } else {
    other.push(`${name} in ${widget}`);
    const li = document.createElement("li");
    li.textContent = `${name} in ${widget}`;
    document.getElementById("other-keys").appendChild(li);
  }
}

function renderTable() {
  const body = document.getElementById("results");
  body.replaceChildren();
  for (const key of PLANNED) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = key;
    tr.appendChild(th);
    for (const widget of WIDGETS) {
      const td = document.createElement("td");
      td.textContent = reached.get(key).has(widget) ? "yes" : "no";
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  const counts = WIDGETS.map((w) => `${w} ${PLANNED.filter((k) => reached.get(k).has(w)).length}`);
  document.getElementById("summary").textContent =
    `Keys reached, out of ${PLANNED.length}: ${counts.join(", ")}.`;
  renderReport(reportLines());
}

function reportLines() {
  const lines = ["Key | listbox | tree | application"];
  for (const key of PLANNED) {
    lines.push(`${key} | ${WIDGETS.map((w) => (reached.get(key).has(w) ? "yes" : "no")).join(" | ")}`);
  }
  if (other.length) lines.push(`Other keys received: ${[...new Set(other)].join(", ")}`);
  lines.push("Screen reader and version: (fill in)");
  return lines;
}

wireCopyButton(reportLines);
renderTable();
status("Ready. Tab to a test widget.");

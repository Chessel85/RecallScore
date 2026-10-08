import { announce } from "./announcer.js";
import { boot, loadScore } from "./py_bridge.js";

const status = document.getElementById("status");
const errorBox = document.getElementById("error");
const picker = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const summary = document.getElementById("summary");

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

function showSummary(info) {
  summary.replaceChildren();
  for (const [label, value] of Object.entries(info.credits)) {
    const row = document.createElement("li");
    row.textContent = `${label}: ${value}`;
    summary.append(row);
  }
  const parts = document.createElement("li");
  parts.textContent = `Parts: ${info.parts.map((p) => p.name).join(", ")}`;
  summary.append(parts);
}

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
  const result = loadScore(bytes, file.name);
  if (result.error) {
    showError(result.error);
    return;
  }
  showSummary(result.summary);
  say(`Loaded ${file.name}. ${result.summary.parts.length} parts, ${result.summary.slices} notes and chords.`);
  summary.focus();
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
boot(say)
  .then(() => {
    ready = true;
    picker.disabled = false;
    say("Ready. Choose a score file.");
  })
  .catch((err) => showError(`Could not start: ${err.message}`));

// Shared helpers for the Phase 0 spike pages. Throwaway code: the real
// announcer lives in web/js/announcer.js from Phase 2 onwards.

const reportLines = [];

/** Short spoken progress line (polite live region with id "status"). */
export function status(text) {
  const el = document.getElementById("status");
  if (el) el.textContent = text;
  log(text);
}

/** Append a line to the on-page log (not live, so it never chatters). */
export function log(text) {
  console.log(text);
  const list = document.getElementById("log");
  if (!list) return;
  const li = document.createElement("li");
  li.textContent = text;
  list.appendChild(li);
}

/** Add a line to the report the tester copies into the findings doc. */
export function report(line) {
  reportLines.push(line);
  renderReport();
}

export function renderReport(extraLines = []) {
  const box = document.getElementById("report");
  if (box) box.value = [environmentLine(), ...reportLines, ...extraLines].join("\n");
}

export function environmentLine() {
  return `Browser: ${navigator.userAgent} | ariaNotify: ${"ariaNotify" in document ? "yes" : "no"} | date: ${new Date().toISOString()}`;
}

/** Wire the "Copy report" button; falls back to selecting the text box. */
export function wireCopyButton(getExtraLines = () => []) {
  const button = document.getElementById("copy-report");
  if (!button) return;
  button.addEventListener("click", async () => {
    renderReport(getExtraLines());
    const box = document.getElementById("report");
    try {
      await navigator.clipboard.writeText(box.value);
      status("Report copied to the clipboard.");
    } catch {
      box.focus();
      box.select();
      status("Copy failed. The report text is selected; press Ctrl+C.");
    }
  });
}

export function median(values) {
  if (!values.length) return NaN;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export const ms = (value) => `${Math.round(value)} ms`;

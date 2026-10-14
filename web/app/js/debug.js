// Diagnostics for screen-reader problems, on only with ?debug in the URL.
// Adds a "Debug log" section at the end of the page that lists, in browse
// mode, what the page itself saw: keys pressed, focus moving, errors. It
// only listens; it never handles a command (those all live in keymap.js).

if (new URLSearchParams(location.search).has("debug")) {
  const section = document.createElement("section");
  const heading = document.createElement("h2");
  heading.textContent = "Debug log";
  const list = document.createElement("ol");
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "Copy debug log";
  section.append(heading, copy, list);
  document.body.append(section);
  const lines = [];
  const t0 = performance.now();

  const describe = (el) =>
    el ? `${el.tagName.toLowerCase()}#${el.id || "-"}[${el.getAttribute?.("role") || "-"}] "${(el.textContent || "").slice(0, 30)}"` : "none";
  const log = (text) => {
    const line = `${Math.round(performance.now() - t0)} ms ${text}`;
    lines.push(line);
    if (list.children.length >= 40) list.firstChild.remove();
    const li = document.createElement("li");
    li.textContent = line;
    list.append(li);
  };

  document.addEventListener("keydown", (e) => log(`keydown ${e.code} ctrl=${e.ctrlKey} alt=${e.altKey} shift=${e.shiftKey} target=${describe(e.target)}`), true);
  document.addEventListener("focusin", (e) => log(`focusin ${describe(e.target)}`));
  document.addEventListener("focusout", (e) => log(`focusout ${describe(e.target)} -> ${describe(e.relatedTarget)}`));
  window.addEventListener("error", (e) => log(`ERROR ${e.message} at ${e.filename}:${e.lineno}`));
  window.addEventListener("unhandledrejection", (e) => log(`REJECTED ${e.reason}`));
  copy.addEventListener("click", () => navigator.clipboard?.writeText(lines.join("\n")));
  log(`debug log on; ariaNotify=${typeof document.ariaNotify}`);
}

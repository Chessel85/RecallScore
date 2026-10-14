// Dialogs: the keyboard help list, Go to bar and Play Settings, on native <dialog>. (The
// Menu is a real ARIA menu, in menu.js.) Rules every dialog here follows:
// * Initial focus goes to the first widget in tab order, never a "more
//   useful" later one (the desktop's dialog rule).
// * There is always an explicit Close or Cancel button, because Escape may
//   never arrive (NVDA keeps it). Escape also works where the browser
//   delivers it.
// * While one is open, keymap.js leaves every key to the dialog.
// * The help list is built from keymap.js, so a command appears here the
//   moment it is bound and shows the key it really has.

import { boundCommands, spokenKey } from "./keymap.js";

const FOCUSABLE = "button, input, select, textarea, a[href], [tabindex]:not([tabindex='-1'])";

const GROUPS = {
  focus: "Regions",
  list: "Lists",
  tree: "Parts",
  region2: "Parts",
  nav: "Navigation",
  goto: "Navigation",
  digits: "Navigation",
  play: "Playback",
  tempo: "Playback",
  options: "Options",
  notes: "Notes",
  attributes: "Attributes",
  help: "Help",
};

let serial = 0;

/** A modal dialog with a heading and a Close/Cancel row the caller fills.
 * Returns {dialog, body, footer, open, close}. */
function makeDialog(title) {
  serial += 1;
  const dialog = document.createElement("dialog");
  const heading = document.createElement("h2");
  heading.id = `dialog-title-${serial}`;
  heading.textContent = title;
  dialog.setAttribute("aria-labelledby", heading.id);
  const body = document.createElement("div");
  const footer = document.createElement("div");
  footer.className = "dialog-buttons";
  dialog.append(heading, body, footer);
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  return {
    dialog,
    body,
    footer,
    open() {
      dialog.showModal();
      dialog.querySelector(FOCUSABLE)?.focus();
    },
    close: () => dialog.close(),
  };
}

function button(text, onClick, type = "button") {
  const el = document.createElement("button");
  el.type = type;
  el.textContent = text;
  if (onClick) el.addEventListener("click", onClick);
  return el;
}

/** "Control 1 to Control 9" for a long run, else "Control G or Enter". */
export function keysText(keys) {
  if (keys.length > 2) return `${spokenKey(keys[0])} to ${spokenKey(keys[keys.length - 1])}`;
  return keys.map(spokenKey).join(" or ");
}

/** The bound commands grouped for display, in table order. */
function groupedCommands(include = () => true) {
  const groups = new Map();
  for (const row of boundCommands()) {
    if (!include(row)) continue;
    const name = GROUPS[row.id.split(".")[0]] ?? "Other";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(row);
  }
  return groups;
}

/** F1: every command and its key, read-only. */
export function showHelp() {
  const d = makeDialog("Keyboard help");
  const intro = document.createElement("p");
  intro.textContent = "Every command and its key. Z X C V B N jump to the regions; Tab and Shift Tab cycle them.";
  d.body.append(intro);
  for (const [name, rows] of groupedCommands()) {
    const heading = document.createElement("h3");
    heading.textContent = name;
    const list = document.createElement("ul");
    for (const row of rows) {
      const li = document.createElement("li");
      li.textContent = `${row.label}: ${keysText(row.keys)}`;
      list.append(li);
    }
    d.body.append(heading, list);
  }
  const close = button("Close", () => d.close());
  d.footer.append(close);
  // Nothing in the list takes focus, so the first widget in tab order is
  // Close; make that explicit rather than rely on the browser's default.
  d.open();
  close.focus();
}

/** Go to bar: resolves to the typed whole number, or null if cancelled or
 * left empty. `info` is web_api.goto_info(). */
export function showGotoBar(info) {
  return new Promise((resolve) => {
    const d = makeDialog(`Go to ${info.word}`);
    const form = document.createElement("form");
    form.method = "dialog";
    const label = document.createElement("label");
    label.textContent = `${info.word} number`;
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "numeric";
    input.pattern = "[0-9]*";
    input.maxLength = 4;
    input.autocomplete = "off";
    if (info.current !== null && info.current !== undefined) input.value = String(info.current);
    label.append(" ", input);
    form.append(label);
    d.body.append(form);
    const ok = button("OK", null, "submit");
    d.footer.append(ok, button("Cancel", () => d.close()));
    let answer = null;
    form.addEventListener("submit", () => {
      const text = input.value.trim();
      answer = /^\d{1,4}$/.test(text) ? Number(text) : null;
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    // The OK button is in the footer, outside the form: submit it from there.
    ok.addEventListener("click", (event) => {
      event.preventDefault();
      form.requestSubmit();
    });
    d.open();
    input.select();
  });
}

/** Play Settings (Ctrl+Alt+P): `form` is web_api.play_settings_form(),
 * `enabledFor(leadIn, playMode)` asks the bridge which fields are live
 * (the desktop dialog's rules) whenever the lead-in tick or the play mode
 * changes. Resolves to {name: value} on OK (number fields as typed; the
 * bridge clamps), or null on Cancel. */
export function showPlaySettings(form, enabledFor) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const el = document.createElement("form");
    el.method = "dialog";
    el.id = `play-settings-${serial}`;
    const inputs = new Map();
    for (const field of form.fields) {
      // A separate <label for>, not one wrapping the control: a wrapped
      // select can have its chosen option read into its name.
      const row = document.createElement("div");
      row.className = "dialog-field";
      const label = document.createElement("label");
      label.textContent = field.label;
      let input;
      if (field.type === "select") {
        input = document.createElement("select");
        for (const option of field.options) {
          const opt = document.createElement("option");
          opt.value = option.value;
          opt.textContent = option.label;
          input.append(opt);
        }
        input.value = field.value;
      } else {
        input = document.createElement("input");
        input.type = field.type;
        if (field.type === "checkbox") input.checked = Boolean(field.value);
        else {
          input.min = String(field.min);
          input.max = String(field.max);
          input.step = "1";
          input.value = String(field.value);
        }
      }
      input.name = field.name;
      input.id = `${el.id}-${field.name}`;
      label.htmlFor = input.id;
      if (field.type === "checkbox") row.append(input, " ", label);
      else row.append(label, " ", input);
      el.append(row);
      inputs.set(field.name, input);
    }
    d.body.append(el);

    const applyEnabled = (enabled) => {
      for (const [name, live] of Object.entries(enabled ?? {})) {
        const input = inputs.get(name);
        if (input) input.disabled = !live;
      }
    };
    const refresh = () => applyEnabled(enabledFor(inputs.get("lead_in_enabled").checked, inputs.get("play_mode").value));
    inputs.get("lead_in_enabled").addEventListener("change", refresh);
    inputs.get("play_mode").addEventListener("change", refresh);
    applyEnabled(form.enabled);

    // The buttons sit in the footer but belong to the form, so Enter in a
    // field submits it as OK.
    const ok = button("OK", null, "submit");
    ok.setAttribute("form", el.id);
    d.footer.append(ok, button("Cancel", () => d.close()));
    let answer = null;
    el.addEventListener("submit", () => {
      answer = {};
      for (const [name, input] of inputs) answer[name] = input.type === "checkbox" ? input.checked : input.value;
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    d.open();
  });
}

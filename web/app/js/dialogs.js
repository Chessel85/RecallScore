// Dialogs: the keyboard help list, Go to bar, Play Settings and the Mixer,
// on native <dialog>. (The Menu is a real ARIA menu, in menu.js.) Rules
// every dialog here follows:
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

/** Mixer (Ctrl+Shift+X), the desktop's MixerDialog: a list of the parts and
 * app sounds, then Volume and Pan for the chosen row, Preview, OK, Cancel.
 * `form` is web_api.mixer_form(). Every change is handed to `change(key,
 * field, percent)` at once, so it is heard while the dialog is open (the
 * bridge keeps it; OK or Cancel decides). `preview()` starts or stops
 * playback (Alt+W or the button). Resolves true on OK, false on Cancel.
 *
 * Changes are taken from arrow steps and committed values (Enter, leaving
 * the field), not from each typed digit: typing 100 never sounds 1 and 10
 * first (the desktop's keyboardTracking off). Home is the highest value,
 * End the lowest and Insert the reset value (the desktop's RangeSpinBox). */
export function showMixer(form, { change, preview }) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const el = document.createElement("form");
    el.method = "dialog";
    el.id = `mixer-${serial}`;
    const values = new Map(form.rows.map((row) => [row.key, { volume: row.volume, pan: row.pan }]));

    const field = (name, labelText, control) => {
      const row = document.createElement("div");
      row.className = "dialog-field";
      const label = document.createElement("label");
      label.textContent = labelText;
      control.id = `${el.id}-${name}`;
      label.htmlFor = control.id;
      row.append(label, " ", control);
      el.append(row);
    };

    const list = document.createElement("select");
    list.size = Math.min(Math.max(form.rows.length, 2), 10);
    for (const row of form.rows) {
      const option = document.createElement("option");
      option.value = row.key;
      option.textContent = row.label;
      list.append(option);
    }
    field("rows", "Part or sound", list);

    const number = (name, label, min, max, reset) => {
      const input = document.createElement("input");
      input.type = "number";
      input.min = String(min);
      input.max = String(max);
      input.step = "1";
      input.dataset.reset = String(reset);
      field(name, label, input);
      return input;
    };
    const volume = number("volume", "Volume %", 0, 100, form.volume_reset);
    const pan = number("pan", "Pan %", -100, 100, form.pan_reset);
    const inputs = { volume, pan };

    const show = () => {
      const now = values.get(list.value);
      if (!now) return;
      volume.value = String(now.volume);
      pan.value = String(now.pan);
    };

    /** Clamp what is in the field, keep it for the row and hand it on. */
    const commit = (name) => {
      const input = inputs[name];
      const now = values.get(list.value);
      const typed = Number.parseInt(input.value, 10);
      if (!now || Number.isNaN(typed)) {
        if (now) input.value = String(now[name]);
        return;
      }
      const value = Math.min(Number(input.max), Math.max(Number(input.min), typed));
      if (String(value) !== input.value) input.value = String(value);
      if (value === now[name]) return;
      now[name] = value;
      change(list.value, name, value);
    };

    for (const [name, input] of Object.entries(inputs)) {
      // An arrow step arrives as an input event with no inputType; typing
      // has one (insertText, deleteContentBackward...) and waits for change.
      input.addEventListener("input", (event) => {
        if (!event.inputType) commit(name);
      });
      input.addEventListener("change", () => commit(name));
      input.addEventListener("keydown", (event) => {
        if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
        const to = { Home: input.max, End: input.min, Insert: input.dataset.reset }[event.key];
        if (to === undefined) return;
        event.preventDefault();
        input.value = to;
        commit(name);
      });
    }
    list.addEventListener("change", show);
    d.body.append(el);

    const previewButton = button("Preview Alt+W", () => preview());
    d.body.append(previewButton);
    d.dialog.addEventListener("keydown", (event) => {
      if (event.altKey && !event.ctrlKey && !event.shiftKey && !event.metaKey && event.code === "KeyW") {
        event.preventDefault();
        preview();
      }
    });

    // OK belongs to the form, so Enter in a field is OK, after that
    // field's value is taken.
    const ok = button("OK", null, "submit");
    ok.setAttribute("form", el.id);
    d.footer.append(ok, button("Cancel", () => d.close()));
    let accepted = false;
    el.addEventListener("submit", () => {
      commit("volume");
      commit("pan");
      accepted = true;
    });
    d.dialog.addEventListener("close", () => resolve(accepted));

    if (form.rows.length) list.selectedIndex = 0;
    show();
    d.open();
  });
}

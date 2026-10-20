// Dialogs: the keyboard help list, Go to bar, Find, the Performance Report,
// Play Settings, the Mixer, and the score edits (Instruments, Key
// Signature, Reorder Parts, Link Parts),
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
  parts: "Parts",
  edit: "Edit",
  nav: "Navigation",
  goto: "Navigation",
  find: "Navigation",
  report: "Tools",
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
  // Tab and Shift+Tab wrap inside the dialog. A modal <dialog> lets Tab
  // leave the last widget for the browser's own toolbar (Firefox).
  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || event.ctrlKey || event.altKey || event.metaKey) return;
    const stops = [...dialog.querySelectorAll(FOCUSABLE)].filter(
      (el) => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length,
    );
    if (!stops.length) return;
    const [first, last] = [stops[0], stops[stops.length - 1]];
    const at = document.activeElement;
    if (event.shiftKey ? at === first || !dialog.contains(at) : at === last) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
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

/** Find (Ctrl+Shift+F), the desktop's FindDialog: the list of what this score
 * has to find, each with its count, then a Filter box that narrows the list
 * to rows whose label contains what is typed (the bridge's `filter` text,
 * never the count digits), then OK and Cancel. Enter on the list or in the
 * filter is OK. `form` is web_api.find_form(). Resolves to the chosen row's
 * index in form.rows, or null on Cancel. */
export function showFind(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const el = document.createElement("form");
    el.method = "dialog";
    el.id = `find-${serial}`;

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
    list.size = Math.min(Math.max(form.rows.length, 2), 12);
    field("list", "Find", list);
    const filter = document.createElement("input");
    filter.type = "text";
    filter.autocomplete = "off";
    field("filter", "Filter", filter);
    d.body.append(el);

    const ok = button("OK", null, "submit");
    ok.setAttribute("form", el.id);
    d.footer.append(ok, button("Cancel", () => d.close()));

    // Rebuilt on every change of the filter. The chosen row stays chosen
    // while it is still listed, else the first listed row is.
    const fill = () => {
      const needle = filter.value.trim().toLowerCase();
      const keep = list.value;
      list.replaceChildren();
      form.rows.forEach((row, i) => {
        if (needle && !row.filter.includes(needle)) return;
        const option = document.createElement("option");
        option.value = String(i);
        option.textContent = row.text;
        list.append(option);
      });
      list.value = keep;
      if (list.selectedIndex === -1 && list.options.length) list.selectedIndex = 0;
      ok.disabled = list.options.length === 0;
    };
    filter.addEventListener("input", fill);
    // A list box does not submit on Enter by itself.
    list.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey) return;
      event.preventDefault();
      if (!ok.disabled) el.requestSubmit();
    });

    let answer = null;
    el.addEventListener("submit", () => {
      answer = list.value === "" ? null : Number(list.value);
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    fill();
    d.open();
  });
}

/** Performance Report (Ctrl+Shift+R), the desktop's PerformanceReportDialog:
 * a read-only tree, every heading (level 0) collapsed, its details (level
 * 1) under it, then Close. The rows take real focus (roving tabindex), as
 * in the regions. Up/Down/Home/End move over the rows showing; Right opens
 * a heading or steps into it, Left closes it or steps out to it. Enter on
 * a row that goes somewhere (form.rows[i].jumps) closes the dialog and
 * resolves to that row's index; Enter anywhere else does nothing, as on
 * the desktop. Resolves null on Close. `form` is web_api.report_form(). */
export function showReport(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const label = document.createElement("div");
    label.id = `report-label-${serial}`;
    label.textContent = form.label;
    const tree = document.createElement("div");
    tree.className = "report-tree";
    tree.setAttribute("role", "tree");
    tree.setAttribute("aria-labelledby", label.id);
    d.body.append(label, tree);

    // One entry per row: its element, its heading's entry (null for a
    // heading) and, for a heading, its details. A detail before any
    // heading is shown at the top level, as the desktop does.
    const items = [];
    let heading = null;
    form.rows.forEach((row, index) => {
      const el = document.createElement("div");
      el.id = `report-${serial}-${index}`;
      el.setAttribute("role", "treeitem");
      el.textContent = row.text;
      el.tabIndex = -1;
      const item = { el, index, row, parent: null, children: [] };
      if (row.level !== 0 && heading) {
        item.parent = heading;
        heading.children.push(item);
      } else if (row.level === 0) {
        heading = item;
      }
      items.push(item);
      tree.append(el);
    });
    const tops = items.filter((item) => !item.parent);
    for (const [list, level] of [[tops, 1], ...tops.map((top) => [top.children, 2])]) {
      list.forEach((item, i) => {
        item.el.setAttribute("aria-level", String(level));
        item.el.setAttribute("aria-posinset", String(i + 1));
        item.el.setAttribute("aria-setsize", String(list.length));
      });
    }
    const open = new Set();
    let current = items[0] ?? null;

    const visible = () => items.filter((item) => !item.parent || open.has(item.parent));
    const show = (focus = true) => {
      for (const item of items) {
        item.el.hidden = Boolean(item.parent) && !open.has(item.parent);
        if (item.children.length) item.el.setAttribute("aria-expanded", open.has(item) ? "true" : "false");
        item.el.tabIndex = item === current ? 0 : -1;
        item.el.setAttribute("aria-selected", item === current ? "true" : "false");
      }
      if (focus) current?.el.focus();
      current?.el.scrollIntoView?.({ block: "nearest" });
    };

    tree.addEventListener("keydown", (event) => {
      if (!current || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey) return;
      const rows = visible();
      const at = rows.indexOf(current);
      const go = (item) => {
        if (item && item !== current) {
          current = item;
          show();
        }
      };
      switch (event.key) {
        case "ArrowUp": go(rows[at - 1]); break;
        case "ArrowDown": go(rows[at + 1]); break;
        case "Home": go(rows[0]); break;
        case "End": go(rows[rows.length - 1]); break;
        case "ArrowRight":
          if (current.children.length && !open.has(current)) {
            open.add(current);
            show();
          } else if (current.children.length) go(current.children[0]);
          break;
        case "ArrowLeft":
          if (open.has(current)) {
            open.delete(current);
            show();
          } else go(current.parent);
          break;
        case "Enter":
          if (current.row.jumps) {
            answer = current.index;
            d.close();
          }
          break;
        default:
          return;
      }
      event.preventDefault();
    });
    tree.addEventListener("click", (event) => {
      const item = items.find((it) => it.el === event.target);
      if (item) {
        current = item;
        show();
      }
    });

    d.footer.append(button("Close", () => d.close()));
    let answer = null;
    d.dialog.addEventListener("close", () => resolve(answer));
    show(false);
    d.open();
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

/** A labelled control in a form: a separate <label for>, never one wrapped
 * round the control (a wrapped select can have its chosen option read into
 * its name). A checkbox goes before its label. */
function addField(form, name, labelText, control) {
  const row = document.createElement("div");
  row.className = "dialog-field";
  const label = document.createElement("label");
  label.textContent = labelText;
  control.id = `${form.id}-${name}`;
  label.htmlFor = control.id;
  if (control.type === "checkbox") row.append(control, " ", label);
  else row.append(label, " ", control);
  form.append(row);
  return control;
}

/** A <form method=dialog> with OK (submit) and Cancel in the footer, so
 * Enter in a field is OK. */
function okCancelForm(d, prefix) {
  const el = document.createElement("form");
  el.method = "dialog";
  el.id = `${prefix}-${serial}`;
  d.body.append(el);
  const ok = button("OK", null, "submit");
  ok.setAttribute("form", el.id);
  d.footer.append(ok, button("Cancel", () => d.close()));
  return { el, ok };
}

/** A select (list box or drop-down) does not submit on Enter by itself. */
function submitOnEnter(list, form) {
  list.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey) return;
    event.preventDefault();
    form.requestSubmit();
  });
}

function listBox(texts, size = 10) {
  const list = document.createElement("select");
  list.size = Math.min(Math.max(texts.length, 2), size);
  texts.forEach((text, i) => list.append(new Option(text, String(i))));
  return list;
}

/** Instruments (Ctrl+Alt+I), the desktop's InstrumentDialog: the parts,
 * each percussion part followed by its drums and cymbals, then Name,
 * Instrument and "Percussion part" for the chosen row, the percussion
 * offset tick when the score has percussion, OK, Cancel. An item row's
 * Instrument lists the GM percussion sounds; a part playing as a kit has
 * none (greyed); "Percussion part" can be changed only on a part the file
 * does not declare percussion, and its drum rows appear after OK. `form`
 * is web_api.instruments_form(). Resolves to {values, autoCorrect} (one
 * {name, sound, percussion} per row; the bridge works out what changed),
 * or null on Cancel. */
export function showInstruments(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const { el } = okCancelForm(d, "instruments");
    const values = form.rows.map((row) => ({ name: row.name, sound: row.sound, percussion: row.percussion }));

    const list = addField(el, "rows", "Parts", listBox(form.rows.map((row) => row.name)));
    const name = document.createElement("input");
    name.type = "text";
    name.autocomplete = "off";
    addField(el, "name", "Name", name);
    const instrument = addField(el, "instrument", "Instrument", document.createElement("select"));
    const percussion = document.createElement("input");
    percussion.type = "checkbox";
    addField(el, "percussion", "Percussion part", percussion);
    let autoCorrect = null;
    if (form.auto_correct !== null && form.auto_correct !== undefined) {
      autoCorrect = document.createElement("input");
      autoCorrect.type = "checkbox";
      autoCorrect.checked = Boolean(form.auto_correct);
      addField(el, "offset", "Apply MusicXML offset for percussion", autoCorrect);
    }
    submitOnEnter(list, el);
    submitOnEnter(instrument, el);

    // "pitched" (the 128 GM instruments), "percussion" (GM percussion
    // sounds) or "none" (a kit's own row: nothing to choose). A sound not
    // in the list (a drum with no GM name) is shown as an extra choice.
    let mode = null;
    const choices = (wanted, sound) => {
      if (wanted !== mode) {
        mode = wanted;
        const names = { pitched: form.instruments, percussion: form.percussion_sounds }[mode] ?? [];
        instrument.replaceChildren(...names.map((text) => new Option(text, text)));
      }
      instrument.querySelector("option[data-extra]")?.remove();
      if (mode !== "none" && sound && ![...instrument.options].some((option) => option.value === sound)) {
        const extra = new Option(sound, sound);
        extra.dataset.extra = "true";
        instrument.prepend(extra);
      }
      instrument.value = mode === "none" ? "" : sound ?? "";
      instrument.disabled = mode === "none";
    };
    const current = () => Number(list.value);
    const showSound = (i) => {
      if (form.rows[i].kind === "item") choices("percussion", values[i].sound);
      else choices(values[i].percussion ? "none" : "pitched", values[i].sound);
    };
    const show = () => {
      const i = current();
      const row = form.rows[i];
      if (!row) return;
      name.value = values[i].name;
      percussion.checked = row.kind === "part" && values[i].percussion;
      percussion.disabled = !row.toggleable;
      showSound(i);
    };

    list.addEventListener("change", show);
    name.addEventListener("input", () => {
      if (form.rows[current()]) values[current()].name = name.value;
    });
    instrument.addEventListener("change", () => {
      if (form.rows[current()]) values[current()].sound = instrument.value;
    });
    percussion.addEventListener("change", () => {
      const i = current();
      if (!form.rows[i]?.toggleable) return;
      values[i].percussion = percussion.checked;
      showSound(i);
    });

    let answer = null;
    el.addEventListener("submit", () => {
      answer = { values, autoCorrect: autoCorrect ? autoCorrect.checked : null };
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    if (form.rows.length) list.selectedIndex = 0;
    else for (const control of [name, instrument, percussion]) control.disabled = true;
    show();
    d.open();
  });
}

/** Key Signature (Ctrl+Alt+K), the desktop's KeySignatureDialog: one
 * choice of key for the whole piece, "Use the file's own key" first, then
 * OK and Cancel. `form` is web_api.key_signature_form(). Resolves to the
 * chosen index, or null on Cancel. */
export function showKeySignature(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const { el } = okCancelForm(d, "key-signature");
    const choice = document.createElement("select");
    form.options.forEach((text, i) => choice.append(new Option(text, String(i))));
    choice.value = String(form.current);
    addField(el, "key", form.label, choice);
    submitOnEnter(choice, el);
    let answer = null;
    el.addEventListener("submit", () => {
      answer = Number(choice.value);
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    d.open();
  });
}

/** Reorder Parts (Ctrl+Shift+O), the desktop's PartOrderDialog: the parts,
 * Move Up, Move Down, OK, Cancel. Moves are kept here and only applied on
 * OK. It opens on form.current, the part Region 2's row belongs to. A move
 * button at its end is aria-disabled, not disabled, so the focus stays on
 * it (a disabled button drops the focus). `form` is
 * web_api.part_order_form(). Resolves to the part ids in their new order,
 * or null on Cancel. */
export function showPartOrder(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const { el } = okCancelForm(d, "part-order");
    const order = [...form.rows];
    const list = addField(el, "rows", form.label, listBox(order.map((row) => row.name)));
    submitOnEnter(list, el);

    const refresh = () => {
      const i = list.selectedIndex;
      up.setAttribute("aria-disabled", String(i <= 0));
      down.setAttribute("aria-disabled", String(i < 0 || i >= order.length - 1));
    };
    const move = (delta) => {
      const i = list.selectedIndex;
      const j = i + delta;
      if (i < 0 || j < 0 || j >= order.length) return;
      [order[i], order[j]] = [order[j], order[i]];
      list.options[i].textContent = order[i].name;
      list.options[j].textContent = order[j].name;
      list.selectedIndex = j;
      refresh();
    };
    const up = button("Move Up Alt+U", () => move(-1));
    const down = button("Move Down Alt+D", () => move(1));
    const moves = document.createElement("div");
    moves.className = "dialog-field";
    moves.append(up, " ", down);
    el.append(moves);
    list.addEventListener("change", refresh);
    // The desktop's &Up and &Down mnemonics, from anywhere in the dialog.
    // Taken before the browser, whose Alt+D is its address bar.
    d.dialog.addEventListener("keydown", (event) => {
      if (!event.altKey || event.ctrlKey || event.shiftKey || event.metaKey) return;
      const delta = { KeyU: -1, KeyD: 1 }[event.code];
      if (delta === undefined) return;
      event.preventDefault();
      move(delta);
    });

    let answer = null;
    el.addEventListener("submit", () => {
      answer = order.map((row) => row.id);
    });
    d.dialog.addEventListener("close", () => resolve(answer));
    if (order.length) list.selectedIndex = Math.min(form.current, order.length - 1);
    refresh();
    d.open();
  });
}

/** Link Parts (Ctrl+Alt+L), the desktop's LinkPartsDialog: every part not
 * yet linked, each a checkable row (Space ticks it, read as checked or not
 * checked), then OK and Cancel. OK, or Enter on the list, links every
 * ticked part into one new group; it is unavailable until two are ticked.
 * The rows take real focus (roving tabindex), as in the regions, opening
 * on form.current. `form` is web_api.link_parts_form(). Resolves to the
 * ticked part ids, or null on Cancel. */
export function showLinkParts(form) {
  return new Promise((resolve) => {
    const d = makeDialog(form.title);
    const label = document.createElement("div");
    label.id = `link-label-${serial}`;
    label.textContent = form.label;
    const list = document.createElement("div");
    list.className = "check-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-labelledby", label.id);
    d.body.append(label, list);
    if (!form.rows.length) {
      const none = document.createElement("p");
      none.id = `link-none-${serial}`;
      none.textContent = "Every part is already linked.";
      d.body.append(none);
      d.dialog.setAttribute("aria-describedby", none.id);
    }

    const ticked = new Set();
    let current = form.rows.length ? Math.min(form.current, form.rows.length - 1) : -1;
    let answer = null;

    // aria-disabled rather than disabled, so it can take the focus and is
    // read as unavailable.
    const ok = button("OK", () => {
      if (ticked.size < 2) return;
      answer = form.rows.filter((_, i) => ticked.has(i)).map((row) => row.id);
      d.close();
    });
    d.footer.append(ok, button("Cancel", () => d.close()));

    const options = form.rows.map((row, i) => {
      const option = document.createElement("div");
      option.id = `link-${serial}-${i}`;
      option.setAttribute("role", "option");
      option.textContent = row.name;
      option.addEventListener("click", () => {
        current = i;
        toggle();
      });
      list.append(option);
      return option;
    });
    const show = (focus = true) => {
      options.forEach((option, i) => {
        option.tabIndex = i === current ? 0 : -1;
        option.setAttribute("aria-selected", i === current ? "true" : "false");
        option.setAttribute("aria-checked", ticked.has(i) ? "true" : "false");
      });
      ok.setAttribute("aria-disabled", String(ticked.size < 2));
      if (focus) options[current]?.focus();
    };
    const toggle = () => {
      if (ticked.has(current)) ticked.delete(current);
      else ticked.add(current);
      show();
    };

    list.addEventListener("keydown", (event) => {
      if (current < 0 || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey) return;
      const go = (i) => {
        if (i >= 0 && i < options.length && i !== current) {
          current = i;
          show();
        }
      };
      switch (event.key) {
        case "ArrowUp": go(current - 1); break;
        case "ArrowDown": go(current + 1); break;
        case "Home": go(0); break;
        case "End": go(options.length - 1); break;
        case " ": toggle(); break;
        case "Enter": ok.click(); break;
        default: return;
      }
      event.preventDefault();
    });

    d.dialog.addEventListener("close", () => resolve(answer));
    show(false);
    d.open();
  });
}

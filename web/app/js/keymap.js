// The page's single key table and its one document-level key handler, in
// the spirit of CLAUDE.md invariant 16: a key is written down once, here,
// and nowhere else. Menus and the F1 help list (task 2.5) are built from
// this table; no other module adds a keydown listener for a command.
//
// Code registers what a command DOES with bind(id, handler); the table says
// which keys trigger it and where. A table row with no handler bound is
// inert (its key is left to the browser), so a row can be added before the
// feature behind it.
//
// Browser rules from Phase 0 spike 2 (docs/rsbv_spike_findings.md):
// * Never bind Escape for anything essential: NVDA uses it to leave focus
//   mode, so the page may never see it. Every dialog has a Close button.
// * Pause was never received. F10 and Alt alone are left to the browser,
//   hence the Menu button.
// * Shift+F10 reaches the page in both browsers; the ContextMenu key only
//   in Chrome. Bind both where a context menu is wanted.
//
// Key names: modifiers in the fixed order Ctrl, Alt, Shift, Meta, joined by
// "+", then the key, e.g. "Ctrl+Alt+Left". Letters and digits are named by
// physical position (KeyboardEvent.code), as spike 2 tested them, so Z X C V
// B N stay the bottom row on any layout.
//
// The table between the KEYMAP markers must stay strict JSON (double
// quotes, no trailing commas, no comments): tests/web read it with
// json.loads to check it against the desktop's keys (task 2.7).
//
// Row fields:
//   id             what bind() names
//   keys           every key that triggers it
//   scope          where it applies (see SCOPES)
//   label          the command's name, for menus and help
//   desktopAction  the desktop MenuBuilder Actions field with the same
//                  command, or null when the desktop has no menu action
//   difference     why the web key differs from the desktop's, or null

// prettier-ignore
export const KEYMAP = /* KEYMAP-BEGIN */ [
  {"id": "focus.next", "keys": ["Tab"], "scope": "cycle", "label": "Next region", "desktopAction": null, "difference": null},
  {"id": "focus.previous", "keys": ["Shift+Tab"], "scope": "cycle", "label": "Previous region", "desktopAction": null, "difference": null},
  {"id": "focus.region1", "keys": ["Z"], "scope": "global", "label": "Score information", "desktopAction": "move_to_metadata", "difference": null},
  {"id": "focus.region2", "keys": ["X"], "scope": "global", "label": "Parts", "desktopAction": "move_to_parts", "difference": null},
  {"id": "focus.region3", "keys": ["C"], "scope": "global", "label": "Notes", "desktopAction": "move_to_notes", "difference": null},
  {"id": "focus.region4", "keys": ["V"], "scope": "global", "label": "Attributes", "desktopAction": "move_to_attributes", "difference": null},
  {"id": "focus.region5", "keys": ["B"], "scope": "global", "label": "Performance information", "desktopAction": "move_to_performance", "difference": null},
  {"id": "focus.region6", "keys": ["N"], "scope": "global", "label": "Status", "desktopAction": null, "difference": "Region 6 is the desktop status bar, which the desktop reaches with F6"},
  {"id": "list.previous", "keys": ["Up"], "scope": "list", "label": "Previous row", "desktopAction": null, "difference": null},
  {"id": "list.next", "keys": ["Down"], "scope": "list", "label": "Next row", "desktopAction": null, "difference": null},
  {"id": "list.top", "keys": ["Home"], "scope": "list", "label": "First row", "desktopAction": null, "difference": null},
  {"id": "list.bottom", "keys": ["End"], "scope": "list", "label": "Last row", "desktopAction": null, "difference": null},
  {"id": "nav.left", "keys": ["Left"], "scope": "region3", "label": "Previous note", "desktopAction": null, "difference": null},
  {"id": "nav.right", "keys": ["Right"], "scope": "region3", "label": "Next note", "desktopAction": null, "difference": null},
  {"id": "nav.barLeft", "keys": ["Ctrl+Left"], "scope": "global", "label": "Previous bar", "desktopAction": "previous_bar", "difference": null},
  {"id": "nav.barRight", "keys": ["Ctrl+Right"], "scope": "global", "label": "Next bar", "desktopAction": "next_bar", "difference": null},
  {"id": "nav.first", "keys": ["Ctrl+Home"], "scope": "global", "label": "First note", "desktopAction": "first_measure", "difference": null},
  {"id": "nav.last", "keys": ["Ctrl+End"], "scope": "global", "label": "Last note", "desktopAction": "last_measure", "difference": null},
  {"id": "nav.jumpPrevious", "keys": ["Ctrl+Alt+Left"], "scope": "global", "label": "Previous jump point", "desktopAction": "previous_jump_point", "difference": null},
  {"id": "nav.jumpNext", "keys": ["Ctrl+Alt+Right"], "scope": "global", "label": "Next jump point", "desktopAction": "next_jump_point", "difference": null},
  {"id": "nav.sectionPrevious", "keys": ["Left"], "scope": "region1", "label": "Previous section", "desktopAction": null, "difference": "The desktop steps sections with its Region 1 tab bar or Ctrl+Shift+Tab; browsers keep Ctrl+Tab for their own tabs"},
  {"id": "nav.sectionNext", "keys": ["Right"], "scope": "region1", "label": "Next section", "desktopAction": null, "difference": "The desktop steps sections with its Region 1 tab bar or Ctrl+Tab; browsers keep Ctrl+Tab for their own tabs"},
  {"id": "notes.selectAll", "keys": ["Ctrl+A"], "scope": "region3", "label": "Select all notes", "desktopAction": "select_all", "difference": null},
  {"id": "attributes.speak", "keys": ["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5", "Ctrl+6", "Ctrl+7", "Ctrl+8", "Ctrl+9"], "scope": "global", "label": "Speak attribute by number", "desktopAction": null, "difference": null}
] /* KEYMAP-END */;

// Most specific first: a region's own row beats a row for any list, which
// beats the region cycle, which beats a global row.
export const SCOPES = ["region1", "region2", "region3", "region4", "region5", "region6", "list", "cycle", "global"];

const handlers = new Map();
let context = () => ({ region: null, inCycle: false, isList: false });

/** Register what command `id` does. The handler receives (event, key) and
 * returns false when it declines this press (the key then goes on to a less
 * specific row, and finally to the browser). */
export function bind(id, handler) {
  if (!KEYMAP.some((row) => row.id === id)) throw new Error(`keymap: no command ${id}`);
  handlers.set(id, handler);
}

/** Rows whose command is implemented, for menus and help. */
export function boundCommands() {
  return KEYMAP.filter((row) => handlers.has(row.id));
}

/** The spoken form of a key, "Control Alt Left Arrow". */
export function spokenKey(key) {
  const words = { Ctrl: "Control", Left: "Left Arrow", Right: "Right Arrow", Up: "Up Arrow", Down: "Down Arrow", ContextMenu: "Applications key" };
  return key.split("+").map((part) => words[part] || part).join(" ");
}

/** focus.js tells the dispatcher where focus is: {region: 1-6 or null,
 * inCycle, isList}. */
export function setContextProvider(provider) {
  context = provider;
}

export function keyName(event) {
  const code = event.code;
  if (/^Key[A-Z]$/.test(code)) return code.slice(3);
  if (/^Digit\d$/.test(code)) return code.slice(5);
  if (code.startsWith("Arrow")) return code.slice(5);
  if (code === "NumpadEnter") return "Enter";
  if (/^(Control|Shift|Alt|Meta|OS)/.test(code)) return null;
  return code || event.key || null;
}

export function combo(event) {
  const name = keyName(event);
  if (name === null) return null;
  const mods = [];
  if (event.ctrlKey) mods.push("Ctrl");
  if (event.altKey) mods.push("Alt");
  if (event.shiftKey) mods.push("Shift");
  if (event.metaKey) mods.push("Meta");
  return [...mods, name].join("+");
}

function isEditable(element) {
  if (!element) return false;
  if (element.isContentEditable) return true;
  const tag = element.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  return !["button", "checkbox", "radio", "file", "submit", "reset"].includes(element.type);
}

function scopeApplies(scope, where) {
  if (scope === "global") return true;
  if (scope === "cycle") return where.inCycle;
  if (scope === "list") return where.isList;
  return where.region !== null && scope === `region${where.region}`;
}

const rank = (scope) => SCOPES.indexOf(scope);

function onKeyDown(event) {
  if (event.isComposing) return;
  const key = combo(event);
  if (key === null || key === "Escape") return;
  const target = event.target;
  // Typing in a field, and anything inside an open dialog, belongs to the
  // browser and the dialog's own controls. Bare letters must not jump
  // regions while someone types a bar number.
  if (isEditable(target) || target?.closest?.("dialog[open]")) return;
  const where = context();
  const rows = KEYMAP
    .filter((row) => row.keys.includes(key) && handlers.has(row.id) && scopeApplies(row.scope, where))
    .sort((a, b) => rank(a.scope) - rank(b.scope));
  for (const row of rows) {
    if (handlers.get(row.id)(event, key) !== false) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
  }
}

// Capture phase: the table decides before any element sees the key.
document.addEventListener("keydown", onKeyDown, true);

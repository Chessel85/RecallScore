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
  {"id": "list.extendPrevious", "keys": ["Shift+Up"], "scope": "region3", "label": "Extend selection up", "desktopAction": null, "difference": null},
  {"id": "list.extendNext", "keys": ["Shift+Down"], "scope": "region3", "label": "Extend selection down", "desktopAction": null, "difference": null},
  {"id": "list.extendTop", "keys": ["Shift+Home"], "scope": "region3", "label": "Extend selection to first row", "desktopAction": null, "difference": null},
  {"id": "list.extendBottom", "keys": ["Shift+End"], "scope": "region3", "label": "Extend selection to last row", "desktopAction": null, "difference": null},
  {"id": "tree.expand", "keys": ["Right"], "scope": "region2", "label": "Expand part or step in", "desktopAction": null, "difference": null},
  {"id": "tree.collapse", "keys": ["Left"], "scope": "region2", "label": "Collapse part or step out", "desktopAction": null, "difference": null},
  {"id": "region2.mute", "keys": ["F8"], "scope": "region2", "label": "Mute or unmute row", "desktopAction": "mute", "difference": null},
  {"id": "region2.solo", "keys": ["F9"], "scope": "region2", "label": "Solo or unsolo row", "desktopAction": "solo", "difference": null},
  {"id": "region2.unmuteAll", "keys": ["Alt+F8"], "scope": "region2", "label": "Unmute all", "desktopAction": "unmute_all", "difference": null},
  {"id": "region2.unsoloAll", "keys": ["Alt+F9"], "scope": "region2", "label": "Unsolo all", "desktopAction": "unsolo_all", "difference": null},
  {"id": "goto.bar", "keys": ["Ctrl+G"], "scope": "global", "label": "Go to bar", "desktopAction": "goto_measure", "difference": null},
  {"id": "digits.type", "keys": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], "scope": "global", "label": "Type a bar number", "desktopAction": null, "difference": null},
  {"id": "digits.commit", "keys": ["Enter"], "scope": "global", "label": "Go to the typed bar", "desktopAction": "commit_digits", "difference": null},
  {"id": "digits.clear", "keys": ["Backspace"], "scope": "global", "label": "Cancel the typed bar number", "desktopAction": null, "difference": "The desktop cancels with Escape, which the web never binds"},
  {"id": "options.barLineIndicator", "keys": ["Ctrl+B"], "scope": "global", "label": "Bar line indicator on or off", "desktopAction": "bar_line_indicator", "difference": null},
  {"id": "options.metronome", "keys": ["Ctrl+M"], "scope": "global", "label": "Metronome on or off", "desktopAction": "metronome", "difference": null},
  {"id": "options.positionAnnouncer", "keys": ["Ctrl+P"], "scope": "global", "label": "Position announcer on or off", "desktopAction": "position_announcer", "difference": null},
  {"id": "options.performanceIndicator", "keys": ["Ctrl+C"], "scope": "global", "label": "Cycle performance indicator", "desktopAction": "performance_indicator_cycle", "difference": null},
  {"id": "performance.toggleCategory", "keys": ["Alt+N"], "scope": "region5", "label": "Add or remove this marking category in the note list", "desktopAction": null, "difference": "The desktop uses Control N, which browsers keep for a new window"},
  {"id": "performance.categoryMenu", "keys": ["Shift+F10", "ContextMenu"], "scope": "region5", "label": "Note list menu for this marking", "desktopAction": null, "difference": null},
  {"id": "play.toggle", "keys": ["Space"], "scope": "global", "label": "Play or stop", "desktopAction": "play_stop", "difference": null},
  {"id": "play.pause", "keys": ["Ctrl+Space"], "scope": "global", "label": "Pause", "desktopAction": "pause_resume", "difference": null},
  {"id": "play.metronome", "keys": ["Ctrl+Alt+Space"], "scope": "global", "label": "Play metronome", "desktopAction": "play_metronome", "difference": null},
  {"id": "play.settings", "keys": ["Ctrl+Alt+P"], "scope": "global", "label": "Play settings", "desktopAction": "play_settings", "difference": "The desktop uses Control Shift P, which Firefox keeps for a private window"},
  {"id": "play.mode", "keys": ["Ctrl+L"], "scope": "global", "label": "Cycle play mode", "desktopAction": "play_mode_cycle", "difference": null},
  {"id": "play.leadIn", "keys": ["Ctrl+I"], "scope": "global", "label": "Lead-in on or off", "desktopAction": "lead_in_toggle", "difference": null},
  {"id": "play.loopRepeat", "keys": ["Ctrl+R"], "scope": "global", "label": "Cycle loop repeat handling", "desktopAction": "loop_repeat_mode", "difference": null},
  {"id": "play.loopLonger", "keys": ["Alt+PageUp"], "scope": "global", "label": "Loop one bar longer", "desktopAction": null, "difference": null},
  {"id": "play.loopShorter", "keys": ["Alt+PageDown"], "scope": "global", "label": "Loop one bar shorter", "desktopAction": null, "difference": null},
  {"id": "digits.loopLength", "keys": ["Ctrl+Enter"], "scope": "global", "label": "Set the typed number as the loop length", "desktopAction": null, "difference": null},
  {"id": "tempo.faster", "keys": ["F"], "scope": "global", "label": "Tempo faster", "desktopAction": null, "difference": null},
  {"id": "tempo.slower", "keys": ["S"], "scope": "global", "label": "Tempo slower", "desktopAction": null, "difference": null},
  {"id": "tempo.reset", "keys": ["D"], "scope": "global", "label": "Score tempo", "desktopAction": null, "difference": null},
  {"id": "notes.audition", "keys": ["Shift+Space"], "scope": "global", "label": "Sound the selected notes again", "desktopAction": null, "difference": null},
  {"id": "help.keys", "keys": ["F1"], "scope": "global", "label": "Keyboard help", "desktopAction": null, "difference": null},
  {"id": "attributes.scopeMenu", "keys": ["Shift+F10", "ContextMenu"], "scope": "region4", "label": "Add or remove this attribute in the note list", "desktopAction": null, "difference": null},
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

/** Run command `id` as if its first key was pressed (the Menu button).
 * Returns what the handler returned. */
export function runCommand(id) {
  const row = KEYMAP.find((r) => r.id === id);
  const handler = handlers.get(id);
  if (!row || !handler) return false;
  return handler(null, row.keys[0]);
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
  // Typing in a field, and anything inside an open dialog or the Menu,
  // belongs to the browser and that widget's own keys. Bare letters must
  // not jump regions while someone types a bar number.
  if (isEditable(target) || target?.closest?.("dialog[open], [role='menu']")) return;
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

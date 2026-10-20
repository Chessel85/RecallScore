// The Menu button's menu: a real ARIA menu shaped like the desktop menu
// bar. The top level lists the desktop's menus (File, Edit, Parts,
// Navigation, Options, Help); Right, Enter or Space opens one as a submenu.
//
// Keys inside the menu belong to it, not to keymap.js (which ignores any
// key whose target is inside a [role=menu], as it does for dialogs):
// * Up/Down move and wrap, Home/End go to the ends, a letter goes to the
//   next item starting with it.
// * Right, Enter or Space open a submenu; Enter or Space run a command.
// * Left closes a submenu, and at the top level closes the menu. Escape
//   does the same where the browser delivers it (NVDA may keep it, which
//   is why Left must work).
// * Tab and Shift+Tab close the menu onto the Menu button.
//
// Running a command closes the menu, puts focus on the region that menu's
// commands act on (Parts: Region 2, Edit and Navigation: Region 3; File and
// Help: the Menu button), then runs the command, so its result is heard
// where it lands: a mute on its Region 2 row, a move on the new note. The
// desktop returns focus to where it was before the menu bar, but here the
// Menu button is always reached through Region 1 or 6, so "where it was"
// would never be the region the command is about.
//
// Items come from the key table: a command appears only once it is bound,
// with its label and the key it really has. A command the bridge says is
// disabled right now (web_api.disabled_commands, as the desktop greys out
// its action) is aria-disabled: still reachable, read as unavailable, and
// does nothing when chosen.
//
// An item the caller's `checked()` names is a menuitemcheckbox (a key-driven
// toggle) or menuitemradio (an extra marked `radio`, one of a set of
// choices) with aria-checked, as the desktop's checkable actions are, so
// the state is heard while arrowing through the menu. Read on every open.
//
// showContextMenu() opens a one-level menu of the same kind beside a
// region (Region 4's scope menu, Shift+F10), with the same keys. Closing
// it without a choice hands focus back to the caller.

import { KEYMAP, boundCommands, runCommand } from "./keymap.js";
import { keysText } from "./dialogs.js";

// The desktop's menu order (widgets/menu_builder.py). An entry is a
// keymap id, "-" for a separator, or "extra:<name>" for a command that is
// not key-driven, supplied by the caller.
const MENUS = [
  { title: "File", items: ["extra:open"] },
  { title: "Edit", region: 3, items: ["notes.selectAll"] },
  { title: "Parts", region: 2, items: ["region2.solo", "region2.mute", "-", "region2.unsoloAll", "region2.unmuteAll"] },
  {
    title: "Navigation",
    region: 3,
    items: [
      "nav.first", "nav.last", "nav.barLeft", "nav.barRight", "-",
      "goto.bar", "-",
      "nav.jumpPrevious", "nav.jumpNext", "-",
      "focus.region1", "focus.region2", "focus.region3", "focus.region4", "focus.region5", "focus.region6",
    ],
  },
  {
    title: "Playback",
    region: 3,
    items: [
      "play.toggle", "play.pause", "play.metronome", "play.settings", "play.mode", "play.leadIn", "play.loopRepeat", "-",
      "tempo.faster", "tempo.slower", "tempo.reset", "-",
      "play.loopLonger", "play.loopShorter", "-",
      "play.mixer",
    ],
  },
  {
    title: "Options",
    region: 3,
    // The desktop's Terminology and Performance Indicator submenus are
    // flattened into their choices: this menu has two levels only.
    items: [
      "extra:ukTerms", "extra:usTerms", "-",
      "options.barLineIndicator", "-",
      "extra:indicatorOff", "extra:indicatorExceptPlaying", "extra:indicatorAlways", "options.performanceIndicator", "-",
      "options.engravingDetails", "options.metronome", "options.positionAnnouncer",
    ],
  },
  { title: "Help", items: ["extra:userGuide", "help.keys"] },
];

let button = null;
let extras = {};
let restoreFocus = () => {};
let disabledIds = () => [];
let checkedIds = () => ({});
let root = null; // the open top-level menu element, or null
let backTo = () => {}; // where closing without a choice puts focus
let fromButton = false; // root is the Menu button's menu
let serial = 0;

/** `menuButton` opens the menu. `extra` maps a name to {label, run}.
 * `returnFocus(region)` focuses that region, or the Menu button for none.
 * `disabled()` lists the keymap ids to show as unavailable. `checked()`
 * maps a MENUS entry (a keymap id, or "extra:<name>") to true or false for
 * each item that has a checked state now; an entry it leaves out is a
 * plain item. */
export function initMenu({ menuButton, extra = {}, returnFocus, disabled, checked }) {
  button = menuButton;
  extras = extra;
  restoreFocus = returnFocus;
  disabledIds = disabled ?? disabledIds;
  checkedIds = checked ?? checkedIds;
  button.setAttribute("aria-haspopup", "menu");
  button.setAttribute("aria-expanded", "false");
  button.addEventListener("click", () => (root ? closeAll(true) : open()));
}

/** The menus with only bound commands, separators tidied, empty menus dropped. */
function liveMenus() {
  const bound = new Set(boundCommands().map((row) => row.id));
  const disabled = new Set(disabledIds());
  const checked = checkedIds() ?? {};
  const menus = [];
  for (const menu of MENUS) {
    const items = [];
    for (const entry of menu.items) {
      const state = typeof checked[entry] === "boolean" ? checked[entry] : null;
      if (entry === "-") {
        if (items.length && items[items.length - 1] !== "-") items.push("-");
      } else if (entry.startsWith("extra:")) {
        const extra = extras[entry.slice(6)];
        if (extra) {
          const role = state === null ? "menuitem" : extra.radio ? "menuitemradio" : "menuitemcheckbox";
          items.push({ label: extra.label, keys: null, run: extra.run, role, checked: state });
        }
      } else if (bound.has(entry)) {
        const row = KEYMAP.find((r) => r.id === entry);
        items.push({
          label: row.label,
          keys: keysText(row.keys),
          run: () => runCommand(row.id),
          disabled: disabled.has(entry),
          role: state === null ? "menuitem" : "menuitemcheckbox",
          checked: state,
        });
      }
    }
    if (items[items.length - 1] === "-") items.pop();
    if (items.length) menus.push({ title: menu.title, region: menu.region ?? null, items });
  }
  return menus;
}

function makeMenuElement(labelledBy, label = null) {
  const el = document.createElement("div");
  el.setAttribute("role", "menu");
  if (label !== null) el.setAttribute("aria-label", label);
  else el.setAttribute("aria-labelledby", labelledBy);
  el.className = "popup-menu";
  el.addEventListener("keydown", onKeyDown);
  return el;
}

/** `checked` is null for a plain item, else the state of a checkbox or
 * radio item (`role`). The tick is drawn only: aria-checked says it. */
function makeItem(text, keys, role = "menuitem", checked = null) {
  serial += 1;
  const item = document.createElement("div");
  item.setAttribute("role", role);
  item.id = `menu-item-${serial}`;
  item.tabIndex = -1;
  const name = document.createElement("span");
  if (checked !== null) {
    item.setAttribute("aria-checked", String(checked));
    const tick = document.createElement("span");
    tick.className = "menu-check";
    tick.setAttribute("aria-hidden", "true");
    tick.textContent = checked ? "✓" : "";
    name.append(tick);
  }
  name.append(text);
  item.append(name);
  if (keys) {
    const key = document.createElement("span");
    key.className = "menu-key";
    key.textContent = keys;
    item.append(key);
    item.setAttribute("aria-label", `${text}, ${keys}`);
  }
  return item;
}

/** The ARIA menu pattern's wrapper: every item, and a submenu beside its
 * parent item, sits in a role="none" element, never directly in the menu. */
function wrap(...children) {
  const el = document.createElement("div");
  el.setAttribute("role", "none");
  el.append(...children);
  return el;
}

/** M from anywhere in the page: open the Menu button's menu. Closing it
 * without a choice calls `back` (where the key was pressed). */
export function openMenu(back) {
  open(back);
}

function open(back = () => button.focus()) {
  closeAll(false);
  const menus = liveMenus();
  root = makeMenuElement(button.id);
  for (const menu of menus) {
    const parent = makeItem(menu.title, null);
    parent.setAttribute("aria-haspopup", "menu");
    parent.setAttribute("aria-expanded", "false");
    const sub = makeMenuElement(parent.id);
    sub.hidden = true;
    for (const entry of menu.items) {
      if (entry === "-") {
        const sep = document.createElement("div");
        sep.setAttribute("role", "separator");
        sub.append(sep);
        continue;
      }
      const item = makeItem(entry.label, entry.keys, entry.role, entry.checked);
      if (entry.disabled) item.setAttribute("aria-disabled", "true");
      else item.addEventListener("click", () => activate(entry.run, menu.region));
      sub.append(wrap(item));
    }
    parent.addEventListener("click", () => openSub(parent));
    // The submenu is the item's sibling so its items are not part of the
    // parent item's accessible name.
    root.append(wrap(parent, sub));
  }
  fromButton = true;
  backTo = back;
  closeOnFocusLoss();
  button.after(root);
  button.setAttribute("aria-expanded", "true");
  items(root)[0]?.focus();
}

/** A one-level menu placed after `anchor` and named `label`. `entries` are
 * {label, run}. Choosing one closes the menu and calls its run(), which
 * then owns the focus; closing without a choice (Left, Escape, Tab) calls
 * `back`. Focus goes to the first item. */
export function showContextMenu({ anchor, label, entries, back }) {
  closeAll(false);
  root = makeMenuElement(null, label);
  for (const entry of entries) {
    const item = makeItem(entry.label, null);
    item.addEventListener("click", () => {
      closeAll(false);
      entry.run();
    });
    root.append(wrap(item));
  }
  fromButton = false;
  backTo = back;
  closeOnFocusLoss();
  anchor.after(root);
  items(root)[0]?.focus();
}

function closeOnFocusLoss() {
  root.addEventListener("focusout", (event) => {
    if (root && !root.contains(event.relatedTarget) && !(fromButton && event.relatedTarget === button)) {
      closeAll(false);
    }
  });
}

/** The menu's own items, not those of a submenu inside it. */
function items(menu) {
  return [...menu.children].map((el) => el.firstElementChild).filter((el) => el?.getAttribute("role")?.startsWith("menuitem"));
}

function submenuOf(parent) {
  return parent.nextElementSibling;
}

function openSub(parent) {
  closeSubs();
  const sub = submenuOf(parent);
  parent.setAttribute("aria-expanded", "true");
  sub.hidden = false;
  items(sub)[0]?.focus();
}

function closeSubs() {
  if (!root) return;
  for (const parent of items(root)) {
    parent.setAttribute("aria-expanded", "false");
    submenuOf(parent).hidden = true;
  }
}

/** Close the whole menu; `toButton` puts focus back where the menu came
 * from (the Menu button, or a context menu's `back`). */
function closeAll(toButton) {
  if (!root) return;
  const el = root;
  root = null;
  el.remove();
  if (fromButton) button.setAttribute("aria-expanded", "false");
  if (toButton) backTo();
}

function activate(run, region) {
  closeAll(false);
  restoreFocus(region);
  setTimeout(run, 0);
}

function onKeyDown(event) {
  const menu = event.currentTarget;
  // A submenu sits inside the root's element tree; let only the innermost
  // menu handle the key.
  event.stopPropagation();
  const list = items(menu);
  const index = list.indexOf(document.activeElement);
  const current = list[index];
  const isTop = menu === root;
  const go = (i) => list[(i + list.length) % list.length]?.focus();
  let handled = true;
  switch (event.key) {
    case "ArrowDown": go(index + 1); break;
    case "ArrowUp": go(index - 1); break;
    case "Home": go(0); break;
    case "End": go(list.length - 1); break;
    case "ArrowRight":
      if (isTop && current?.hasAttribute("aria-haspopup")) openSub(current);
      break;
    case "ArrowLeft":
    case "Escape":
      if (isTop) closeAll(true);
      else {
        const parent = menu.previousElementSibling;
        closeSubs();
        parent.focus();
      }
      break;
    case "Enter":
    case " ":
      current?.click();
      break;
    case "Tab":
      closeAll(true);
      break;
    default:
      handled = typeAhead(list, index, event);
  }
  if (handled) event.preventDefault();
}

function typeAhead(list, index, event) {
  if (event.key.length !== 1 || event.ctrlKey || event.altKey || event.metaKey) return false;
  const letter = event.key.toLowerCase();
  for (let step = 1; step <= list.length; step += 1) {
    const item = list[(index + step) % list.length];
    // The name's own text, after any tick.
    const name = item.firstElementChild?.lastChild?.textContent ?? item.textContent;
    if (name.trim().toLowerCase().startsWith(letter)) {
      item.focus();
      break;
    }
  }
  return true;
}

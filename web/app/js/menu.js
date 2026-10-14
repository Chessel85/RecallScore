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
// with its label and the key it really has.

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
  { title: "Playback", region: 3, items: ["play.toggle", "play.pause"] },
  { title: "Options", region: 3, items: ["options.barLineIndicator", "options.metronome", "options.positionAnnouncer"] },
  { title: "Help", items: ["help.keys"] },
];

let button = null;
let extras = {};
let restoreFocus = () => {};
let root = null; // the open top-level menu element, or null
let serial = 0;

/** `menuButton` opens the menu. `extra` maps a name to {label, run}.
 * `returnFocus(region)` focuses that region, or the Menu button for none. */
export function initMenu({ menuButton, extra = {}, returnFocus }) {
  button = menuButton;
  extras = extra;
  restoreFocus = returnFocus;
  button.setAttribute("aria-haspopup", "menu");
  button.setAttribute("aria-expanded", "false");
  button.addEventListener("click", () => (root ? closeAll(true) : open()));
}

/** The menus with only bound commands, separators tidied, empty menus dropped. */
function liveMenus() {
  const bound = new Set(boundCommands().map((row) => row.id));
  const menus = [];
  for (const menu of MENUS) {
    const items = [];
    for (const entry of menu.items) {
      if (entry === "-") {
        if (items.length && items[items.length - 1] !== "-") items.push("-");
      } else if (entry.startsWith("extra:")) {
        const extra = extras[entry.slice(6)];
        if (extra) items.push({ label: extra.label, keys: null, run: extra.run });
      } else if (bound.has(entry)) {
        const row = KEYMAP.find((r) => r.id === entry);
        items.push({ label: row.label, keys: keysText(row.keys), run: () => runCommand(row.id) });
      }
    }
    if (items[items.length - 1] === "-") items.pop();
    if (items.length) menus.push({ title: menu.title, region: menu.region ?? null, items });
  }
  return menus;
}

function makeMenuElement(labelledBy) {
  const el = document.createElement("div");
  el.setAttribute("role", "menu");
  el.setAttribute("aria-labelledby", labelledBy);
  el.className = "popup-menu";
  el.addEventListener("keydown", onKeyDown);
  return el;
}

function makeItem(text, keys) {
  serial += 1;
  const item = document.createElement("div");
  item.setAttribute("role", "menuitem");
  item.id = `menu-item-${serial}`;
  item.tabIndex = -1;
  const name = document.createElement("span");
  name.textContent = text;
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

function open() {
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
      const item = makeItem(entry.label, entry.keys);
      item.addEventListener("click", () => activate(entry.run, menu.region));
      sub.append(wrap(item));
    }
    parent.addEventListener("click", () => openSub(parent));
    // The submenu is the item's sibling so its items are not part of the
    // parent item's accessible name.
    root.append(wrap(parent, sub));
  }
  root.addEventListener("focusout", (event) => {
    if (root && !root.contains(event.relatedTarget) && event.relatedTarget !== button) closeAll(false);
  });
  button.after(root);
  button.setAttribute("aria-expanded", "true");
  items(root)[0]?.focus();
}

/** The menu's own items, not those of a submenu inside it. */
function items(menu) {
  return [...menu.children].map((el) => el.firstElementChild).filter((el) => el?.getAttribute("role") === "menuitem");
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

/** Close the whole menu; `toButton` puts focus on the Menu button. */
function closeAll(toButton) {
  if (!root) return;
  const el = root;
  root = null;
  el.remove();
  button.setAttribute("aria-expanded", "false");
  if (toButton) button.focus();
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
      if (isTop && current) openSub(current);
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
    if (item.textContent.trim().toLowerCase().startsWith(letter)) {
      item.focus();
      break;
    }
  }
  return true;
}

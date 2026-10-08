// The single owner of the region focus cycle, as RegionFocusCycleMixin is on
// the desktop (CLAUDE.md invariant 7): Menu button, then Regions 1 to 6, and
// round again. Tab and Shift+Tab inside the cycle, and the direct jumps
// Z X C V B N, all come here through keymap.js; nothing else moves focus
// between regions.
//
// Tab is taken over only while focus is in the cycle, so it wraps from
// Region 6 to the Menu button instead of leaving for the browser's toolbar.
// Anywhere else on the page (the file picker, a dialog) Tab is the
// browser's own.
//
// Jumping to a region never moves the score cursor, as on the desktop.

import { bind, setContextProvider } from "./keymap.js";

const LIST_REGIONS = new Set([1, 3, 4, 5, 6]); // Region 2 is a tree

let members = []; // [menuButton, region1, ..., region6]

/** `regions` are the six focusable region widgets, Region 1 first. */
export function initFocus({ menuButton, regions }) {
  if (regions.length !== 6) throw new Error("focus: expected six regions");
  members = [menuButton, ...regions];
  for (const el of members) {
    if (!el.hasAttribute("tabindex")) el.tabIndex = 0;
  }
  bind("focus.next", () => cycle(1));
  bind("focus.previous", () => cycle(-1));
  for (let n = 1; n <= 6; n += 1) bind(`focus.region${n}`, () => focusRegion(n));
  setContextProvider(() => {
    const region = focusedRegion();
    return {
      region: region > 0 ? region : null,
      inCycle: region !== null,
      isList: LIST_REGIONS.has(region),
    };
  });
}

/** 0 for the Menu button, 1 to 6 for a region, null outside the cycle. */
export function focusedRegion() {
  const active = document.activeElement;
  const index = members.findIndex((el) => el === active || el.contains(active));
  return index === -1 ? null : index;
}

export function regionElement(n) {
  return members[n];
}

export function focusRegion(n) {
  members[n]?.focus();
}

export function focusMenuButton() {
  members[0]?.focus();
}

/** Tab (+1) and Shift+Tab (-1). From outside the cycle this declines, so
 * the browser's own Tab order applies. */
export function cycle(delta) {
  const current = focusedRegion();
  if (current === null) return false;
  members[(current + delta + members.length) % members.length].focus();
  return true;
}

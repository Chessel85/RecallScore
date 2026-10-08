// Region rendering: just enough for tasks 2.1 and 2.2 to be tried with a
// screen reader. Task 2.3 owns this module and adds Region 3 multi-select
// (Shift+arrows), Region 2 expand and collapse, and Region 4 keeping focus
// on the same attribute across a rebuild.
//
// Accessibility shape (set here, keep it in 2.3):
// * Each region is one focusable widget with aria-activedescendant; the
//   rows are role="option" (role="treeitem" in Region 2) and never take
//   focus themselves.
// * Every render gives the rows fresh ids. Pointing aria-activedescendant
//   at a new id is what makes the screen reader read the row, even when the
//   text is the same as before (two C's in a row must both be heard).
// * Regions 1, 4, 5 and 6 are not re-rendered when their text is
//   unchanged, so focus and the reading position survive a move that does
//   not affect them (RegionPresenter.refresh_region_5's diff). Region 3 is
//   re-rendered on every move: the cursor moved, so the note is read.

const regions = new Map(); // n -> {el, rows, current, selection}
let serial = 0;

export function initRegions(elements) {
  elements.forEach((el, i) => {
    regions.set(i + 1, { el, rows: [], current: 0, selection: [] });
  });
  for (const n of regions.keys()) renderPlaceholder(n, "No score loaded");
}

function renderPlaceholder(n, text) {
  render(n, [{ text }], { force: true });
}

/** Draw `rows` ({text}) into region n. Region 3 takes `selection` (row
 * indices); the current row is 0 after a render unless `keepCurrent`. */
export function render(n, rows, { selection = null, force = false, keepCurrent = false } = {}) {
  const region = regions.get(n);
  const texts = rows.map((row) => row.text);
  const same = texts.length === region.rows.length && texts.every((t, i) => t === region.rows[i].text);
  if (same && !force && n !== 3) return;
  serial += 1;
  const isTree = n === 2;
  region.rows = rows;
  region.current = keepCurrent ? Math.min(region.current, rows.length - 1) : 0;
  region.selection = selection ?? [region.current];
  const children = rows.map((row, i) => {
    const option = document.createElement("div");
    option.id = `r${n}-${serial}-${i}`;
    option.setAttribute("role", isTree ? "treeitem" : "option");
    option.textContent = row.text;
    if (isTree) {
      option.setAttribute("aria-level", "1");
      if (row.children?.length) option.setAttribute("aria-expanded", "false");
    }
    return option;
  });
  region.el.replaceChildren(...children);
  showCurrent(n);
}

function showCurrent(n) {
  const region = regions.get(n);
  const options = region.el.children;
  const selected = new Set(n === 3 ? region.selection : [region.current]);
  for (let i = 0; i < options.length; i += 1) {
    options[i].setAttribute("aria-selected", selected.has(i) ? "true" : "false");
  }
  const current = options[region.current];
  if (current) region.el.setAttribute("aria-activedescendant", current.id);
  else region.el.removeAttribute("aria-activedescendant");
}

export function currentRow(n) {
  return regions.get(n).current;
}

export function rowAt(n, index) {
  return regions.get(n).rows[index];
}

/** Region 3's selected row indices. */
export function selection() {
  return [...regions.get(3).selection];
}

/** Up/Down/Home/End within region n. Returns false at an end (nothing
 * moved). Moving in Region 3 selects just the new row, as the desktop's
 * list does for a plain arrow. */
export function moveRow(n, where) {
  const region = regions.get(n);
  const last = region.rows.length - 1;
  const target = { previous: region.current - 1, next: region.current + 1, top: 0, bottom: last }[where];
  if (target < 0 || target > last || target === region.current) return false;
  region.current = target;
  if (n === 3) region.selection = [target];
  showCurrent(n);
  return true;
}

/** Ctrl+A in Region 3: select every row, current row unchanged. */
export function selectAll() {
  const region = regions.get(3);
  region.selection = region.rows.map((_, i) => i);
  showCurrent(3);
}

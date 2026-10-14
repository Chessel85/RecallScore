// Region rendering: the six regions as listboxes (Region 2 a tree) from the
// rows the bridge returns.
//
// Accessibility shape (set in 2.1, keep it):
// * Rows take real focus (roving tabindex): the current row has tabindex 0
//   and the focus, every other row -1, and the region element itself is not
//   focusable. aria-activedescendant was tried first and NVDA stayed silent
//   with it in both Firefox and Chrome; real focus is read everywhere.
// * Every render gives the rows fresh ids and fresh elements, so a repeated
//   row (two C's in a row) is still read as a new focus.
// * Regions 1, 4, 5 and 6 are not re-rendered when their text is
//   unchanged, so focus and the reading position survive a move that does
//   not affect them (RegionPresenter.refresh_region_5's diff). Region 3 is
//   re-rendered on every move: the cursor moved, so the note is read.
// * Region 3 is multi-select: a plain move selects just that row, Shift
//   extends from an anchor, Ctrl+A selects all. Region 4 follows it, and
//   keeps the current row on the same attribute (by `key`) across a rebuild
//   (Region4ListWidget.refresh_list).
// * Region 2 is a tree. Expand state is the page's and is never saved, as
//   on the desktop; every node starts collapsed, and collapsing a node
//   forgets its descendants' expand state (Region2ListWidget._collapse_item).

const regions = new Map(); // n -> {el, rows, current, selection, anchor, nodes}
const expanded = new Set(); // Region 2 node ids that are open
let serial = 0;

export function initRegions(elements) {
  elements.forEach((el, i) => {
    regions.set(i + 1, { el, rows: [], current: 0, selection: [], anchor: 0, nodes: [] });
  });
  for (const n of regions.keys()) render(n, [{ text: "No score loaded" }], { force: true });
}

/** Region 2's nested nodes -> the flat list of rows currently showing. */
function visibleTree(nodes, level = 1, parentId = null, out = []) {
  nodes.forEach((node, index) => {
    const children = node.children ?? [];
    out.push({
      ...node,
      level,
      parentId,
      position: index + 1,
      siblings: nodes.length,
      hasChildren: children.length > 0,
    });
    if (children.length && expanded.has(node.id)) visibleTree(children, level + 1, node.id, out);
  });
  return out;
}

/** Draw `rows` into region n.
 * Region 3 takes `selection` (row indices). The current row goes back to 0
 * unless `keepCurrent`, which keeps the same Region 4 attribute (by `key`)
 * or the same Region 2 node (by `id`) when it is still there. `reset`
 * (Region 2) forgets the expand state, for a newly loaded score. */
export function render(n, rows, { selection = null, force = false, keepCurrent = false, reset = false, inPlace = false } = {}) {
  const region = regions.get(n);
  const isTree = n === 2;
  if (inPlace && !isTree && rows.length === region.rows.length && region.el.children.length === rows.length) {
    // Playback following: change the text where it differs and leave the
    // current row and the focus alone, so a moving position line does not
    // pull the reader back to the top of the region.
    rows.forEach((row, i) => {
      if (row.text !== region.rows[i].text) region.el.children[i].textContent = row.text;
    });
    region.rows = rows;
    return;
  }
  if (isTree && reset) expanded.clear();
  const flat = isTree ? visibleTree(rows) : rows;
  const texts = flat.map((row) => row.text);
  const same = texts.length === region.rows.length && texts.every((t, i) => t === region.rows[i].text);
  if (same && !force && n !== 3 && !isTree) return;
  serial += 1;
  const hadFocus = region.el.contains(document.activeElement);
  const previous = region.rows[region.current];
  if (isTree) region.nodes = rows;
  region.rows = flat;
  region.current = keepCurrent ? keptIndex(n, previous, region.current, flat) : 0;
  region.selection = selection ?? [region.current];
  region.anchor = region.current;
  const children = flat.map((row, i) => {
    const option = document.createElement("div");
    option.id = `r${n}-${serial}-${i}`;
    option.setAttribute("role", isTree ? "treeitem" : "option");
    option.textContent = row.text;
    if (isTree) setTreeAttributes(option, row);
    return option;
  });
  region.el.replaceChildren(...children);
  showCurrent(n, hadFocus);
}

function keptIndex(n, previous, oldIndex, rows) {
  const field = n === 4 ? "key" : n === 2 ? "id" : null;
  if (field && previous?.[field] !== undefined) {
    const found = rows.findIndex((row) => row[field] === previous[field]);
    if (found !== -1) return found;
  }
  return Math.min(oldIndex, Math.max(rows.length - 1, 0));
}

function setTreeAttributes(option, row) {
  option.setAttribute("aria-level", String(row.level ?? 1));
  if (row.siblings) {
    option.setAttribute("aria-posinset", String(row.position));
    option.setAttribute("aria-setsize", String(row.siblings));
  }
  if (row.hasChildren) option.setAttribute("aria-expanded", expanded.has(row.id) ? "true" : "false");
}

/** Mark the current row (and Region 3's selection) and, when the region has
 * the focus, move the focus onto the current row. */
function showCurrent(n, focus = regions.get(n).el.contains(document.activeElement)) {
  const region = regions.get(n);
  const options = region.el.children;
  const selected = new Set(n === 3 ? region.selection : [region.current]);
  for (let i = 0; i < options.length; i += 1) {
    options[i].setAttribute("aria-selected", selected.has(i) ? "true" : "false");
    options[i].tabIndex = i === region.current ? 0 : -1;
  }
  const current = options[region.current];
  if (focus) current?.focus();
  current?.scrollIntoView?.({ block: "nearest" });
}

/** Put the focus on region n's current row (the region cycle and Z X C V B N). */
export function focusCurrent(n) {
  const region = regions.get(n);
  const current = region.el.children[region.current];
  if (current) current.focus();
  else {
    region.el.tabIndex = -1;
    region.el.focus();
  }
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

function targetRow(region, where) {
  const last = region.rows.length - 1;
  const target = { previous: region.current - 1, next: region.current + 1, top: 0, bottom: last }[where];
  return target < 0 || target > last || target === region.current ? null : target;
}

/** Up/Down/Home/End within region n. Returns false at an end (nothing
 * moved). Moving in Region 3 selects just the new row, as the desktop's
 * list does for a plain arrow. */
export function moveRow(n, where) {
  const region = regions.get(n);
  const target = targetRow(region, where);
  if (target === null) {
    // At an end Region 3 still collapses a chord's selection to the current
    // row, as the desktop's TimelineListWidget does for Up/Down.
    if (n === 3 && region.selection.length > 1) {
      region.selection = [region.current];
      region.anchor = region.current;
      showCurrent(n);
    }
    return false;
  }
  region.current = target;
  if (n === 3) {
    region.selection = [target];
    region.anchor = target;
  }
  showCurrent(n);
  return true;
}

/** Shift+Up/Down/Home/End in Region 3: extend the selection from the anchor
 * to the new current row. False at an end. */
export function extendSelection(where) {
  const region = regions.get(3);
  const target = targetRow(region, where);
  if (target === null) return false;
  region.current = target;
  const [from, to] = region.anchor <= target ? [region.anchor, target] : [target, region.anchor];
  region.selection = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  showCurrent(3);
  return true;
}

/** Ctrl+A in Region 3: select every row, current row unchanged. */
export function selectAll() {
  const region = regions.get(3);
  region.selection = region.rows.map((_, i) => i);
  showCurrent(3);
}

// --- Region 2 expand and collapse ---------------------------------------------

/** Right: open a closed node, or step into an open node's first child.
 * False when there is nothing to do (a leaf). */
export function treeExpand() {
  const region = regions.get(2);
  const row = region.rows[region.current];
  if (!row?.hasChildren) return false;
  if (!expanded.has(row.id)) {
    expanded.add(row.id);
    redrawTree(row.id);
  } else {
    region.current += 1;
    showCurrent(2);
  }
  return true;
}

/** Left: close an open node (forgetting its descendants' open state), else
 * step to the parent. False at a closed top-level node. */
export function treeCollapse() {
  const region = regions.get(2);
  const row = region.rows[region.current];
  if (!row) return false;
  if (row.hasChildren && expanded.has(row.id)) {
    forget(row);
    redrawTree(row.id);
    return true;
  }
  if (row.parentId === null || row.parentId === undefined) return false;
  region.current = region.rows.findIndex((r) => r.id === row.parentId);
  showCurrent(2);
  return true;
}

function forget(row) {
  expanded.delete(row.id);
  for (const child of row.children ?? []) forget(child);
}

function redrawTree(currentId) {
  const region = regions.get(2);
  render(2, region.nodes, { force: true });
  region.current = Math.max(region.rows.findIndex((r) => r.id === currentId), 0);
  region.selection = [region.current];
  showCurrent(2);
}

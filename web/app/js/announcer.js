// Minimal announcer for loading progress. Task 2.1 replaces this module with
// the real one (ariaNotify, assertive/polite); keep the announce() signature.
// Every message goes through a queue, one per gap, so none is dropped or
// merged, and two alternating live regions make repeated text re-announce.

const GAP_MS = 400;
const queue = [];
let draining = false;
let flip = false;

export function announce(text) {
  queue.push(text);
  if (!draining) drain();
}

function drain() {
  const next = queue.shift();
  if (next === undefined) {
    draining = false;
    return;
  }
  draining = true;
  flip = !flip;
  const [now, previous] = flip ? ["a", "b"] : ["b", "a"];
  document.getElementById(`live-${previous}`).textContent = "";
  document.getElementById(`live-${now}`).textContent = next;
  setTimeout(drain, GAP_MS);
}

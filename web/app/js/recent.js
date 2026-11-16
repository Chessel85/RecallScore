// File > Recent Files. The desktop keeps paths; a browser cannot reopen a
// path, so the score's bytes are kept in IndexedDB instead (localStorage is
// too small). Most recent first, no duplicates (same bytes = same entry), capped
// at the desktop's MAX_RECENT_FILES (persistence/app_settings.py).
//
// The list is held in memory so the Menu can read it synchronously on every
// open. Every IndexedDB call is wrapped: a private window or blocked site data
// just means the list is empty or lasts for the session.

const MAX_RECENT_FILES = 20;
const DB_NAME = "recallscore-recent";
const STORE = "files";

let entries = []; // {id, name, saved (ms), bytes}, most recent first

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function done(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = tx.onabort = () => reject(tx.error);
  });
}

/** Read the stored list into memory. Call once at start-up. */
export async function initRecent() {
  try {
    const db = await openDb();
    const request = db.transaction(STORE).objectStore(STORE).getAll();
    entries = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    db.close();
    entries.sort((a, b) => b.saved - a.saved);
  } catch {
    entries = [];
  }
}

/** The list for the Menu: [{id, name}], most recent first. */
export function recentFiles() {
  return entries.map(({ id, name }) => ({ id, name }));
}

/** The stored {name, bytes} for `id`, or null. */
export function recentFile(id) {
  const entry = entries.find((e) => e.id === id);
  return entry ? { name: entry.name, bytes: entry.bytes } : null;
}

/** Record a successfully opened score as the most recent. `key` is the
 * score's SHA-256, or null where the browser has no digest (name + size). */
export async function addRecent(key, name, bytes) {
  const id = key ?? `${name}:${bytes.length}`;
  const entry = { id, name, saved: Date.now(), bytes };
  entries = [entry, ...entries.filter((e) => e.id !== id)];
  const dropped = entries.slice(MAX_RECENT_FILES);
  entries = entries.slice(0, MAX_RECENT_FILES);
  try {
    const db = await openDb();
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    store.put(entry);
    for (const old of dropped) store.delete(old.id);
    await done(tx);
    db.close();
  } catch {
    // kept for this session only
  }
}

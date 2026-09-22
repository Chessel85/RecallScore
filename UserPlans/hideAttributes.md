# Attribute management: hide attributes from Region 4, per-part ordering

Status: implemented 2026-09-22, same day as the revised plan below. First
draft 2026-09-22 from a pasted feature request; revised same day after the
user's comments settled several open questions and substantially changed the
scope (ordering moves from a single global list to one list **per part**,
and hiding gets a two-tier visible/hidden-for-part/hidden-for-all model
instead of a single flag). Read `docs/architecture.md`'s "The attribute
system (Ref 15 AC4)" section and `docs/dialog_widget_patterns.md` before
touching this area again.

Landed as designed below, with two small deviations discovered during
implementation (both noted inline where relevant):
- `attribute_keys_for_part`/`attribute_elevated_for_part`/
  `attribute_elevated_parts` read the universe of voices/parts from the
  notes themselves (and, for elevation, also from any explicit
  `voice_display_attributes` entry) rather than from `parts_info` alone -
  `parts_info` is only populated by `MusicXMLReader.load()` and stays empty
  for a directly-built `MusicData(file_path=...)` (the same reasoning
  `MusicData._all_voice_tuples` already documents), so relying on it alone
  would silently do nothing for that construction path.
- `MusicData.apply_config`'s `known_part_ids` (used to filter
  `attribute_order_by_part`/`hidden_attributes_by_part` and, as before, the
  part name/program overrides) is now the union of `parts_info` and the
  part ids the notes themselves carry, for the same reason.

The "Hide for All" blocked-message wording (the one open item below) was not
re-confirmed with the user before landing - implemented as proposed.

**This is now a bigger change than the original request implied** - moving
`attribute_order` from one global list to a per-part `Dict[str, List[str]]`
touches every reader of `attribute_order` (Region 3 rendering, Region 4
rendering, `.rsc` persistence, and the fingerprint harness's baseline) even
though the user only asked to add hiding. Flagged as a scale note, not a
reason to push back - the user was explicit ("Attribute ordering is always
per part. never score, stave or voice level").

## Vocabulary check (CLAUDE.md Terminology section)

Nothing here touches PART vs INSTRUMENT - this is entirely about the
attribute display system (Ref 15 AC4), not instruments/GM programs. "Part" in
this document always means the MusicXML/Region 2 structural part, per that
convention.

## What exists today (unchanged by this revision - still the baseline)

Two independent mechanisms already control what Region 3/4 show, both in
`models/note_renderer.py`, both fields on `MusicData`:

- **WHICH** - `voice_display_attributes: Dict[(part_id, staff, voice), Set[str]]`.
  Default is `{"step"}` only. `set_display_attribute`/
  `set_display_attribute_for_voice` fan a toggle out across a
  `"voice"/"stave"/"part"/"score"` scope (`voice_tuples_for_scope`). An
  attribute present in some voice's set is what this document calls
  **elevated** - it renders in Region 3 ("the note list") for that voice.
  **This only gates Region 3, and this plan does not change it** - the four
  fan-out scopes on Region 4's context menu and the dialog's existing
  Add/&Remove button stay exactly as they are.
- **ORDER** - today, `attribute_order: List[str]`, a single global (per-score)
  ordering both Region 3 and Region 4 iterate. **This plan replaces it** with
  one list per part - see below.

**Region 4 (`NoteRenderer.region_4_rows`) is NOT gated by
`voice_display_attributes` at all** - it shows every `attribute_key` in
`attribute_order` that the selected note(s) actually have a value for,
regardless of the WHICH toggle. That split is deliberate and stays: Region 4
is the exhaustive detail view, Region 3 is the curated one. Hiding is a new,
third mechanism that gates Region 4 (and, per the user's answer below, Find)
the way `voice_display_attributes` gates Region 3.

The Reorder Attributes dialog (`widgets/attribute_order_dialog.py`) is a
working-copy Ok/Cancel dialog (`docs/dialog_widget_patterns.md`) for Up/Down
only - moves are staged locally and committed via `ordered_keys()` on Accept
(`AttributeController.apply_order`). The existing Add/&Remove button is
different: it applies immediately, not staged, because it's a different
feature (WHICH) to the ordering (ORDER). **Hide and Hide for All follow the
same immediate-apply pattern as Add/Remove**, for the same reason.

## The user's decisions (this revision)

Quoting/paraphrasing the comments added to the previous draft, organised by
topic:

### Scope: the dialog is part-specific; ordering is part-specific

> The Hide and reorder dialogue needs to be part specific. Not stave or
> voice specific. So it displays data for the current part the user is on or
> in. ... Attribute ordering is always per part. never score, stave or voice
> level.

Whatever Region 2 node (voice/staff/part) was current when the dialog opens,
the dialog resolves it to that node's **part** and always lists/reorders at
part granularity. This replaces the current per-node-type behaviour
(`_filter_scopes_for_node_level`, `voice_tuples_for_node`) *for the
list/order/hide half only* - the Add/Remove button's own scope fan-out
(voice/stave/part/score) is untouched, since the user's comments only talk
about hide/order, not WHICH.

### Hide has two tiers, mutually exclusive with "visible"

> An extra button labelled "Hide for all" with accelerator alt+A sets the
> status to hide the attribute for all parts in the score. So an attribute
> can either be visible, hidden for a part, or hidden for the entire score.
> They are mutually exclusive. If an attribute for one part is hidden when
> it is hidden for all from a different part, the hidden for all supersedes.
> When a row for an attribute that is hidden for all is selected, the 'hide
> for just this part' button is disabled. The hide and hide for all buttons
> are actually toggles. Keep the accelerators the same but can the button
> label be changed to unhide and unhide for all as appropriate?

Three states per `(attribute_key, part)`: visible / hidden-for-this-part /
hidden-for-all. "Hidden for all" is score-wide and takes precedence over any
part's own hidden-for-part state wherever the two might otherwise disagree.
Both Hide buttons are toggles (label flips to Unhide/"Unhide for All" when
already in that state, accelerator letter unchanged since H and A both
survive the Un- prefix).

### Elevation blocks hiding, but the buttons stay enabled and explain why

> In the attribute list of the dialogue, prefix an attribute that is
> elevated to the note list with an asterisk. Do this in the main region 4
> list as well. It doesn't matter if it is elevated to voice, stave, part or
> score, if it is elevated at all, prefix with an asterisk. An elevated
> attribute cannot be hidden. It must be un-elevated first. Keep the hide and
> hide for all buttons enabled. If the user presses hide, display a message
> saying it must be un-elevated though need a better word than this. If a
> user tries to hide for all an attribute, that is in use, display a message
> which lists all the parts it is elevated in.

This **replaces** the button-disabling approach the first draft proposed
(disable Hide when elevated). Instead: the buttons are always enabled (when a
row is selected); pressing one that's currently blocked by elevation pops a
message and makes no change, rather than being unreachable.

### Find respects hiding, per-part

> Yes, a hidden attribute cannot be found. Respects the currently selected
> part.

### Naming

> Change to 'Attribute management'.

Replaces this plan's earlier `Hide and Reorder Attributes...` recommendation
(and the request's own `Attribute hide and reorder`) with **Attribute
Management...** everywhere the dialog/menu item is named (menu text, window
title). Ellipsis kept, matching the "opens a dialog" convention every other
Options-menu action here uses (`Reorder Attributes...`, `Goto Measure...`,
`Find...`).

## Revised design

### State model

For a given `attribute_key`:

- **Elevated** (existing concept, unchanged) - present in
  `voice_display_attributes` for at least one voice anywhere in the score.
  Drives Region 3 rendering, unaffected by this feature.
- **Hidden for all** - in a new score-wide set. Blocks Region 4/Find
  everywhere, for every part, regardless of any part's own hidden-for-part
  state.
- **Hidden for `<part_id>`** - in a new per-part set. Blocks Region 4/Find
  for that part only.
- **Visible** (default) - none of the above.

"Elevated" and "hidden" (either tier) are meant to be mutually exclusive by
construction: hiding is refused (with a message) while the attribute is
elevated anywhere the relevant check looks (see below), and nothing in this
design un-elevates an attribute as a side effect of hiding it - the user must
remove it from Region 3 via the existing Add/Remove button or Region 4's
context menu first. The blocked-hide message's wording is settled below
(Decisions from the previous round item 1) - it doesn't use the word
"elevated" at all, sidestepping the "need a better word" ask.

### Data model (`models/music_data.py` / `models/note_renderer.py`)

Replace the single `attribute_order: List[str]` field with:

- `attribute_order_by_part: Dict[str, List[str]]` - one full copy of
  `DISPLAY_ATTRIBUTE_ORDER`-shaped ordering per `part_id`, lazily seeded
  (first access for a part with no entry yet gets a fresh
  `list(DISPLAY_ATTRIBUTE_ORDER)`) rather than pre-populated for every part
  up front, so a score gaining a part later (unlikely, but keeps the
  invariant simple) doesn't need special-casing.
- `hidden_attributes_by_part: Dict[str, Set[str]]` - empty sets by default.
- `hidden_attributes_for_all: Set[str]` - empty by default.

New/changed `NoteRenderer` methods:

- `attribute_order_for_part(part_id) -> List[str]` - the live, mutable list
  for that part (seeding it on first access, per above).
- `move_attribute_order_for_part(part_id, attribute_key, up, within=None)` -
  same pop/insert-relative-to-neighbour logic `move_attribute_order` already
  has, just against `attribute_order_for_part(part_id)`. `within` still
  means what it means today (the dialog's own present-in-this-part subset) -
  the mechanism that lets a filtered list move by exactly one displayed row
  while carrying along not-currently-present keys between them is unchanged,
  only the list it operates on is now per-part instead of the one global
  list intersected with a voice-scope subset.
- `set_attribute_order_within_part(part_id, new_order, within)` - the OK-time
  bulk commit, same shape as today's `set_attribute_order_within` against the
  per-part list.
- `attribute_keys_for_part(part_id) -> List[str]` - every attribute key
  present on any note in that part, in that part's own order. Reuses
  `voice_tuples_for_scope(part_id, staff=0, voice=0, scope="part")` to get
  every voice tuple under the part (the `staff`/`voice` args are ignored by
  that method for the `"part"`/`"score"` branches already, so this needs no
  new scanning code) and then filters `_real_timeline_slices` the same way
  `attribute_keys_for_voices` does today.
- `is_attribute_hidden(attribute_key, part_id) -> bool` - `attribute_key in
  hidden_attributes_for_all or attribute_key in
  hidden_attributes_by_part.get(part_id, set())`. This is what
  `region_4_rows` and Find call.
- `attribute_elevated_for_part(attribute_key, part_id) -> bool` - True if
  elevated for at least one voice under that part, at any of the four
  add/remove scopes (voice/stave/part/score all just mean "some voice in
  this part has it on" from this check's point of view - "regardless of the
  level" per the user). Drives the dialog's own asterisk (the dialog is
  itself part-scoped, so this part-local check is what it uses - not the
  whole-score one below) and the "Hide" (per-part) block.
- `attribute_elevated_parts(attribute_key) -> List[str]` - every `part_id`
  in the whole score where the key is elevated for at least one voice.
  Empty means not elevated anywhere. Used **only** for the "Hide for All"
  block's message, which must name every part standing in its way - not for
  the dialog's row asterisk (see above; confirmed by the user, who reasoned
  the dialog is part-scoped so its own asterisk should be too).
- `set_attribute_hidden_for_part(attribute_key, part_id, hidden: bool) ->
  bool` - returns `False` (refused, no state change) if `hidden=True` and
  either (a) `attribute_elevated_for_part(attribute_key, part_id)` is True,
  or (b) `attribute_key` is already in `hidden_attributes_for_all`. The
  model enforces (b) itself rather than leaning on the dialog's button
  disablement to prevent it - user: "good coding should mean it isn't
  permitted in the data model," on top of the dialog disabling the button
  for the same case as a UI-level convenience/announcement, not as the only
  guard.
- `set_attribute_hidden_for_all(attribute_key, hidden: bool) -> bool` -
  returns `False` (refused) if `hidden=True` and
  `attribute_elevated_parts(attribute_key)` is non-empty. On success with
  `hidden=True`, also clears that key from every part's
  `hidden_attributes_by_part` entry (now redundant/stale - avoids a
  surprising leftover per-part hide reappearing if the score-wide hide is
  later undone).
- `MusicData` gets one-line delegators for all of the above (invariant 4).

### Region 3 rendering

`format_note_for_region_3` (`models/note_renderer.py:133`) changes its one
line `order = data.attribute_order` to
`order = self.attribute_order_for_part(note.part_id)`. No other change -
hiding never reaches Region 3, since a hidden attribute is (by construction)
never elevated, so it was never rendering there anyway.

### Region 4 rendering

`region_4_rows` (`models/note_renderer.py:228`) changes:

- The iteration `for attribute_key in data.attribute_order:` becomes `for
  attribute_key in self.attribute_order_for_part(n.part_id):` - each note's
  row-group uses its own part's order. (A multi-part chord selection - e.g.
  selecting several Region 3 rows that happen to span two parts sounding at
  once - already iterates notes one at a time here, `is_chord` just decides
  the `"note N "` prefix, so this falls out naturally: each note's block of
  rows follows its own part's order, which is a reasonable reading of "per
  part" but worth confirming, see Open Questions.)
- Add a skip: `if self.is_attribute_hidden(attribute_key, n.part_id):
  continue`.
- **No asterisk in Region 4.** The user changed their mind on this: "the
  user can see by looking at notes in the note list if it is elevated or
  not," so Region 4 needs no elevation marker of its own. Only the dialog
  (below) gets the asterisk.

### Reorder/Hide dialog (`widgets/attribute_order_dialog.py`)

The dialog keeps taking the Region 2 `node` it's opened against (still
needed for Add/Remove's existing scope fan-out), but everything new resolves
`part_id = node.part_id` once and uses that throughout:

- **List contents**: `attribute_keys_for_part(part_id)`, not
  `attribute_keys_for_voices(voice_tuples_for_node(node))`. Every row's label
  gets a leading `"*"` when `attribute_elevated_for_part(key, part_id)` is
  True (see Data model above - **part-local** elevation, confirmed by the
  user: "because the dialogue is scoped to the part, it must prefix with an
  asterisk regardless of the level" - "the level" being which of the four
  add/remove scopes, not which part).
- **Up/Down**: operate on `attribute_order_for_part(part_id)` via
  `move_attribute_order_for_part`; OK commits via
  `set_attribute_order_within_part`.
- **Add/&Remove...** (unchanged): still built from `node` (not collapsed to
  `part_id`), so a voice/stave-level selection still offers voice/stave/
  part/score fan-out exactly as today. `AttributeController.order_menu_actions`
  needs no change.
- **New `&Hide`/`&Unhide` button** (Alt+H): toggles
  `hidden_attributes_by_part[part_id]` for the current row's key via
  `set_attribute_hidden_for_part`. If refused for being elevated in this
  part, `notify_user("error", ...)` (the existing modal pattern in
  `widgets/user_notification.py`) with the user's confirmed wording:
  **`"<label> can't be hidden while it's shown in the note list."`**
  Disabled outright (not just refused-with-message) when the row is already
  hidden-for-all - user: "the hide button is disabled when the selected
  attribute is hidden for all" - this is the one case that stays a
  disablement rather than a message, since it's redundant rather than an
  error; the elevated case stays enabled-with-message per the user's
  earlier instruction.
- **New `Hide for &All`/`Unhide for &All` button** (Alt+A): toggles
  `hidden_attributes_for_all` via `set_attribute_hidden_for_all`. If refused
  (elevated in any part), `notify_user("error", ...)` naming every part from
  `attribute_elevated_parts(key)`. The user confirmed the per-part message's
  exact wording but not this one - proposed, as the natural extension of the
  same sentence: **`"<label> can't be hidden for the whole score while it's
  shown in the note list for: Piano, Guitar."`** (comma-joined part names,
  in whatever order `attribute_elevated_parts` returns them - worth a quick
  confirmation when this is built, not blocking). Always enabled per the
  user's explicit instruction.
- Both new buttons: `setAutoDefault(False)` like every other button in this
  dialog (`docs/dialog_widget_patterns.md`'s autoDefault trap - load-bearing,
  confirmed live-tested for this exact dialog already).
- **Immediate-apply, not staged** - same as Add/Remove, for the same reason
  (a different feature to F2's ordering). After a successful toggle, update
  just that row's text in place: the asterisk (elevation) and a hidden-state
  suffix are independent flags on the same row, both confirmed:
  - Hidden for this part only: `"<label> (hidden)"`.
  - Hidden for all: `"<label> (hidden for all)"`.

  **Hidden rows stay listed in the dialog itself** at both tiers -
  confirmed by the user ("must stay visible in the dialogue because...
  cannot unhide it otherwise") - only Region 4 loses the row.
- Button row gets both new buttons appended after `add_remove_button`;
  `_update_button_state` extended for the Hide-for-all-disables-Hide-for-part
  case described above (everything else about the two new buttons stays
  enabled whenever a row is selected, i.e. same condition as
  `add_remove_button`).
- No change to `showEvent`/focus handling.

### Controller (`controllers/attribute_controller.py`)

- `order_pairs_for_node(node)` → resolve `part_id = node.part_id` and call
  new `order_pairs_for_part(part_id)`, which also computes the asterisk flag
  per row (returning a richer row type than today's bare `(key, label)` pair
  - e.g. `(key, label, elevated: bool)` - or leaving asterisk-prefixing to
  the controller so the dialog stays purely a view, consistent with how
  `order_pairs_for_node` already pre-translates labels via
  `attribute_label`).
- `scope_node()` unchanged (still resolves from Region 2's current node);
  the part-collapse happens where the dialog/controller consumes it, not
  here, since Add/Remove still needs the original node.
- New `toggle_hidden_for_part(dialog, node, attribute_key)` and
  `toggle_hidden_for_all(dialog, attribute_key)` - mutate the model via the
  new `set_attribute_hidden_for_part`/`set_attribute_hidden_for_all`,
  `notify_user` on refusal, refresh Region 4 (check whether a Region-4-only
  refresh call already exists distinct from `refresh_region_3_labels`, or
  whether hiding needs both refreshed since Region 3's order also moved to
  per-part), and update the dialog's own current row in place.
- `apply_order(node, new_order)` → resolve `part_id` and call
  `set_attribute_order_within_part`.

### Find (`models/find_target.py`, `models/find_index.py`)

**Confirmed: per-occurrence.** An occurrence's availability as a Find target
is filtered through `is_attribute_hidden(attribute_key, note.part_id)` for
**the note the occurrence actually belongs to** - hidden-for-all excludes it
everywhere; hidden-for-just-part-A excludes only that part's occurrences,
leaving the same attribute findable in a part where it isn't hidden. This
mirrors the existing Ref 7 active-parts/staves filtering
(`FindIndex._is_marking_visible`) in shape - both filter occurrence-by-
occurrence against that occurrence's own part, not against whatever's
currently selected in Region 2.

### Naming

- `widgets/menu_builder.py` (~line 823) - `a.attribute_order` action text
  `"Reorder Attributes..."` → `"Attribute Management..."`. Keeps
  `Ctrl+Shift+A` (not asked to change). Variable name `attribute_order` left
  alone (internal identifier).
- `AttributeOrderDialog.__init__`'s `setWindowTitle("Reorder Attributes")` →
  `setWindowTitle("Attribute Management")`.
- Sweep `docs/architecture.md`'s references to "Options > Reorder
  Attributes..." as part of this change (architecture doc, not user-facing).
  **Leave `docs/user_guide.md`/`.html` alone unless separately asked** -
  `feedback_no_unprompted_user_guide_edits` - flag the sweep as a follow-up
  ask rather than doing it unprompted.
- Class name `AttributeOrderDialog`/module `attribute_order_dialog.py` -
  recommend leaving as-is; purely internal, renaming is a large diff for no
  behavioural gain unless the user wants it for consistency with the new
  user-facing name.

### Persistence / migration (`models/score_config_data.py`,
`MusicData.export_config`/`apply_config`)

`ScoreConfig` gains:

- `attribute_order_by_part: Dict[str, List[str]]`
- `hidden_attributes_by_part: Dict[str, Set[str]]`
- `hidden_attributes_for_all: Set[str]`

`export_config()` writes all three (plus everything already there);
`apply_config()` restores them, filtering each part's list against
`DISPLAY_ATTRIBUTE_ORDER`'s known keys the same way today's single
`attribute_order` restore does, so a stale key from an edited/older `.rsc`
can't crash rendering.

**Migration for existing saves**: an old `.rsc` has a flat `attribute_order`
and no `attribute_order_by_part`. On load, if the new field is empty/absent
and the old one is present, seed *every part currently in the score* with a
copy of the old flat order as that part's starting per-part order - the
closest available approximation of "what the user already had", since there
is no way to know whether the old flat order was really customised with one
particular part in mind. **No need to also keep writing the old flat field
for downgrade safety** - confirmed by the user ("no need to worry about old
versions, I'm still pretty much the only person using this application").
New saves write only the new fields; the old field is read once, on the way
in, purely to carry the user's own existing customisation forward, never
written again.

### Tests

- `tests/models/test_music_data.py` / a new `test_attribute_management.py` -
  new coverage for:
  - Per-part order round-trips through `export_config`/`apply_config`/
    `.rsc`, including the old-flat-field migration path.
  - `hidden_attributes_by_part`/`hidden_attributes_for_all` round-trip.
  - Region 4 omits a key hidden-for-part only for that part's own notes, and
    hidden-for-all for every part's notes.
  - Region 3 for a note in one part is unaffected by another part's order
    changes (proves the per-part split is real, not accidentally shared).
  - `set_attribute_hidden_for_part`/`_for_all` both refuse (return `False`,
    no state change) when elevated, and `attribute_elevated_parts` reports
    every part correctly for the "Hide for All" message.
  - Un-hiding at either tier restores the Region 4 row.
- `tests/test_main_window_attributes.py` - dialog-level:
  - Asterisk prefix appears for a row elevated anywhere *within the dialog's
    own part* (voice/stave/part/score scope all count), and does **not**
    appear for a row elevated only in a *different* part - the part-local
    rule, not the whole-score one.
  - Pressing Hide while elevated pops the confirmed message
    (`"<label> can't be hidden while it's shown in the note list."`,
    monkeypatched `notify_user`) and makes no model change.
  - Pressing Hide for All while elevated anywhere in the score pops a
    message naming every elevated part and makes no model change.
  - Hide (per-part) button is disabled outright when the row is already
    hidden-for-all (not just refused-with-message).
  - `set_attribute_hidden_for_part` itself (not just the dialog) refuses a
    hide when the key is already in `hidden_attributes_for_all`, proving the
    guard lives in the model, not only the UI.
  - Button labels flip Hide↔Unhide / "Hide for All"↔"Unhide for All"
    correctly, accelerators unchanged.
  - Row suffix reads `"(hidden)"` for a hidden-for-part row and
    `"(hidden for all)"` for a hidden-for-all row - the two are
    distinguishable, not just both "hidden".
- `models/find_target.py`/`find_index.py` tests - a hidden attribute is
  excluded from Find per-occurrence: hidden-for-all excludes every
  occurrence; hidden-for-just-one-part excludes only that part's
  occurrences, leaving the same attribute findable via an occurrence
  belonging to a different, non-hidden part.
- `tests/manual/model_fingerprint.py` - **this is the acceptance gate for
  this change**, not just "tests pass" (CLAUDE.md's own instruction for any
  `models/`/`parsers/` change meant to be behaviour-preserving on existing
  data): every score's Region 3/4 fingerprint must match the pre-change
  baseline for a fresh `MusicData` with nothing hidden and no saved
  per-part customisation, since replacing the single global order with
  per-part lists that all start as identical copies of
  `DISPLAY_ATTRIBUTE_ORDER` should render identically to today until the
  user actually customises one part's order.

## Decisions from the previous round (all resolved)

1. **Blocked-hide message wording (per-part)**: confirmed, exact text -
   `"<label> can't be hidden while it's shown in the note list."`
2. **Hidden rows stay listed in the dialog** (both tiers), so they can be
   found and un-hidden - confirmed.
3. **Find filters per-occurrence** against that occurrence's own owning
   part, not whatever's currently selected in Region 2 - confirmed.
4. **The model itself, not just the dialog's button disablement, refuses a
   per-part hide when the key is already hidden-for-all** - confirmed
   ("good coding should mean it isn't permitted in the data model"); the
   dialog still disables the button too, as a UI-level convenience on top.
5. **The dialog's own asterisk is part-local** (elevated anywhere within
   the dialog's own part, any of the four scopes), not whole-score -
   confirmed, reasoned from the dialog itself being part-scoped.
   **Region 4 gets no asterisk at all** - the user changed their mind on
   this; skip it entirely (see Region 4 rendering above).
6. **No migration-write/downgrade-safety concern** - confirmed, single-user
   application; read the old flat field once on load, never write it again.
7. **Land per-part ordering and hide/hide-for-all together**, one change -
   confirmed ("do both").

## Remaining open items

Only one item from this round is genuinely still open - everything else
above is settled:

1. **"Hide for All" blocked message wording** - the user confirmed the
   per-part message's exact text but wasn't asked for the "Hide for All"
   variant specifically. This plan proposes the natural extension -
   `"<label> can't be hidden for the whole score while it's shown in the
   note list for: Piano, Guitar."` - and a comma-joined part-name list in
   whatever order `attribute_elevated_parts` returns them. Worth a quick
   confirmation when this is actually built, not blocking the rest of the
   plan.
2. **Hidden-for-part vs hidden-for-all row suffix wording in the dialog** -
   confirmed: show different text for the two. `"(hidden)"` for
   hidden-for-this-part, `"(hidden for all)"` for hidden-for-all. Applied in
   the Dialog UI section above.
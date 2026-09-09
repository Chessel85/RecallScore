# models/music_data.py
import bisect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from models import vocabulary
from models.barline_mark import BarlineMark
from models.clef_change_mark import ClefChangeMark
from models.coda_mark import CodaMark
from models.direction_mark import DirectionMark
from models.direction_span import DirectionSpan
from models.ending_span import EndingSpan
from models.measure_style_mark import MeasureStyleMark
from models.event_slice import EventSlice
from models.fine_mark import FineMark
from models.find_index import FindIndex
from models.find_target import FindTarget
from models.hairpin_span import HairpinSpan
from models.key_signatures import key_signature_display_name
from models.mixer_settings import MixerSettings
from models.navigation_jump import NavigationJump
from models.note_data import NoteData
from models.note_renderer import NoteRenderer
from models.override_manager import OverrideManager
from models.parts_structure import PartStructureInfo
from models.performance_region_row import PerformanceRegionRow
from models.performance_rows import PerformanceRows
from models.playback_event_builder import PlaybackEventBuilder
from models.playback_jump_state import PlaybackJumpState
from models.repeat_span import RepeatSpan
from models.score_config_data import ScoreConfig
from models.score_formats import family_for_path
from models.score_section import ScoreSection
from models.section_span import SectionSpan
from models.segno_mark import SegnoMark
from models.strum_pattern import StrumPattern
from models.tempo_change import TempoChange
from models.timeline_navigator import TimelineNavigator
from models.to_coda_mark import ToCodaMark
from models.synthetic_parts import CHORDS_PART_ID, LYRICS_PART_ID


@dataclass
class MusicData:
    score: Optional[Any] = None
    credits: Dict[str, str] = field(default_factory=dict)
    parts_info: List[PartStructureInfo] = field(default_factory=list)
    file_path: str = ""
    tempo_bpm: int = 120

    # A9: tempo_bpm is ALWAYS quarter-note BPM (playback timing).
    # tempo_beat_unit_* are the ratio and label converting it back to the
    # score's own beat unit - a score marked eighth=96 has tempo_bpm=48 and
    # quarter_length=0.5, so 48/0.5 = 96, the number the user actually
    # reads. Anything user-facing (Region 1, status bar, tempo dialog, F/S/D)
    # must go through the display units, never the raw quarter BPM.
    tempo_beat_unit_quarter_length: float = 1.0
    tempo_beat_unit_name: str = "quarter"

    # Ref 12: an ABSOLUTE playback tempo, stored as quarter-note BPM
    # (denominator-independent, robust to score edits). None = "use the
    # score default" (self.tempo_bpm). Never a mutation of tempo_bpm -
    # Region 1 keeps showing the score's own notated marking. Playback is
    # always FLAT: the score's internal rall./accel./section tempo changes
    # are described (Region 5, Performance Report) but not sounded.
    # Persisted per-score (.rsc), unlike the old session-only offset.
    playback_tempo_bpm: Optional[float] = None

    # Ref 12 multi-tempo scope: every tempo marking after the first, sorted
    # by position, from TimelineBuilder. tempo_bpm above stays the OPENING
    # tempo (Region 1's summary); this list is what lets the status bar,
    # dialog and Sequencer use the tempo actually in effect at a position.
    tempo_changes: List[TempoChange] = field(default_factory=list)

    # Pre-parsed ElementTree root from MusicXMLReader, so TimelineBuilder
    # need not re-parse. None when MusicData(file_path=...) is built
    # directly, in which case TimelineBuilder parses the file itself.
    xml_root: Optional[Any] = None

    # Pre-parsed MidiSource from MidiReader (parsers/midi_source.py), the
    # MIDI counterpart of xml_root - same reasoning, same fallback when None.
    midi_source: Optional[Any] = None

    # Pre-parsed GpSource from GpReader (parsers/gp_source.py), the Guitar
    # Pro counterpart of xml_root/midi_source - same reasoning, same
    # fallback when None.
    gp_source: Optional[Any] = None

    # Pre-parsed UgSource from UgReader (parsers/ug_source.py), the
    # Ultimate Guitar counterpart of xml_root/midi_source/gp_source. Unlike
    # those three, there is no fallback re-parse from file_path alone - a UG
    # import's file_path is a synthetic slug with nothing fetchable at it
    # (see UgReader/UgTimelineBuilder), so this must always be provided.
    ug_source: Optional[Any] = None

    timeline_slices: List[EventSlice] = field(default_factory=list)
    active_event_index: int = 0

    # (part_id, staff, voice) tuples currently shown/played (Ref 7).
    # None means unfiltered. Must default to None, NOT an empty set - an
    # empty set means "nothing visible", and callers that never set a filter
    # expect the full note list.
    active_voice_filter: Optional[Set[Tuple[str, int, int]]] = None

    # Ref 15 AC4: which optional attributes each voice shows in Region 3.
    # A voice absent from this dict falls back to DEFAULT_DISPLAY_ATTRIBUTES,
    # NOT an empty set - most voices are never touched by the context menu
    # and must keep showing the plain note name.
    voice_display_attributes: Dict[Tuple[str, int, int], Set[str]] = field(default_factory=dict)

    # F2/Ref 15 AC4: the live, mutable rendering order Region 3/4 both read.
    # Defaults empty rather than to DISPLAY_ATTRIBUTE_ORDER because that
    # constant is defined further down the class body and isn't bound yet
    # here; __post_init__ fills it in, so "empty" never escapes.
    attribute_order: List[str] = field(default_factory=list)

    # Ref 14: gates both whether a beat sounds a click and whether a beat
    # with no note counts as a navigable event at all (_slice_is_navigable,
    # AC4). Off by default per load - MusicData is rebuilt on every load, so
    # nothing needs an explicit reset.
    metronome_enabled: bool = False

    # Ref 28: unlike metronome_enabled, toggling this never touches
    # timeline_slices - AC5 requires the announcer to speak only where an
    # event already exists and never create one, so there is nothing to
    # splice in or out.
    position_announcer_enabled: bool = False

    # Options > Bar Line Indicator (Ctrl+B): a high metronome beep when a
    # plain Left/Right step crosses a bar line. Like position_announcer_
    # enabled, toggling it needs no timeline rebuild. Per-score (saved in
    # the .rsc), off by default per load.
    bar_line_indicator_enabled: bool = False

    # Wishlist #4: per-score volume/pan overrides, live on MusicData like
    # every other per-score setting above - export_config()/apply_config()
    # carry it the same way, so it survives a load/save round trip instead
    # of being read once at load and discarded (which is what happened
    # before this field existed: PlaybackController.attach_score received a
    # mixer only as a local variable, and the next save silently wrote back
    # an empty one).
    mixer: MixerSettings = field(default_factory=MixerSettings)

    # S5: per-part display-name/instrument overrides the user set via
    # widgets/instrument_dialog.py, keyed by part_id. Bookkeeping only -
    # apply_part_overrides() is what actually mutates parts_info/NoteData -
    # kept so export_config() can persist exactly what was overridden
    # rather than every part's current value, same "explicit overrides
    # only" shape as mixer above.
    part_name_overrides: Dict[str, str] = field(default_factory=dict)
    part_program_overrides: Dict[str, int] = field(default_factory=dict)

    # Wishlist #8 follow-up: per-percussion-item playback/name overrides,
    # set via widgets/instrument_dialog.py, same "explicit overrides only"
    # bookkeeping shape as the two above. Keyed by (part_id, the item's
    # ORIGINAL file-declared key - NoteData.percussion_source_key), NOT by
    # its current display name - a name is itself overridable
    # (percussion_item_name_overrides), and keying by name would orphan a
    # sound override the moment the item was renamed.
    percussion_item_overrides: Dict[Tuple[str, int], int] = field(default_factory=dict)
    percussion_item_name_overrides: Dict[Tuple[str, int], str] = field(default_factory=dict)
    # "Apply MusicXML offset for percussion" (Edit > Instruments...) -
    # best-effort auto-correction, cross-referencing each percussion item's
    # OWN declared name against its OWN declared key via
    # models.gm_percussion_map.gm_percussion_key_for_name. Off by default -
    # every other override in this app starts as "nothing changed" and this
    # is no different, even though the file that motivated it (Hit It.mxl)
    # needed it for every one of its percussion instruments. MusicXML-only
    # in effect: a MIDI note's name is already DERIVED from its key
    # (gm_percussion_name), so there is nothing for it to disagree with -
    # see apply_percussion_overrides.
    percussion_auto_correct_enabled: bool = False

    # S6: a single whole-piece key signature override, set via the
    # Instruments & Key dialog. None means "use the file's own key(s)".
    key_signature_override_fifths: Optional[int] = None
    key_signature_override_mode: Optional[str] = None

    # F4/D-6: UK vs US terminology. main_window.py owns the real startup
    # default (OS-locale-detected) and re-applies it after every load, since
    # MusicData is wholly replaced then and this is a session preference,
    # not a per-score one like metronome_enabled.
    uk_terms: bool = False

    # Ref 29: repeat-barline pairs, 1st/2nd endings and hairpins, from
    # TimelineBuilder, same side-channel pattern as tempo_changes above.
    # total_measures is the whole-score bar count for the Performance
    # Report - NOT derived from timeline_slices, which would undercount a
    # trailing all-rest measure.
    repeat_spans: List[RepeatSpan] = field(default_factory=list)
    ending_spans: List[EndingSpan] = field(default_factory=list)
    hairpin_spans: List[HairpinSpan] = field(default_factory=list)
    # P3: <direction>/<direction-type> spans (pedal, octave shift, dashed/
    # bracketed lines) and points (rehearsal, pedal change, D6 catch-all),
    # collected per part (D5). Pedal/octave-shift are Find + Performance
    # Report only - deliberately NO Region 5 row (D15).
    direction_spans: List[DirectionSpan] = field(default_factory=list)
    direction_marks: List[DirectionMark] = field(default_factory=list)
    # P4: <bar-style> points (M6), mid-part <clef> changes (M7),
    # <measure-style> points (M8). MusicXML-only - MIDI/GP/UG stub them
    # empty. Findable, listed in the Performance Report, and shown as a
    # one-shot Region 5 row at their own measure (D15 bars only pedal/
    # octave-shift from Region 5, not these).
    barline_marks: List[BarlineMark] = field(default_factory=list)
    clef_change_marks: List[ClefChangeMark] = field(default_factory=list)
    measure_style_marks: List[MeasureStyleMark] = field(default_factory=list)
    total_measures: int = 0

    # Segno/Coda/D.C./D.S./Fine navigation marks, same side-channel pattern
    # as repeat_spans/ending_spans/hairpin_spans above. MusicXML-only, like
    # every other field on this line - MIDI/GP/UG builders stub these to
    # empty lists (see e.g. parsers/midi_timeline_builder.py). Consumed by
    # next_playback_index (playback/preview repeat-and-jump stepping) and
    # get_performance_region_rows/get_performance_report_lines (display).
    segno_marks: List[SegnoMark] = field(default_factory=list)
    coda_marks: List[CodaMark] = field(default_factory=list)
    to_coda_marks: List[ToCodaMark] = field(default_factory=list)
    fine_marks: List[FineMark] = field(default_factory=list)
    navigation_jumps: List[NavigationJump] = field(default_factory=list)
    # P2: named song sections (Intro/Verse/Chorus/...). Populated by
    # UgTimelineBuilder today; other builders stub it empty. Drives a
    # Region 5 row, a Find target, and Ctrl+Alt+Left/Right section stepping.
    section_spans: List[SectionSpan] = field(default_factory=list)

    # Multi-section MusicXML (UserPlans/MultiSectionScores.md): one file
    # holding several independent pieces back to back. build_sections()
    # yields one ScoreSection per piece, each carrying its own complete,
    # standalone TimelineBuild; set_active_section() swaps which one is
    # live by re-adopting its build. ALWAYS has at least one entry - every
    # non-MusicXML format, and an ordinary single-piece MusicXML file,
    # yields exactly one section with an empty label, so the downstream
    # path is unchanged from before this feature. Not persisted: every
    # load starts on section 0 (feedback_simplicity_over_stateful_features).
    sections: List[ScoreSection] = field(default_factory=list)
    active_section_index: int = 0

    @property
    def is_midi(self) -> bool:
        """True for a score loaded from a Standard MIDI File, as opposed to
        MusicXML - the same format family check __post_init__ uses to pick a
        timeline builder, exposed once here so other call sites (Ref 25/S2's
        Region 2 collapse) don't each repeat it. Extension lists live in
        models/score_formats.py (S4)."""
        return family_for_path(self.file_path) == "midi"

    @property
    def is_gp(self) -> bool:
        """True for a score loaded from a Guitar Pro (.gp) file - the same
        format family check __post_init__ uses to pick a timeline builder."""
        return family_for_path(self.file_path) == "gp"

    @property
    def is_ug(self) -> bool:
        """True for a score imported from Ultimate Guitar - the same
        synthetic-extension check __post_init__ uses to pick a timeline
        builder (see UgReader for where file_path gets its .ug suffix).
        Also drives Region 2's collapse_to_parts, same as is_midi - both
        of UG's synthetic parts (Chords/Lyrics) are flat, nothing useful to
        toggle below the part level."""
        return family_for_path(self.file_path) == "ug"

    @property
    def collapsed_part_ids(self) -> Union[bool, Set[str]]:
        """Region 2's collapse_to_parts argument (widgets/region2_manager.py):
        True to flatten every part (MIDI, a pure Ultimate Guitar import,
        where a real staff/voice concept doesn't exist anywhere in the
        score), or the specific set of part_ids to flatten for a score that
        mixes real notated parts with synthetic ones - a MusicXML file
        carrying its own <harmony>/<lyric> markup keeps its real
        instrument's staff/voice tree intact and flattens only the
        synthetic Chords/Lyrics parts, whose "Chord chart"/"Voice 1" labels
        have nothing real underneath them (reported: showing them as a
        3-level tree read as redundant, made-up navigation - the same
        "chords don't have layers below them" call already made for GP's
        synthetic Chords voice and a pure UG import's Chords/Lyrics parts).

        Region 2 follow-up (wishlist #8): a MIDI percussion part is no
        longer collapsed - unlike every other MIDI part, its "voices" are
        now real, independently mute/soloable rows (one per distinct
        drum/cymbal, via PartStructureInfo.staves_voices - see
        parsers/midi_reader.py), not a fake single always-voice-1 concept
        with nothing to gain from expanding. Every other MIDI part still
        collapses exactly as before."""
        if self.is_ug:
            return True
        if self.is_midi:
            return {p.part_id for p in self.parts_info if not p.is_percussion}
        return {p.part_id for p in self.parts_info if p.part_id in (CHORDS_PART_ID, LYRICS_PART_ID)}

    @property
    def ug_strum_patterns(self) -> List[StrumPattern]:
        """The UG import's parsed strumming patterns (0..3), or []. Consumed
        by the Strumming Patterns dialog (Edit menu). Per-chord strummed
        audition was removed - the pattern is legible in the dialog and,
        with a multi-pattern song, was arbitrary per bar anyway."""
        if self.ug_source is None:
            return []
        return list(self.ug_source.strum_patterns)

    def __post_init__(self):
        # S1 collaborators. Each holds a reference back to this MusicData
        # and owns no state of its own, so they never go stale against the
        # score - and MusicData keeps a delegator for every method they
        # took over, which is what makes the split invisible to callers.
        # Built FIRST: the timeline build below already calls through to
        # one of them (_set_percussion_voice_names).
        self.find_index = FindIndex(self)
        self.overrides = OverrideManager(self)
        self.renderer = NoteRenderer(self)
        self.playback_events = PlaybackEventBuilder(self)
        self.navigator = TimelineNavigator(self)
        self.performance_rows = PerformanceRows(self)
        # DISPLAY_ATTRIBUTE_ORDER is the fixed default; attribute_order is
        # the live copy the reorder dialog mutates. A caller-supplied order
        # is honoured as-is.
        if not self.attribute_order:
            self.attribute_order = list(self.DISPLAY_ATTRIBUTE_ORDER)
        if self.file_path:
            # S2: imported HERE, not at module scope, and deliberately so.
            # models/ owns the data; parsers/ owns which builder a file
            # format needs. A module-level import would make that a
            # models -> parsers dependency AND would pull music21 (~460ms,
            # ~700 modules) into every process that merely touches the data
            # model, parsing or not. Deferring it to the one moment a file
            # is actually parsed keeps the documented
            # MusicData(file_path=...) shortcut working unchanged - see
            # parsers/timeline_builder_factory.py.
            from parsers.timeline_builder_factory import build_sections

            self.sections = build_sections(self)
            self._adopt_timeline_build(self.sections[0].build)
            self.active_event_index = 0
            self._set_percussion_voice_names()
        else:
            self._beat_markers: List[EventSlice] = []
            # A directly-constructed MusicData (caller-supplied
            # timeline_slices, no file) still has exactly one section so
            # every section-aware consumer has something to read. Its
            # build is None - set_active_section is unreachable with one
            # section, so nothing dereferences it.
            self.sections = [ScoreSection(index=0, label="", build=None)]
            self._adopt_timeline_build(None)

    def _adopt_timeline_build(self, build) -> None:
        """Make `build` (a models.timeline_build.TimelineBuild, or None to
        keep the current timeline_slices) the live timeline and reset every
        cache derived from it. Called by __post_init__ and by
        set_active_section.

        Every timeline-derived cache MUST be dropped here - a missed one is
        this method's failure mode. A stale _measure_numbers_cache alone
        makes `Go to bar` in a later section silently jump into an earlier
        section's slices.
        """
        if build is not None:
            build.apply_to(self)
        # The real, marker-free timeline, kept stable so
        # set_metronome_enabled can restore exactly this when the metronome
        # goes off again.
        self._real_timeline_slices = self.timeline_slices
        # Safe to cache until the next _adopt_timeline_build:
        # timeline_slices is not reassigned in between (the metronome
        # rebuild aside, which invalidates these itself). The
        # filter-dependent caches are dropped by
        # _invalidate_visibility_cache below.
        self._measure_numbers_cache: Optional[List[int]] = None
        # M1: parallel list of tempo_changes[i].quarters_from_start for the
        # bisect in _tempo_change_at. tempo_changes is assigned by
        # TimelineBuild.apply_to and not mutated after, so this is built
        # lazily and kept, like _measure_numbers_cache.
        self._tempo_change_starts_cache: Optional[List[float]] = None
        # P2 (UG "Tab" import): forward-filled "chord / lyric in effect"
        # context, aligned to _real_timeline_slices (the stable, marker-free
        # list) and resolved by quarters_from_start - same "cache until the
        # build changes, source is immutable after apply_to" property
        # _tempo_change_at relies on, and robust to the metronome splicing
        # markers into timeline_slices (a marker slice keeps a real
        # quarters_from_start).
        self._chord_context: Optional[List[Optional[Tuple[str, int]]]] = None
        self._lyric_context: Optional[List[Optional[Tuple[str, int]]]] = None
        self._context_quarters: Optional[List[float]] = None
        self._invalidate_visibility_cache()

    @property
    def has_multiple_sections(self) -> bool:
        """True for a MusicXML file split into 2+ independent pieces (see
        `sections`). Drives whether Region 1's section tab bar shows and
        whether `Navigation > Select Section...` is enabled."""
        return len(self.sections) > 1

    @property
    def active_section(self) -> ScoreSection:
        return self.sections[self.active_section_index]

    def set_active_section(self, index: int) -> bool:
        """Switch which section's TimelineBuild is live. Returns False (a
        no-op) for an out-of-range index or the already-active one, True
        when the switch happened.

        Everything keyed by whole-file facts - active_voice_filter,
        voice_display_attributes, mixer, the override dicts - carries across
        untouched; only the timeline-derived caches they feed are dropped
        (by _adopt_timeline_build). But state that was *baked into* the old
        section's NoteData at build time has to be re-applied to the fresh
        slices, in the same order __post_init__/apply_config use.
        """
        if not (0 <= index < len(self.sections)):
            return False
        if index == self.active_section_index:
            return False

        metronome_was_on = self.metronome_enabled

        self.active_section_index = index
        self._adopt_timeline_build(self.active_section.build)
        self.active_event_index = 0

        self.apply_part_overrides(self.part_name_overrides, self.part_program_overrides)
        self.apply_percussion_overrides()
        self.apply_key_signature_override(
            self.key_signature_override_fifths, self.key_signature_override_mode
        )
        self._set_percussion_voice_names()
        # _adopt_timeline_build swapped in the section's marker-free list,
        # so metronome_enabled no longer reflects timeline_slices. Force a
        # clean re-splice past set_metronome_enabled's no-op guard.
        if metronome_was_on:
            self.metronome_enabled = False
            self.set_metronome_enabled(True)
        return True

    def _invalidate_visibility_cache(self) -> None:
        """Drops the navigator's filter-dependent caches - see
        TimelineNavigator.invalidate_cache - and FindIndex's attribute-
        target occurrence cache (M1), which keys off the same
        active_voice_filter state. Called whenever active_voice_filter
        changes (set_active_voice_filter) and from set_metronome_enabled,
        which changes what counts as navigable."""
        self.navigator.invalidate_cache()
        self.find_index.invalidate_cache()

    def get_current_slice(self) -> Optional[EventSlice]:
        if 0 <= self.active_event_index < len(self.timeline_slices):
            return self.timeline_slices[self.active_event_index]
        return None

    def _slice_has_visible_notes(self, index: int) -> bool:
        """True if timeline_slices[index] has at least one note passing the
        Region 2 filter (Ref 7). Lets timeline navigation skip slices that
        only contain notes from deactivated parts/staves/voices, so e.g.
        stepping through a still-active semibreve viola part isn't
        interrupted by a deactivated flute's crotchet-rate slices."""
        if not (0 <= index < len(self.timeline_slices)):
            return False
        notes = self.timeline_slices[index].notes
        if not notes:
            return False
        if self.active_voice_filter is None:
            return True
        return any(
            (n.part_id, n.staff, n.voice) in self.active_voice_filter for n in notes
        )

    def set_metronome_enabled(self, enabled: bool) -> None:
        """Ref 14 toggle.

        timeline_slices is rebuilt rather than permanently merged, so with
        the metronome off it holds exactly "one entry per (measure, offset)
        with at least one sounding note" - the invariant the rest of the
        codebase assumes. Turning it on splices in TimelineBuilder's
        synthetic beat markers; turning it off restores the untouched real
        list. Indices shift either way, so the cursor is relocated to the
        equivalent real position rather than left on an arbitrary slice.
        """
        if enabled == self.metronome_enabled:
            return

        current = self.get_current_slice()
        self.metronome_enabled = enabled

        if enabled:
            merged = list(self._real_timeline_slices) + list(self._beat_markers)
            merged.sort(key=lambda s: (s.measure, s.quarters_from_start))
            self.timeline_slices = merged
        else:
            self.timeline_slices = self._real_timeline_slices

        if current is not None and self.timeline_slices:
            # Last slice at or before the current position: an exact match
            # where one exists, else the nearest preceding real event (which
            # is the case when toggling off while sitting on a marker, since
            # markers have no counterpart in the real-only list).
            match_index = 0
            for i, s in enumerate(self.timeline_slices):
                if s.quarters_from_start <= current.quarters_from_start:
                    match_index = i
                else:
                    break
            self.active_event_index = match_index

        self._invalidate_visibility_cache()

    def toggle_metronome(self) -> None:
        self.set_metronome_enabled(not self.metronome_enabled)

    def set_position_announcer_enabled(self, enabled: bool) -> None:
        """Ref 28 toggle. No timeline rebuild/cursor relocation needed,
        unlike set_metronome_enabled - see position_announcer_enabled's own
        comment for why."""
        self.position_announcer_enabled = enabled

    def toggle_position_announcer(self) -> None:
        self.set_position_announcer_enabled(not self.position_announcer_enabled)

    def set_bar_line_indicator_enabled(self, enabled: bool) -> None:
        """Options > Bar Line Indicator toggle. No timeline rebuild needed,
        exactly like set_position_announcer_enabled."""
        self.bar_line_indicator_enabled = enabled

    def toggle_bar_line_indicator(self) -> None:
        self.set_bar_line_indicator_enabled(not self.bar_line_indicator_enabled)

    # --- timeline navigation (Refs 2/3/5/6) ---------------------------
    #
    # S1: the logic and its visibility caches live in
    # models/timeline_navigator.py (TimelineNavigator, built in
    # __post_init__). Kept as delegators - NavigationController, the
    # Sequencer, Region 5's span jumps and a large body of tests all move
    # the cursor through MusicData.

    def _slice_is_navigable(self, index: int) -> bool:
        """Ref 14 AC4 - see TimelineNavigator.slice_is_navigable."""
        return self.navigator.slice_is_navigable(index)

    def _slice_has_visible_sounding_note(self, index: int) -> bool:
        """See TimelineNavigator.slice_has_visible_sounding_note."""
        return self.navigator.slice_has_visible_sounding_note(index)

    def _sounding_bounds(self) -> Optional[Tuple[int, int]]:
        """(first, last) navigable index - see
        TimelineNavigator.sounding_bounds."""
        return self.navigator.sounding_bounds()

    def move_timeline_left(self) -> bool:
        return self.navigator.move_left()

    def move_timeline_right(self) -> bool:
        return self.navigator.move_right()

    def measure_numbers(self) -> List[int]:
        """Distinct measure numbers present in the timeline, ascending."""
        return self.navigator.measure_numbers()

    def first_event_index_of_measure(self, measure_number: int) -> Optional[int]:
        """Index of the first timeline event in the measure, unfiltered -
        see TimelineNavigator.first_event_index_of_measure."""
        return self.navigator.first_event_index_of_measure(measure_number)

    def last_event_index(self) -> int:
        """Index of the last timeline event, or -1 if the timeline is empty."""
        return len(self.timeline_slices) - 1

    def first_visible_event_index_of_measure(self, measure_number: int) -> Optional[int]:
        """The measure's first event passing the Region 2 filter (Ref 7) -
        see TimelineNavigator.first_visible_event_index_of_measure."""
        return self.navigator.first_visible_event_index_of_measure(measure_number)

    def last_visible_event_index_of_measure(self, measure_number: int) -> Optional[int]:
        """Ref 29: the measure's LAST visible event - see
        TimelineNavigator.last_visible_event_index_of_measure."""
        return self.navigator.last_visible_event_index_of_measure(measure_number)

    def slice_index_at_or_after_quarters(self, quarters_from_start: float) -> Optional[int]:
        """First slice at or after an elapsed-quarters position - see
        TimelineNavigator.slice_index_at_or_after_quarters."""
        return self.navigator.slice_index_at_or_after_quarters(quarters_from_start)

    def move_timeline_left_by_measure(self) -> bool:
        """Ctrl+Left (Ref 3) - see TimelineNavigator.move_left_by_measure."""
        return self.navigator.move_left_by_measure()

    def move_timeline_right_by_measure(self) -> bool:
        """Ctrl+Right (Ref 3) - see TimelineNavigator.move_right_by_measure."""
        return self.navigator.move_right_by_measure()

    def jump_to_measure(self, measure_number: int) -> bool:
        """Ref 6: jump to a typed measure number - see
        TimelineNavigator.jump_to_measure."""
        return self.navigator.jump_to_measure(measure_number)

    def move_timeline_home(self) -> bool:
        """Home (Ref 5) - see TimelineNavigator.move_home."""
        return self.navigator.move_home()

    def last_sounding_event_index(self) -> Optional[int]:
        """The true end of playable content - see
        TimelineNavigator.last_sounding_event_index."""
        return self.navigator.last_sounding_event_index()

    def move_timeline_end(self) -> bool:
        """End (Ref 5) - see TimelineNavigator.move_end."""
        return self.navigator.move_end()

    def get_region_1_data(self) -> Dict[str, str]:
        """credits' "Tempo" entry is baked at parse time in US units, so it
        is rebuilt here to reflect a live UK/US toggle without a reload.
        Built from tempo_bpm directly, not the cursor-aware
        tempo_beat_unit_name_at, because Region 1 always shows the score's
        OPENING tempo (A9)."""
        data = dict(self.credits)
        if "Tempo" in data:
            number = self.tempo_bpm / self.tempo_beat_unit_quarter_length
            number_str = str(int(number)) if float(number).is_integer() else str(round(number, 2))
            unit = vocabulary.duration_name(self.tempo_beat_unit_name, self.uk_terms)
            data["Tempo"] = f"{number_str} {unit} notes per minute"
        # Multi-section MusicXML (UserPlans/MultiSectionScores.md): credits'
        # "Key Signature" / "Time Signature" are the whole file's opening
        # values, parsed once by MusicXMLReader. When the file is really N
        # independent pieces, Region 1 must show the ACTIVE section's own
        # opening key/time - taken live from its first slice, the same
        # "rebuild, don't touch the parsed original" pattern Tempo uses. A
        # single-section score never enters this branch, so its Region 1 is
        # bit-identical to before.
        if self.has_multiple_sections:
            first = self._real_timeline_slices[0] if self._real_timeline_slices else None
            if first is not None:
                data["Key Signature"] = key_signature_display_name(first.key_fifths, None)
                ts_num, ts_den = first.time_sig
                data["Time Signature"] = f"{ts_num}/{ts_den}"
            build = self.active_section.build
            if build is not None and build.tempo_changes:
                change = build.tempo_changes[0]
                number = change.tempo_bpm / change.beat_unit_quarter_length
                number_str = (
                    str(int(number)) if float(number).is_integer() else str(round(number, 2))
                )
                unit = vocabulary.duration_name(change.beat_unit_name, self.uk_terms)
                data["Tempo"] = f"{number_str} {unit} notes per minute"
        # S6: same "rebuild live, don't touch the parsed original" pattern
        # as Tempo above - and it must still win over the per-section key.
        if self.key_signature_override_fifths is not None:
            data["Key Signature"] = key_signature_display_name(
                self.key_signature_override_fifths, self.key_signature_override_mode
            )
        return data

    def get_score_structure(self) -> List[Dict[str, Any]]:
        """The parts/staves/voices shape Region2HierarchyModel expects
        (Ref 7). A pure transform of parts_info, no XML access."""
        structure = []
        for p in self.parts_info:
            staves = [
                {
                    "id": s_id,
                    "name": p.staves_clefs.get(s_id, "Standard stave"),
                    "voices": p.staves_voices[s_id],
                    "voice_names": {
                        v_id: p.voice_names[(s_id, v_id)]
                        for v_id in p.staves_voices[s_id]
                        if (s_id, v_id) in p.voice_names
                    },
                }
                for s_id in sorted(p.staves_voices.keys())
            ]
            structure.append({"id": p.part_id, "name": p.name, "staves": staves})
        return structure

    def set_active_voice_filter(self, active_tuples: Set[Tuple[str, int, int]]) -> None:
        self.active_voice_filter = set(active_tuples)
        self._invalidate_visibility_cache()

    def _all_voice_tuples(self) -> Set[Tuple[str, int, int]]:
        """Every (part_id, staff, voice) the score has - the universe
        export_config/apply_config filter saved keys against. Scans the
        notes rather than parts_info, which is only populated by
        MusicXMLReader.load() and so is empty for a directly-built
        MusicData even though the notes are all there."""
        return {
            (n.part_id, n.staff, n.voice)
            for event_slice in self._real_timeline_slices
            for n in event_slice.notes
        }

    def _visible_notes(self, index: Optional[int] = None) -> List[NoteData]:
        """Notes at the given slice passing the Region 2 filter (Ref 7), or
        at the cursor when index is None.

        Every UI-facing accessor reads through this, which is what makes a
        row index mean the same note in Region 3, Region 4 and playback
        alike. The explicit-index form is for the Sequencer, which plays by
        absolute index without disturbing the cursor or Region 3's
        selection (so phrase audition can leave the cursor untouched).
        """
        if index is None:
            current = self.get_current_slice()
        else:
            current = self.timeline_slices[index] if 0 <= index < len(self.timeline_slices) else None
        if not current or not current.notes:
            return []
        if self.active_voice_filter is None:
            return current.notes
        return [
            n for n in current.notes
            if (n.part_id, n.staff, n.voice) in self.active_voice_filter
        ]

    # Ref 15 AC4: the fixed DEFAULT rendering order for Region 3's optional
    # extra attributes and Region 4's rows - every fresh MusicData starts
    # attribute_order (see __post_init__) as a copy of this. F2's
    # attribute-order dialog mutates that live copy, never this constant.
    # "text" sits right before "measure" rather than beside "step" - it and
    # "step"/"octave"/"midi" are mutually exclusive per note (an ordinary
    # note never has "text", a stave text event never has step/octave/midi),
    # so its exact position among those three doesn't affect rendering
    # either way; placed here instead so it doesn't disturb the "step"/
    # "octave" adjacency and "strum is last" behaviour existing tests pin.
    DISPLAY_ATTRIBUTE_ORDER = [
        "step", "octave", "midi", "text", "measure", "beat position", "duration",
        "part", "stave", "voice", "string", "fret",
        "dynamic", "articulation", "fingering", "pluck", "strum",
        # P1 (D9): note-attached notations, grouped
        # after the existing optional tail. "other notation" is the D6
        # catch-all and stays last (a pinned move_attribute_order test
        # relies on that).
        "tie", "slur", "tuplet", "grace", "arpeggio", "fermata",
        "accidental", "glissando", "technique", "other notation",
        # P2 (D9): chord symbol/diagram, grouped last.
        # "chord diagram" is now the final key - the pinned
        # move_attribute_order boundary test tracks whatever is last.
        "chord symbol", "chord diagram",
    ]
    # A voice with no entry in voice_display_attributes uses this - today's
    # plain-note-name behaviour, not an empty display.
    DEFAULT_DISPLAY_ATTRIBUTES = frozenset({"step"})

    # The Find dialog (widgets/find_dialog.py): attribute keys on
    # essentially every note. "Next occurrence of step" is meaningless -
    # it's just "the next note" - so only the optional/situational tail of
    # DISPLAY_ATTRIBUTE_ORDER is offered as something to find.
    CORE_ATTRIBUTE_KEYS = frozenset({
        "step", "octave", "midi", "measure", "beat position", "duration",
        "part", "stave", "voice",
    })

    def notes_for_indices(self, selected_indices: List[int]) -> List[NoteData]:
        """The NoteData behind Region 3's selected rows, for callers needing
        the notes themselves rather than indices or pitches."""
        notes = self._visible_notes()
        return [notes[i] for i in selected_indices if 0 <= i < len(notes)]

    # --- Region 3/4 rendering + attribute system (Ref 15 AC4) ---------
    #
    # S1: the logic lives in models/note_renderer.py (NoteRenderer, built
    # in __post_init__). voice_display_attributes and attribute_order stay
    # fields here - export_config()/apply_config() persist them - so only
    # the reading and mutating moved. The three display constants below
    # stay here too, beside DISPLAY_ATTRIBUTE_ORDER/
    # DEFAULT_DISPLAY_ATTRIBUTES which apply_config also reads.

    # Attribute keys whose value alone is self-explanatory in Region 3's
    # comma-joined note text, so the "<Label> " prefix
    # NoteRenderer.format_note_for_region_3 adds for every other attribute
    # is dropped: "step" ("F sharp") needs no "Step" prefix, and per user
    # request "duration" doesn't either WHEN it is a real word - "quaver"
    # already says what it is without "Duration quaver". A bare number has
    # no such self-evidence (could be mistaken for a measure/beat/pitch
    # value), so it keeps the "Duration" prefix - see that method, which
    # checks note.duration_name_us itself rather than relying on this set
    # for "duration". Region 4's table always labels its "Duration" row
    # regardless; only the inline Region 3 rendering ever omits the prefix.
    REGION_3_UNPREFIXED_ATTRIBUTES = frozenset({"step", "text", "duration"})

    def _note_attribute_pairs(self, note: NoteData) -> Dict[str, str]:
        """Attribute name -> value for one note - see
        NoteRenderer.note_attribute_pairs."""
        return self.renderer.note_attribute_pairs(note)

    def _region_4_rows(self, selected_notes: List[NoteData]) -> List[Tuple[str, str, NoteData, str]]:
        """See NoteRenderer.region_4_rows."""
        return self.renderer.region_4_rows(selected_notes)

    def _format_note_for_region_3(self, note: NoteData) -> str:
        """See NoteRenderer.format_note_for_region_3."""
        return self.renderer.format_note_for_region_3(note)

    def get_region_3_data(self) -> List[str]:
        return self.renderer.region_3_data()

    def get_region_4_data_for_indices(self, selected_indices: List[int]) -> Dict[str, str]:
        return self.renderer.region_4_data_for_indices(selected_indices)

    def get_region_4_rows_for_indices(self, selected_indices: List[int]) -> List[Tuple[str, str, str]]:
        """(display_key, attribute_key, value) triples for Region 4's rows -
        see NoteRenderer.region_4_rows_for_indices."""
        return self.renderer.region_4_rows_for_indices(selected_indices)

    def get_region_4_row_targets(self, selected_indices: List[int]) -> List[Tuple[str, NoteData]]:
        """(attribute_key, note) per Region 4 row - see
        NoteRenderer.region_4_row_targets."""
        return self.renderer.region_4_row_targets(selected_indices)

    def note_has_display_attribute(self, note: NoteData, attribute_key: str) -> bool:
        """Whether `note`'s own voice currently shows `attribute_key` in
        Region 3 - drives the Add-vs-Remove variant of the Ref 15 AC4
        context menu."""
        return self.renderer.display_attribute_present_for_voice(
            attribute_key, note.part_id, note.staff, note.voice
        )

    def display_attribute_present_for_voice(
        self, attribute_key: str, part_id: str, staff: int, voice: int
    ) -> bool:
        """note_has_display_attribute, from a bare (part_id, staff, voice)
        tuple instead of a NoteData - see
        NoteRenderer.display_attribute_present_for_voice."""
        return self.renderer.display_attribute_present_for_voice(
            attribute_key, part_id, staff, voice
        )

    def set_display_attribute(
        self, attribute_key: str, scope: str, notes: List[NoteData], add: bool
    ) -> None:
        """Ref 15 AC4: add/remove an attribute across a scope - see
        NoteRenderer.set_display_attribute."""
        self.renderer.set_display_attribute(attribute_key, scope, notes, add)

    def set_display_attribute_for_voice(
        self, attribute_key: str, scope: str, part_id: str, staff: int, voice: int, add: bool
    ) -> None:
        """set_display_attribute from a Region 2 node position - see
        NoteRenderer.set_display_attribute_for_voice."""
        self.renderer.set_display_attribute_for_voice(
            attribute_key, scope, part_id, staff, voice, add
        )

    def move_attribute_order(self, attribute_key: str, up: bool, within: Optional[List[str]] = None) -> bool:
        """F2/Ref 15 AC4: move an attribute one step in the live rendering
        order - see NoteRenderer.move_attribute_order."""
        return self.renderer.move_attribute_order(attribute_key, up, within)

    def attribute_keys_for_voices(self, voice_tuples: Set[Tuple[str, int, int]]) -> List[str]:
        """Every attribute key present on a note in these voices, ordered
        per attribute_order - see NoteRenderer.attribute_keys_for_voices."""
        return self.renderer.attribute_keys_for_voices(voice_tuples)

    def set_attribute_order_within(self, new_order: List[str], within: List[str]) -> None:
        """Commits the Reorder Attributes dialog's staged order on OK - see
        NoteRenderer.set_attribute_order_within."""
        self.renderer.set_attribute_order_within(new_order, within)

    def reorder_parts(self, part_id_order: List[str]) -> None:
        """Options > Reorder Parts... - the order parts_info lists parts
        in, live and user-controlled (the same "mutable order the render
        layer reads" pattern attribute_order already established, just for
        parts instead of attributes). Affects Region 2's part-row order
        (main_window.py reorders Region2HierarchyModel.roots to match
        separately, without a full rebuild - see
        Region2ListWidget.reorder_parts, since a load_score_structure
        rebuild would discard on/off toggles) and, in turn, Region 3's
        note-row order: a stable re-sort of every EventSlice.notes list by
        the new part order, so e.g. a UG score's Chords/Lyrics rows come
        back in whichever order the user chose - most importantly
        controlling which part's row a screen reader lands on first after
        every navigation step, since Region 3's "current" row is always
        row 0 (this is the whole point of the feature: NVDA reading the
        chord name when the user wanted to hear the lyric, or vice versa).

        Best-effort, like every other saved-config restore in this class:
        an unknown part_id in part_id_order is ignored; a known part_id
        missing from it keeps its existing relative order, appended after
        every part that was explicitly ordered - so a stale or partial
        saved order still applies everything it can rather than being
        rejected outright."""
        known_ids = [p.part_id for p in self.parts_info]
        ordered = [pid for pid in part_id_order if pid in known_ids]
        ordered += [pid for pid in known_ids if pid not in ordered]
        order_index = {pid: i for i, pid in enumerate(ordered)}

        self.parts_info.sort(key=lambda p: order_index[p.part_id])

        def note_sort_key(note: NoteData) -> int:
            return order_index.get(note.part_id, len(ordered))

        for event_slice in self.timeline_slices:
            event_slice.notes.sort(key=note_sort_key)

    def export_config(self) -> ScoreConfig:
        """Ref 27: this score's state as a ScoreConfig. voices_muted is the
        complement of active_voice_filter, not the active list - a muted-set
        is what lets a changed score still load best-effort (see
        apply_config). MainWindow overwrites it with Region 2's own
        per-node state, which is lossless where this derived version is
        not (and MusicData has no solo concept at all, so parts_soloed/
        staves_soloed/voices_soloed stay at their empty defaults here -
        also only ever filled in by Region 2's own state)."""
        voices_muted: Set[Tuple[str, int, int]] = set()
        if self.active_voice_filter is not None:
            voices_muted = self._all_voice_tuples() - self.active_voice_filter
        return ScoreConfig(
            voices_muted=voices_muted,
            metronome_enabled=self.metronome_enabled,
            position_announcer_enabled=self.position_announcer_enabled,
            bar_line_indicator_enabled=self.bar_line_indicator_enabled,
            voice_display_attributes={
                k: set(v) for k, v in self.voice_display_attributes.items()
            },
            attribute_order=list(self.attribute_order),
            mixer=self.mixer.copy(),
            part_name_overrides=dict(self.part_name_overrides),
            part_program_overrides=dict(self.part_program_overrides),
            key_signature_override_fifths=self.key_signature_override_fifths,
            key_signature_override_mode=self.key_signature_override_mode,
            playback_tempo_bpm=self.playback_tempo_bpm,
            part_order=[p.part_id for p in self.parts_info],
            percussion_item_overrides=dict(self.percussion_item_overrides),
            percussion_item_name_overrides=dict(self.percussion_item_name_overrides),
            percussion_auto_correct_enabled=self.percussion_auto_correct_enabled,
            last_position_index=self.active_event_index,
        )

    def apply_config(self, config: ScoreConfig) -> None:
        """Ref 27: restore a saved ScoreConfig, best-effort. An entry that no
        longer matches anything in THIS score (renamed part, deleted voice,
        unknown attribute key) is dropped silently rather than rejecting the
        whole config, so a stale .rsc still applies everything it can."""
        if 0 <= config.last_position_index < len(self.timeline_slices):
            self.active_event_index = config.last_position_index

        known_voices = self._all_voice_tuples()
        active = known_voices - (config.voices_muted & known_voices)
        self.set_active_voice_filter(active)

        self.voice_display_attributes = {
            voice_key: set(attrs)
            for voice_key, attrs in config.voice_display_attributes.items()
            if voice_key in known_voices
        }

        known_attribute_keys = set(self.DISPLAY_ATTRIBUTE_ORDER)
        ordered = [key for key in config.attribute_order if key in known_attribute_keys]
        ordered += [key for key in self.DISPLAY_ATTRIBUTE_ORDER if key not in ordered]
        self.attribute_order = ordered

        self.set_metronome_enabled(config.metronome_enabled)
        self.set_position_announcer_enabled(config.position_announcer_enabled)
        self.set_bar_line_indicator_enabled(config.bar_line_indicator_enabled)
        self.mixer = config.mixer.copy()

        known_part_ids = {p.part_id for p in self.parts_info}
        self.apply_part_overrides(
            {k: v for k, v in config.part_name_overrides.items() if k in known_part_ids},
            {k: v for k, v in config.part_program_overrides.items() if k in known_part_ids},
        )

        self.apply_key_signature_override(
            config.key_signature_override_fifths, config.key_signature_override_mode
        )

        # Ref 12: absolute per-score playback tempo. Best-effort - accept
        # None or a finite positive number, clamp defensively into a sane
        # quarter-BPM band, otherwise leave the score default (None).
        tempo_bpm = config.playback_tempo_bpm
        try:
            tempo_bpm = float(tempo_bpm) if tempo_bpm is not None else None
        except (TypeError, ValueError):
            tempo_bpm = None
        if tempo_bpm is not None and tempo_bpm == tempo_bpm and 0.0 < tempo_bpm < float("inf"):
            self.playback_tempo_bpm = max(1.0, min(1000.0, tempo_bpm))
        else:
            self.playback_tempo_bpm = None

        if config.part_order:
            self.reorder_parts(config.part_order)

        known_percussion_items = {
            (n.part_id, n.percussion_source_key)
            for s in self._real_timeline_slices
            for n in s.notes
            if n.percussion_source_key is not None
        }
        self.percussion_item_overrides = {
            k: v for k, v in config.percussion_item_overrides.items() if k in known_percussion_items
        }
        self.percussion_item_name_overrides = {
            k: v for k, v in config.percussion_item_name_overrides.items() if k in known_percussion_items
        }
        self.percussion_auto_correct_enabled = config.percussion_auto_correct_enabled
        self.apply_percussion_overrides()

    def get_midi_notes_for_indices(self, selected_indices: List[int]) -> List[int]:
        notes = self._visible_notes()
        if not notes or not selected_indices:
            return []
        pitches: List[int] = []
        for i in selected_indices:
            if not (0 <= i < len(notes)):
                continue
            note = notes[i]
            if note.chord_pitches is not None:
                # Guitar Pro's synthetic Chords voice: one NoteData per
                # strum event carries the whole chord here rather than one
                # pitch in midi_pitch (see NoteData.chord_pitches).
                pitches.extend(note.chord_pitches)
            elif note.midi_pitch is not None:
                pitches.append(note.midi_pitch)
        return pitches

    def get_performance_region_rows(self, index: Optional[int] = None) -> List[PerformanceRegionRow]:
        """Ref 29: Region 5's rows for the given position (default the
        cursor). Delegator - see PerformanceRows.get_performance_region_rows."""
        return self.performance_rows.get_performance_region_rows(index)

    def _ensure_context_arrays(self) -> None:
        """Builds the forward-filled chord/lyric context once. Each entry is
        (display_text, onset_measure) of the last CHORDS_PART_ID / real
        LYRICS_PART_ID note seen at or before that slice, or None before the
        first. Aligned to _real_timeline_slices; _context_quarters is the
        parallel quarters_from_start list for a bisect."""
        if self._chord_context is not None:
            return
        chord_ctx: List[Optional[Tuple[str, int]]] = []
        lyric_ctx: List[Optional[Tuple[str, int]]] = []
        quarters: List[float] = []
        cur_chord: Optional[Tuple[str, int]] = None
        cur_lyric: Optional[Tuple[str, int]] = None
        for s in self._real_timeline_slices:
            for n in s.notes:
                if n.part_id == CHORDS_PART_ID:
                    text = n.chord_symbol or n.step_name
                    if text:
                        cur_chord = (text, s.measure)
                elif n.part_id == LYRICS_PART_ID:
                    if n.step_name and n.step_name != "No lyrics":
                        cur_lyric = (n.step_name, s.measure)
            chord_ctx.append(cur_chord)
            lyric_ctx.append(cur_lyric)
            quarters.append(s.quarters_from_start)
        self._chord_context = chord_ctx
        self._lyric_context = lyric_ctx
        self._context_quarters = quarters

    def _section_span_at(self, measure: int) -> Optional[SectionSpan]:
        """The song section (P2) containing `measure`, or None. Sections
        don't overlap, so the first match is the only one."""
        for span in self.section_spans:
            if span.start_measure <= measure <= span.end_measure:
                return span
        return None

    def get_performance_context_rows(self, index: Optional[int] = None) -> List[PerformanceRegionRow]:
        """P2: 0-3 "what's in effect at the cursor" rows for Region 5 -
        Section / Chord / Lyric - each omitted when it has no value. Updated
        as the cursor moves (RegionPresenter.refresh_region_5 relabels them
        in place, without re-firing the change cue). Structural context,
        like sections themselves - computed regardless of the Region 2 voice
        filter. Ctrl+Home/Ctrl+End on one jumps to its onset bar."""
        resolved_index = self.active_event_index if index is None else index
        if not (0 <= resolved_index < len(self.timeline_slices)):
            return []
        slice_ = self.timeline_slices[resolved_index]
        self._ensure_context_arrays()

        rows: List[PerformanceRegionRow] = []
        span = self._section_span_at(slice_.measure)
        if span is not None and span.label:
            rows.append(PerformanceRegionRow(
                label=f"Section: {span.label}",
                jump_target_measure=span.start_measure,
            ))

        assert self._context_quarters is not None
        ctx_i = bisect.bisect_right(self._context_quarters, slice_.quarters_from_start) - 1
        chord = self._chord_context[ctx_i] if ctx_i >= 0 else None
        lyric = self._lyric_context[ctx_i] if ctx_i >= 0 else None
        if chord is not None and chord[0]:
            rows.append(PerformanceRegionRow(
                label=f"Chord: {chord[0]}",
                jump_target_measure=chord[1],
            ))
        if lyric is not None and lyric[0]:
            rows.append(PerformanceRegionRow(
                label=f"Lyric: {lyric[0]}",
                jump_target_measure=lyric[1],
            ))
        return rows

    def is_at_beginning_repeat_target(self, index: Optional[int] = None) -> bool:
        """True when the resolved slice is the first note of measure 1 AND a
        repeat sends playback back there (a RepeatSpan with start_measure ==
        1) - "there is a repeat that takes the user back to the beginning"
        (the user's own framing, requested after Ref 29 shipped). Landing
        here after already having been inside that same still-active span -
        stepping back from bar 2, or starting playback from bar 1 without
        first navigating away - would otherwise never re-fire Region 5's
        change cue, since RegionPresenter.refresh_region_5's row-label diff
        sees no difference from last time. This is a deliberate, narrow
        carve-out for that one case, not a general "re-fire on every
        repeat-start arrival" rule - an ordinary mid-score practice repeat
        (e.g. bars 4-5) keeps the existing dedup untouched."""
        resolved_index = self.active_event_index if index is None else index
        if not (0 <= resolved_index < len(self.timeline_slices)):
            return False
        slice_ = self.timeline_slices[resolved_index]
        if slice_.measure != 1 or slice_.beat_position != 1.0:
            return False
        return any(span.start_measure == 1 for span in self.repeat_spans)

    @staticmethod
    def _format_tempo_number(value: float) -> str:
        """Whole numbers print bare ("100"), not "100.0" - same rounding
        _tempo_status_field already uses for the live playback-tempo field,
        factored out here so this row's wording matches it exactly."""
        return str(int(value)) if float(value).is_integer() else str(round(value, 2))

    @staticmethod
    def _bar_beat_label(bar_word: str, measure: int, beat_position: float) -> str:
        """"bar N" on the downbeat (the bar number already pins it down, and
        repeat/ending rows are always this case since barlines fall at
        measure boundaries); "bar N beat B" otherwise, worded exactly as
        get_status_bar_fields does so it reads the same everywhere. Only
        markers actually falling mid-bar name a beat (user's decision)."""
        if float(beat_position) == 1.0:
            return f"{bar_word} {measure}"
        beat_str = str(int(beat_position)) if float(beat_position).is_integer() else str(beat_position)
        return f"{bar_word} {measure} beat {beat_str}"

    def _marking_part_prefix(self, part_id: str, contributing_part_ids) -> str:
        """D5: a Region 5 / Performance Report row for a per-part marking is
        prefixed with the part name only when more than one part contributes
        a marking of that kind. `contributing_part_ids` is any iterable of
        the part_ids that do."""
        if len(set(contributing_part_ids)) <= 1:
            return ""
        name = next((p.name for p in self.parts_info if p.part_id == part_id), None)
        return f"{name}: " if name else ""

    # --- Find (widgets/find_dialog.py) --------------------------------
    #
    # S1: the scanner itself lives in models/find_index.py (FindIndex,
    # built in __post_init__). These stay as delegators because Find's
    # occurrences depend on the live voice filter and attribute system,
    # so callers must keep asking MusicData rather than holding their own
    # FindIndex.

    def available_find_targets(self) -> List[FindTarget]:
        """The Find dialog's list, computed fresh from the loaded score -
        see FindIndex.available_targets."""
        return self.find_index.available_targets()

    def available_find_targets_with_counts(self) -> List[Tuple[FindTarget, int]]:
        """The Find dialog's list plus each row's occurrence count (D13) -
        see FindIndex.available_targets_with_counts."""
        return self.find_index.available_targets_with_counts()

    def find_occurrence(self, target: FindTarget, from_index: int, direction: int) -> Optional[int]:
        """The next/previous occurrence of `target` - see
        FindIndex.find_occurrence."""
        return self.find_index.find_occurrence(target, from_index, direction)

    def get_performance_report_lines(self) -> List[str]:
        """Ref 29: the Performance Report's whole-score summary lines.
        Delegator - see PerformanceRows.get_performance_report_lines."""
        return self.performance_rows.get_performance_report_lines()

    # Ref 12 AC2: hard bounds, in the score's DISPLAY units - what the user
    # reads and types (the time-signature-denominator beat), not the
    # internal quarter-note equivalent.
    MIN_TEMPO_BPM = 5
    MAX_TEMPO_BPM = 300

    def _tempo_change_at(self, index: Optional[int] = None) -> Tuple[int, float, str]:
        """(tempo_bpm, beat_unit_quarter_length, beat_unit_name) in effect at
        an index, or the cursor. Falls back to the score's opening tempo
        before the first marking. tempo_changes is sorted by position
        (TimelineBuilder's job), so the last entry not past it wins - found
        here with a bisect over the change positions rather than a linear
        walk: this is on the Sequencer's per-step path via
        effective_tempo_bpm and is called N times over by
        FindIndex.tempo_change_indices (M1)."""
        idx = self.active_event_index if index is None else index
        quarters = self.timeline_slices[idx].quarters_from_start if 0 <= idx < len(self.timeline_slices) else 0.0

        if self._tempo_change_starts_cache is None:
            self._tempo_change_starts_cache = [
                c.quarters_from_start for c in self.tempo_changes
            ]
        pos = bisect.bisect_right(self._tempo_change_starts_cache, quarters)
        if pos == 0:
            return (self.tempo_bpm, self.tempo_beat_unit_quarter_length, self.tempo_beat_unit_name)
        change = self.tempo_changes[pos - 1]
        return (change.tempo_bpm, change.beat_unit_quarter_length, change.beat_unit_name)

    def score_tempo_display_bpm(self, index: Optional[int] = None) -> float:
        """The tempo actually in effect at `index` (or the cursor), in the
        beat unit it was authored in (A9) - e.g. 96 for a passage marked
        eighth=96, not the quarter-note-equivalent BPM used internally for
        playback timing."""
        bpm, beat_unit_ql, _ = self._tempo_change_at(index)
        return bpm / beat_unit_ql

    def _ts_denominator_at(self, index: Optional[int] = None) -> int:
        """The time-signature denominator in effect at `index` (or the
        cursor), 4 when the timeline is empty / out of range - the beat unit
        the absolute playback tempo is expressed in."""
        idx = self.active_event_index if index is None else index
        if 0 <= idx < len(self.timeline_slices):
            return self.timeline_slices[idx].time_sig[1] or 4
        return 4

    def effective_playback_quarter_bpm(self) -> float:
        """The absolute playback tempo in quarter-note BPM, flat across the
        whole piece (Ref 12: "always flat"). The user's override if set,
        else the score's opening tempo. No `index` - it does not vary with
        position."""
        return self.playback_tempo_bpm or self.tempo_bpm

    def playback_tempo_display_bpm(self, index: Optional[int] = None) -> float:
        """The absolute playback tempo converted to the time-signature
        denominator beat at `index` (or the cursor) - what the status bar
        shows and the Play Settings dialog / F / S / D read. Shifts as the
        cursor crosses a TS change even though the physical speed is
        constant; Region 1 still shows the score's own notated marking, so
        the two can legitimately differ."""
        return self.effective_playback_quarter_bpm() * self._ts_denominator_at(index) / 4.0

    def set_playback_tempo_display_bpm(self, value: float, index: Optional[int] = None) -> None:
        """Set the absolute playback tempo from a denominator-relative
        number (Ref 12 AC2: clamped to [MIN_TEMPO_BPM, MAX_TEMPO_BPM], not
        rejected). Stored back as quarter-note BPM."""
        value = max(self.MIN_TEMPO_BPM, min(self.MAX_TEMPO_BPM, float(value)))
        self.playback_tempo_bpm = value * 4.0 / self._ts_denominator_at(index)

    def nudge_playback_tempo(self, delta_display: float) -> None:
        """F / S: +/-10 of the displayed (denominator-relative) number."""
        self.set_playback_tempo_display_bpm(self.playback_tempo_display_bpm() + delta_display)

    def effective_tempo_bpm(self, index: Optional[int] = None) -> float:
        """Quarter-note BPM for real playback timing (Sequencer,
        get_duration_ms_for_index). Flat: `index` is accepted for call-site
        compatibility but ignored - playback no longer follows the score's
        internal tempo changes (Ref 12: "always flat")."""
        return self.effective_playback_quarter_bpm()

    def tempo_beat_unit_name_at(self, index: Optional[int] = None) -> str:
        """The beat unit label (e.g. "eighth"/"quaver") in effect at `index`
        (or the cursor) - lets the status bar show the right unit even where
        a mid-score tempo marking changes beat unit, not just the number.
        F4/D-6: translated per self.uk_terms."""
        _, _, name = self._tempo_change_at(index)
        return vocabulary.duration_name(name, self.uk_terms)

    def reset_playback_tempo(self) -> None:
        """D (Ref 12 AC4): reset control returns to the score's own tempo."""
        self.playback_tempo_bpm = None

    # Channels no real part may use. Each value is duplicated from the
    # audio/ module that owns it rather than imported - models/ must not
    # depend on audio/. Keeping parts off these is what stops an instrument
    # colliding with the click, the spoken position word or the change cue.
    #
    # Named METRONOME_CLICK_CHANNEL, not PERCUSSION_CHANNEL (its old name,
    # before wishlist #8): a REAL percussion part (is_percussion=True) is
    # NOT routed here - it gets an ordinary channel like any other part,
    # program-selected to the GM percussion bank instead (see
    # get_playback_events_for_indices). This channel is reserved only
    # because audio/metronome.py's click sound already owns it - the old
    # name would now wrongly suggest real percussion notes land here too.
    METRONOME_CLICK_CHANNEL = 9    # audio/metronome.py METRONOME_CHANNEL
    POSITION_ANNOUNCER_CHANNEL = 8  # audio/position_announcer.py
    PERFORMANCE_CUE_CHANNEL = 7     # audio/performance_cue.py
    LIVE_MIDI_INPUT_CHANNEL = 6     # audio/midi_input.py LIVE_MIDI_INPUT_CHANNEL
    VOICE_CONTROL_CUE_CHANNEL = 5   # audio/voice_confirmation_cue.py
    BOUNDARY_CUE_CHANNEL = 4        # audio/boundary_cue.py
    RESERVED_CHANNELS = {
        POSITION_ANNOUNCER_CHANNEL, METRONOME_CLICK_CHANNEL,
        PERFORMANCE_CUE_CHANNEL, LIVE_MIDI_INPUT_CHANNEL, VOICE_CONTROL_CUE_CHANNEL,
        BOUNDARY_CUE_CHANNEL,
    }
    MAX_MIDI_CHANNELS = 16

    def get_channel_for_part(self, part_id: str) -> int:
        """One MIDI channel per part, in part-list order, skipping
        RESERVED_CHANNELS. Wraps if a score has more melodic parts than the
        16 channels minus reservations allow.

        The usable list is built per call, not as a class attribute: only a
        comprehension's outermost iterable is evaluated in the enclosing
        class scope, not its condition, so referring to RESERVED_CHANNELS
        there raises NameError. 16 elements is too cheap to be worth caching
        another way.
        """
        usable_channels = [
            c for c in range(self.MAX_MIDI_CHANNELS) if c not in self.RESERVED_CHANNELS
        ]
        for idx, p in enumerate(self.parts_info):
            if p.part_id == part_id:
                return usable_channels[idx % len(usable_channels)]
        return 0

    def get_gmidi_program_for_part(self, part_id: str) -> int:
        for p in self.parts_info:
            if p.part_id == part_id:
                return p.gmidi_program
        return 25

    def is_percussion_part(self, part_id: str) -> bool:
        """Wishlist #8: whether this part's notes are unpitched percussion
        (a MusicXML percussion clef, or a MIDI channel-10 track) rather than
        real GM instrument notes - see PartStructureInfo.is_percussion.
        get_playback_events_for_indices reads this to route the part's
        channel to the GM percussion bank instead of its (meaningless, for
        percussion) gmidi_program."""
        for p in self.parts_info:
            if p.part_id == part_id:
                return p.is_percussion
        return False

    # --- user overrides (S5/S6/wishlist #8) ---------------------------
    #
    # S1: the mutation logic lives in models/override_manager.py
    # (OverrideManager, built in __post_init__). The override dicts stay
    # fields on MusicData - export_config() persists them and the dialogs
    # write to them directly - so only the "apply it to the parsed notes"
    # half moved.

    def apply_part_overrides(
        self, name_overrides: Dict[str, str], program_overrides: Dict[str, int]
    ) -> None:
        """S5: rename a part and/or change its instrument - see
        OverrideManager.apply_part_overrides."""
        self.overrides.apply_part_overrides(name_overrides, program_overrides)

    def _set_percussion_voice_names(self) -> None:
        """See OverrideManager.set_percussion_voice_names."""
        self.overrides.set_percussion_voice_names()

    def get_percussion_items_for_part(
        self, part_id: str
    ) -> List[Tuple[Tuple[str, int], str, int]]:
        """The Instruments dialog's per-item rows for a percussion part -
        see OverrideManager.get_percussion_items_for_part."""
        return self.overrides.get_percussion_items_for_part(part_id)

    def apply_percussion_overrides(self) -> None:
        """Wishlist #8: re-resolve every percussion item's name and sound -
        see OverrideManager.apply_percussion_overrides."""
        self.overrides.apply_percussion_overrides()

    def apply_key_signature_override(
        self, fifths: Optional[int], mode: Optional[str]
    ) -> None:
        """S6: a single whole-piece key signature override - see
        OverrideManager.apply_key_signature_override."""
        self.overrides.apply_key_signature_override(fifths, mode)

    def get_stave_name_for_part(self, part_id: str, staff: int) -> str:
        """Spoken-friendly stave name for Region 4 ("Treble stave"), worded
        exactly as Region 2 does so a note matches the stave it was toggled
        under. D-15: deliberately NOT translated by the uk_terms toggle."""
        for p in self.parts_info:
            if p.part_id == part_id:
                return p.staves_clefs.get(staff, "Standard stave")
        return "Standard stave"

    # --- playback events, timing and stepping -------------------------
    #
    # S1: the logic lives in models/playback_event_builder.py
    # (PlaybackEventBuilder, built in __post_init__). Kept as delegators
    # because the Sequencer, PlaybackController and the tests all reach
    # these through MusicData, and a playback run must never hold its own
    # builder - MusicData is replaced wholesale on every load.

    def get_playback_events_for_indices(
        self, selected_indices: List[int], index: Optional[int] = None
    ) -> List[Tuple[int, Optional[int], List[int], int]]:
        """Selected notes grouped by part for multi-part playback (Ref 8) -
        see PlaybackEventBuilder.events_for_indices."""
        return self.playback_events.events_for_indices(selected_indices, index)

    def get_grace_note_events_for_indices(
        self, selected_indices: List[int], index: Optional[int] = None
    ) -> List[Tuple[int, Optional[int], List[int]]]:
        """The grace-note side channel - see
        PlaybackEventBuilder.grace_events_for_indices."""
        return self.playback_events.grace_events_for_indices(selected_indices, index)

    def get_grace_note_events_at_index(self, index: int) -> List[Tuple[int, Optional[int], List[int]]]:
        """See PlaybackEventBuilder.grace_events_at_index."""
        return self.playback_events.grace_events_at_index(index)

    def get_playback_events_at_index(self, index: int) -> List[Tuple[int, Optional[int], List[int], int]]:
        """The Sequencer's index-based equivalent of
        get_playback_events_for_indices - see
        PlaybackEventBuilder.events_at_index."""
        return self.playback_events.events_at_index(index)

    def get_current_duration_ms(self) -> int:
        return self.get_duration_ms_for_index(self.active_event_index)

    def get_duration_ms_for_index(self, index: int) -> int:
        """Slice-wide duration at an arbitrary index - see
        PlaybackEventBuilder.duration_ms_for_index."""
        return self.playback_events.duration_ms_for_index(index)

    def get_ring_out_ms_for_index(self, index: int, events=None) -> int:
        """How long the notes at this index actually take to stop ringing -
        see PlaybackEventBuilder.ring_out_ms_for_index."""
        return self.playback_events.ring_out_ms_for_index(index, events)

    def _quarters_to_ms(self, quarter_length: float, index: Optional[int]) -> int:
        """See PlaybackEventBuilder.quarters_to_ms."""
        return self.playback_events.quarters_to_ms(quarter_length, index)

    def bar_bounds_quarters(self, index: int) -> Optional[Tuple[float, float]]:
        """(start, end) of this slice's bar in elapsed quarters - see
        PlaybackEventBuilder.bar_bounds_quarters."""
        return self.playback_events.bar_bounds_quarters(index)

    def span_ms_to_quarters(self, start_index: int, end_quarters: float) -> int:
        """Tempo-change-aware elapsed milliseconds across a span - see
        PlaybackEventBuilder.span_ms_to_quarters."""
        return self.playback_events.span_ms_to_quarters(start_index, end_quarters)

    def next_visible_event_index(
        self, index: int, end_index: Optional[int] = None
    ) -> Optional[int]:
        """The plain, stateless playback step (rests included) - see
        PlaybackEventBuilder.next_visible_event_index."""
        return self.playback_events.next_visible_event_index(index, end_index)

    def next_playback_index(
        self,
        index: int,
        jump_state: PlaybackJumpState,
        end_index: Optional[int] = None,
        jump_lower_bound: int = 0,
    ) -> Optional[int]:
        """The repeat/ending/Segno/Coda/D.C./D.S./Fine-aware playback step -
        see PlaybackEventBuilder.next_playback_index. Arrow-key navigation
        uses next_visible_event_index above and is untouched by this."""
        return self.playback_events.next_playback_index(
            index, jump_state, end_index, jump_lower_bound
        )

    def playback_span_ms(self, start_index: int, end_index: int, end_quarters: float) -> int:
        """Jump-aware elapsed milliseconds for Preview's loop timing - see
        PlaybackEventBuilder.playback_span_ms."""
        return self.playback_events.playback_span_ms(start_index, end_index, end_quarters)

    def simulate_loop_iteration(
        self, start_index: int, measure_budget: int, seed_jump_state=None
    ):
        """One repeat-aware looped iteration's (indices, span_ms,
        end_quarters) - see PlaybackEventBuilder.simulate_loop_iteration."""
        return self.playback_events.simulate_loop_iteration(
            start_index, measure_budget, seed_jump_state
        )

    def get_status_bar_fields(self) -> List[str]:
        """The first four status-bar fields in Tab order: position, key,
        time signature, playback tempo. All read the CURRENT slice, not the
        score's opening values - any of them can change mid-score, unlike
        Region 1's one-off summary. The tempo field is the only way a
        screen-reader user can check playback tempo without an
        announcement."""
        bar_word = vocabulary.bar_word(self.uk_terms).capitalize()
        current = self.get_current_slice()
        if current is None:
            return [f"{bar_word} - beat -", "Key: -", "Time: -", self._tempo_status_field()]

        beat = current.beat_position
        beat_str = str(int(beat)) if float(beat).is_integer() else str(beat)
        ts_num, ts_den = current.time_sig
        # S6: the override, when set, wins everywhere - not just where the
        # file's own key is missing/wrong (matches how apply_part_overrides
        # already behaves for name/program).
        if self.key_signature_override_fifths is not None:
            key_name = key_signature_display_name(
                self.key_signature_override_fifths, self.key_signature_override_mode
            )
        else:
            key_name = key_signature_display_name(current.key_fifths, None)

        return [
            f"{bar_word} {current.measure} beat {beat_str}",
            f"Key: {key_name}",
            f"Time: {ts_num}/{ts_den}",
            self._tempo_status_field(),
        ]

    def tempo_display_beat_unit_name_at(self, index: Optional[int] = None) -> str:
        """The note value of the time-signature denominator at `index` (or
        the cursor), translated per uk_terms - the beat the ABSOLUTE
        playback tempo number is counted in (a quarter in 4/4, an eighth in
        6/8). Distinct from tempo_beat_unit_name_at, which names the score's
        own notated tempo marking's unit (used by Region 5 / the report)."""
        from models.duration_units import quarter_length_to_display_name

        name = quarter_length_to_display_name(4.0 / self._ts_denominator_at(index)) or "quarter"
        return vocabulary.duration_name(name, self.uk_terms)

    def _tempo_status_field(self) -> str:
        """The ABSOLUTE playback tempo, in time-signature-denominator beats
        per minute (Ref 12). "(score default)" while no override is set.
        Region 1's Tempo line still shows the score's notated marking, so
        the two numbers can legitimately differ for a score whose marking
        unit is not its TS denominator."""
        effective_str = self._format_tempo_number(self.playback_tempo_display_bpm())
        unit = f"{self.tempo_display_beat_unit_name_at()} notes per minute"
        if self.playback_tempo_bpm is None:
            return f"Playback tempo: {effective_str} {unit} (score default)"
        return f"Playback tempo: {effective_str} {unit}"
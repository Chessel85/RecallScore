# main_window.py
import os
import re
import sys
from contextlib import contextmanager
from typing import Optional

from PySide6.QtCore import QLocale, QTimer, QUrl, Qt
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from audio.metronome import click_event_for_beat, click_event_for_symbol
from audio.synth_engine import SynthEngine
from controllers.attribute_controller import AttributeController
from controllers.focus_controller import FocusController
from controllers.keyboard_echo_controller import KeyboardEchoController
from controllers.live_midi_input_controller import LiveMidiInputController
from controllers.navigation_controller import NavigationController
from controllers.playback_controller import PlaybackController
from controllers.region_presenter import RegionPresenter
from controllers.score_edit_controller import ScoreEditController
from controllers.score_persistence import ScorePersistenceController
from controllers.score_session import ScoreSession
from controllers.shortcut_controller import ShortcutController, ShortcutTarget
from controllers.tuner_controller import TunerController
from controllers.voice_control_controller import VoiceControlController
from models.metronome_pattern import default_pattern, snap_time_signature
from models.music_data import MusicData
from models.score_formats import SCORE_FORMATS
from models.vocabulary import bar_word
from parsers.file_signature import precheck as precheck_score_file
from parsers.musescore_reader import (
    clear_musescore_detection_cache,
    find_musescore_executable,
    resolve_musescore_path,
)
from parsers.score_load_error import ScoreLoadError
from parsers.ug_source import write_ug_source
from persistence import app_settings
from widgets import accessible_announcer
from widgets.about_dialog import AboutDialog
from widgets.attribute_order_dialog import AttributeOrderDialog
from widgets.find_dialog import FindDialog
from widgets.goto_measure_dialog import GotoMeasureDialog
from widgets.instrument_dialog import InstrumentDialog
from widgets.key_signature_dialog import KeySignatureDialog
from widgets.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from widgets.live_midi_input_dialog import LiveMidiInputDialog
from widgets.menu_builder import MenuBuilder, goto_measure_action_text
from widgets.metronome_player_dialog import MetronomePlayerDialog
from widgets.mixer_dialog import MixerDialog
from widgets.part_order_dialog import PartOrderDialog
from widgets.performance_report_dialog import PerformanceReportDialog
from widgets.play_settings_dialog import PlaySettingsDialog
from widgets.region1_list_widget import Region1ListWidget
from widgets.region1_section_tab_bar import Region1SectionTabBar
from widgets.region2_list_widget import Region2ListWidget
from widgets.region2_manager import node_breadcrumb
from widgets.region4_list_widget import Region4ListWidget
from widgets.region5_list_widget import Region5ListWidget
from widgets.status_bar_widget import StatusBarWidget
from widgets.strumming_dialog import StrummingDialog
from widgets.timeline_list_widget import TimelineListWidget
from widgets.tuner_dialog import TunerDialog
from widgets.tuner_settings_dialog import TunerSettingsDialog
from widgets.ultimate_guitar_import_dialog import UltimateGuitarImportDialog
from widgets.user_notification import notify_user
from widgets.voice_control_dialog import VoiceControlDialog
from widgets.voice_control_test_dialog import VoiceControlTestDialog
from workers.device_enumeration_worker import DeviceEnumerationThread


def detect_default_uk_terms(system_locale: Optional[QLocale] = None) -> bool:
    """F4/D-6: UK is the safe default; only a positively-detected US locale
    switches it. Anything indeterminate (non-English, unresolvable) stays
    UK rather than guessing. Lives here, not models/vocabulary.py, because
    it needs QLocale and models/ stays Qt-free. system_locale is injectable
    so tests are deterministic regardless of the machine."""
    loc = system_locale if system_locale is not None else QLocale.system()
    # PySide6 6.11 exposes the non-deprecated .territory() method, but it
    # still returns the QLocale.Country enum (not a separate Territory enum
    # class, unlike some Qt6 versions/bindings) - verified via introspection.
    return loc.territory() != QLocale.Country.UnitedStates


# Sentinel for _scan_devices_async's `selected` arg: "keep whatever the
# combo currently shows" (a Refresh), as distinct from an explicit None
# ("the default device").
_KEEP_SELECTION = object()


def _app_base_dir() -> str:
    """A data file's parent directory: next to main_window.py (repo root) in
    dev, or the frozen bundle root (sys._MEIPASS) once packaging/
    RecallScore.spec bundles it - same idiom as main.py's _app_icon_path()."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def user_guide_html_path() -> str:
    return os.path.join(_app_base_dir(), "docs", "user_guide.html")


class MainWindow(QMainWindow):
    """The window shell: builds the widgets, owns the controllers, and wires
    them together. Deliberately holds almost no logic of its own.

    The methods below are mostly one-line delegators. They are the stable
    API the region widgets call (via window()) and the tests drive, so they
    stay here as a facade even though the work happens in controllers/.
    """

    # Re-exported so callers (and tests) can name the boundary cue's channel
    # without reaching into the playback controller.
    BOUNDARY_CUE_CHANNEL = PlaybackController.BOUNDARY_CUE_CHANNEL

    def __init__(
        self, synth=None, uk_terms: bool | None = None, live_midi_manager=None,
        voice_control_manager=None, tuner_manager=None,
    ):
        """Create the main window.

        synth: any object with the SynthEngine interface (play_chord /
        play_notes / stop_all_notes / set_program / close). Tests pass a
        stand-in so no audio device opens and they can assert what would
        have sounded.

        uk_terms: startup dialect override. None resolves to the saved
        AppSettings value, falling back to OS-locale detection when nothing
        has ever been saved. An explicit value skips both and is not
        persisted, so tests are deterministic regardless of the machine.

        live_midi_manager: any object with the MidiInputManager interface
        (set_callback / list_ports / open / close / is_open / device_name).
        Tests pass a NullMidiInputManager stand-in so no real MIDI device is
        touched - same reasoning as synth above.

        voice_control_manager: any object with the VoiceRecognitionManager
        interface (set_callback / set_diagnostic_callback / list_devices /
        start / stop / is_running / rebuild_grammar / set_confidence_
        threshold). Tests pass a NullVoiceRecognizer stand-in so no real
        SAPI COM recognizer is touched - same reasoning as live_midi_manager.

        tuner_manager: any object with the TunerCapture interface
        (set_callback / set_target / list_devices / open / close / is_open /
        device_name). Tests pass a NullTunerCapture stand-in so no real
        microphone is touched - same reasoning as live_midi_manager.
        """
        super().__init__()
        self.setWindowTitle("Recall Score")
        self.resize(800, 600)
        # Beat-click timer for the Strumming Patterns dialog's demo; created
        # lazily on first use, kept so _stop_strum_demo can cancel it.
        self._strum_click_timer = None
        self._strum_click_state = {"beat": 0, "total": 0}

        # Tools > Metronome Player remembers its last-used settings for the
        # lifetime of the app session only - re-seeded from the score (or the
        # 4/4 defaults) on the first open, then from this tuple on every
        # later open. Not persisted to disk: a fresh app start forgets it.
        # (numerator, denominator, pattern, tempo_bpm) or None.
        self._metronome_player_state = None

        if uk_terms is None:
            saved_uk_terms = app_settings.load().uk_terms
            uk_terms = (
                saved_uk_terms if saved_uk_terms is not None else detect_default_uk_terms()
            )

        self.session = ScoreSession(
            synth if synth is not None else SynthEngine(), uk_terms, parent=self
        )
        self._live_midi_manager = live_midi_manager
        self._voice_control_manager = voice_control_manager
        self._tuner_manager = tuner_manager
        # In-flight off-the-main-thread device scans for the audio settings
        # dialogs (P1). Each self-removes on finish; closeEvent waits out any
        # that are still running so tearing down the window can't orphan one.
        self._device_scan_threads: list = []

        self.setup_ui()
        self.setup_controllers()
        self.setup_menu()
        self.connect_signals()

        self.region_1.setFocus()

    # --- construction -------------------------------------------------

    def setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        grid_layout = QGridLayout(central_widget)

        # Region 1: score info. The property list is the region proper (it
        # stays `self.region_1` - the stable name widgets and tests drive);
        # a section tab bar is spliced in above it for a multi-section
        # MusicXML score and stays hidden otherwise
        # (UserPlans/MultiSectionScores.md).
        self.region_1 = Region1ListWidget()
        self.region_1.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.region_1_section_tabs = Region1SectionTabBar()

        # Region 2: Parts/Staves/Voices hierarchy, navigated Up/Down, O to toggle
        self.region_2 = Region2ListWidget()
        self.region_2.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        # Region 3: Timeline List
        self.region_3 = TimelineListWidget()
        self.region_3.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.region_3.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        # Region 4: note attributes. Region4ListWidget (not the plain
        # Region1ListWidget-shaped base) adds the Ref 15 AC4 context menu
        # for appending/removing an attribute in Region 3's note display.
        self.region_4 = Region4ListWidget()
        self.region_4.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        # Region 5 (Ref 29, the "Performance region"): duration-spanning
        # markers (repeat barlines, 1st/2nd endings, crescendo/diminuendo
        # hairpins) active at the cursor's current position.
        self.region_5 = Region5ListWidget()
        self.region_5.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        # Each region gets a visible caption above it AND the same name as its
        # widget's accessible name, so NVDA announces it on entry (Tab/
        # Shift+Tab and the Z/X/C/V/B direct-jump actions). A plain QLabel is
        # used rather than a QGroupBox on purpose: a QGroupBox carries the
        # accessibility "grouping" role, so NVDA prefixed every region with
        # "... grouping" (reported). A bare QLabel is not in the tab order and
        # isn't spoken on focus moves, so only the widget's own accessible
        # name is announced.
        def _titled_region(widget, title):
            container = QWidget()
            inner = QVBoxLayout(container)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(2)
            caption = QLabel(title)
            caption.setStyleSheet("font-weight: bold;")
            inner.addWidget(caption)
            inner.addWidget(widget)
            widget.setAccessibleName(title)
            return container

        self.region_1_box = _titled_region(self.region_1, "Score information")
        # caption at 0, list at 1 -> put the section tab bar between them.
        self.region_1_box.layout().insertWidget(1, self.region_1_section_tabs)
        self.region_2_box = _titled_region(self.region_2, "Parts")
        self.region_3_box = _titled_region(self.region_3, "Notes")
        self.region_4_box = _titled_region(self.region_4, "Attributes")
        self.region_5_box = _titled_region(self.region_5, "Performance information")

        # Row 1 = 2 regions, row 2 = 3 - a deliberate departure from the
        # original 2x2 (agreed with the user: consistent region numbering
        # matters far more than visual layout here). A 6-column grid, the
        # LCM of 2 and 3, keeps both rows aligned under one layout.
        grid_layout.addWidget(self.region_1_box, 0, 0, 1, 3)
        grid_layout.addWidget(self.region_2_box, 0, 3, 1, 3)
        grid_layout.addWidget(self.region_3_box, 1, 0, 1, 2)
        grid_layout.addWidget(self.region_4_box, 1, 2, 1, 2)
        grid_layout.addWidget(self.region_5_box, 1, 4, 1, 2)

        grid_layout.setRowStretch(0, 1)
        grid_layout.setRowStretch(1, 1)
        for col in range(6):
            grid_layout.setColumnStretch(col, 1)

        # A real QMainWindow status bar, so NVDA+End ("report status bar")
        # works through Qt's native accessibility role.
        self.status_bar = StatusBarWidget()
        self.setStatusBar(self.status_bar)

        self.setup_shortcuts()

    def setup_shortcuts(self):
        """WindowShortcut fires regardless of which child widget has focus,
        which is what's wanted, without ApplicationShortcut's app-wide scope
        - that causes ambiguous-shortcut conflicts between MainWindow
        instances alive in the same QApplication.

        Ctrl+M/Ctrl+P/Ctrl+G/Ctrl+A have no QShortcut here: their menu
        actions carry the shortcut themselves. Ctrl+A in particular is
        Edit > Select All (widgets/menu_builder.py) - do not re-add it as a
        bare QShortcut here; it is gated to the Note region only by
        FocusController the same way Home/End already are.
        """
        def window_shortcut(sequence, slot):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
            return shortcut

        # C7: F6/Shift+F6 toggle between the regions area (restoring the
        # last-focused region) and the status bar. Menu bar access stays on
        # the OS's native Alt mechanism.
        self.f6_shortcut = window_shortcut(Qt.Key.Key_F6, self._toggle_pane)
        self.shift_f6_shortcut = window_shortcut("Shift+F6", self._toggle_pane)

        # Tempo controls (Ref 12) are global, not Note-region-scoped like
        # arrow-key navigation: they adjust a playback-wide setting rather
        # than a per-row position. Playback transport is global for the
        # same reason.
        self.tempo_faster_shortcut = window_shortcut(Qt.Key.Key_F, self.tempo_faster)
        self.tempo_slower_shortcut = window_shortcut(Qt.Key.Key_S, self.tempo_slower)
        self.tempo_reset_shortcut = window_shortcut(Qt.Key.Key_D, self.tempo_reset)
        # Space/Ctrl+Space are bound via the Playback menu's play_stop/
        # pause_resume QAction shortcuts instead of a QShortcut here - two
        # bindings for the same key sequence in the same WindowShortcut
        # context would be ambiguous and neither would fire. Same pattern
        # Ctrl+M/Ctrl+P/Ctrl+G already use.

        # Ref 13: re-trigger the chord at the cursor on demand. No held-key
        # tracking needed - AC2's "hold for the marked length" is already
        # each note's own duration, and "or pressed again" is a plain
        # retrigger, which play_chord's default already handles.
        self.chord_audition_shortcut = window_shortcut(
            "Shift+Space", self._audition_current_selection
        )

        # Ref 6: typing a bar number then Enter jumps to it. Global, like the
        # transport and tempo shortcuts above and unlike arrow-key
        # navigation - a bar jump is a position-wide action, not a per-row
        # one, so it should work from any region or the status bar. Bare
        # digits are safe window-wide here: no region uses digit type-ahead
        # for anything meaningful (the rows are part/staff/voice names and
        # note text), and Ctrl+digit in the Note region is a separate combo.
        # The digits accumulate on NavigationController; Enter (a hidden
        # window QAction routing through audition_phrase()) commits a bar
        # number, Ctrl+Enter commits it as the loop length, Escape cancels a
        # half-typed number. Numpad digits arrive with
        # KeypadModifier and are not bound (they weren't before either).
        self._digit_shortcuts = [
            window_shortcut(
                Qt.Key(Qt.Key.Key_0 + d),
                lambda d=d: self.navigation.append_pending_digit(str(d)),
            )
            for d in range(10)
        ]
        # A lambda, not a bound-method reference: setup_shortcuts() runs
        # before setup_controllers() creates self.navigation.
        self._cancel_digits_shortcut = window_shortcut(
            Qt.Key.Key_Escape, lambda: self.navigation.clear_pending_digits()
        )
        # Ctrl+Enter/Ctrl+Return: commit a typed number as the LOOP LENGTH
        # (instead of Enter's jump-to-bar). Global like the digit buffer
        # itself. Numpad Ctrl+Enter arrives as Key_Enter, main keyboard as
        # Key_Return - both bound.
        self._commit_loop_length_shortcuts = [
            window_shortcut("Ctrl+Enter", lambda: self.commit_loop_length()),
            window_shortcut("Ctrl+Return", lambda: self.commit_loop_length()),
        ]

    def setup_controllers(self):
        regions = [self.region_1, self.region_2, self.region_3, self.region_4, self.region_5]

        self.playback = PlaybackController(self.session, parent=self)
        # Lead-in/looping is a global preference (all scores), so it is
        # loaded once here rather than per file load - unlike the absolute
        # playback tempo, which travels with the score's own .rsc config.
        self.playback.set_play_settings(app_settings.load().play)
        # Live MIDI input (device/instrument/volume/pan) is likewise global,
        # not per-score - constructed once here, outliving every file load,
        # the same lifetime ScoreSession/SynthEngine already have. .start()
        # auto-connects to the last-used device if enabled and present this
        # session; degrades silently otherwise.
        self.live_midi = LiveMidiInputController(
            self.session.synth, parent=self, midi_manager=self._live_midi_manager,
        )
        self.live_midi.start()
        self.navigation = NavigationController(self.session, parent=self)
        # Hands-free voice control (Ref 19): recognized commands call
        # straight into navigation/playback, so it's constructed once both
        # exist. Global like live_midi above, for the same reasoning -
        # confirmed with the user. .start() auto-starts listening if enabled
        # and pywin32/SAPI are available; degrades silently otherwise.
        self.voice_control = VoiceControlController(
            self.session.synth, self.navigation, self.playback, parent=self,
            voice_manager=self._voice_control_manager,
        )
        self.voice_control.start()
        # Tools > Tuner (speculative feature): constructed once here for the
        # same lifetime reasoning as live_midi/voice_control above, but does
        # NOT auto-start listening - the dialog itself starts/stops capture on
        # show/close (no explicit Start/Stop Listening control).
        self.tuner = TunerController(parent=self, capture=self._tuner_manager)
        self.focus = FocusController(self, regions, self.status_bar)
        self.presenter = RegionPresenter(
            self.session, self.region_1, self.region_2, self.region_3,
            self.region_4, self.region_5, self.status_bar,
            playback_status_fields=self.playback.status_fields,
            region_1_section_tabs=self.region_1_section_tabs,
            parent=self,
        )
        # While it is visible the section tab bar joins the Tab/Shift+Tab
        # cycle as the stop just ahead of Region 1's list.
        self.focus.region_1_extra_stop = self.region_1_section_tabs
        self.attributes = AttributeController(self.session, self.presenter, self)
        # S5: the score-data edits behind the Instruments, Key Signature and
        # Reorder Parts dialogs. Built after the presenter, which it drives
        # for every Region 2 label/order change - this controller touches no
        # widgets itself.
        self.score_edit = ScoreEditController(self.session, self.presenter)
        self.persistence = ScorePersistenceController(self.session, self.region_2)
        # Wired here rather than through VoiceControlController's own
        # constructor: RegionPresenter doesn't exist yet at that point in
        # this method (see its own construction above). The "attribute N"
        # voice command dispatches through this reference - see
        # VoiceControlController._dispatch and RegionPresenter.
        # announce_attribute_by_number.
        self.voice_control.presenter = self.presenter
        # Deferred for the same reason: NavigationController.select_section
        # (multi-section scores) redraws Region 1 and Region 5 through the
        # presenter, which doesn't exist when navigation is constructed.
        self.navigation.presenter = self.presenter

        self.focus.connect_tracking()

    def setup_menu(self):
        # The menu's QActions are reached as self._actions.<name> everywhere
        # (production and tests). MenuBuilder.Actions is the one list of them;
        # the window keeps no per-action aliases of its own.
        self._actions = MenuBuilder(self, self, self.session.uk_terms).build()

        # Global (AppSettings.play), not per-score - the lead-in toggle is
        # checkable and set once here from the loaded settings, kept in sync
        # by toggle_lead_in. The play-mode action is a non-checkable cycle
        # (three states), so it carries no checked state of its own.
        self._actions.lead_in_toggle.setChecked(self.playback.play_settings.lead_in_enabled)
        # Global (AppSettings), not per-score like the metronome/position-
        # announcer toggles - set once here, never re-set on score load.
        self._actions.live_midi_input.setChecked(self.live_midi.settings.enabled)
        # Same reasoning as live_midi_input above.
        self._actions.voice_control.setChecked(self.voice_control.settings.enabled)

        self.persistence.clear_action = self._actions.clear_preferences
        self.persistence.refresh_clear_action()
        self.focus.first_measure_action = self._actions.first_measure
        self.focus.last_measure_action = self._actions.last_measure
        self.focus.select_all_action = self._actions.select_all
        self.focus.update_navigation_actions_enabled()
        self.focus.mute_action = self._actions.mute
        self.focus.solo_action = self._actions.solo
        self.focus.unmute_all_action = self._actions.unmute_all
        self.focus.unsolo_all_action = self._actions.unsolo_all
        self.focus.update_region2_actions_enabled()

        self.recent_files_menu = self._actions.recent_files_menu
        self._refresh_recent_files_menu()

        # Both the menu QActions and the four window-level QShortcuts below
        # already exist by now (setup_shortcuts runs during setup_ui, before
        # setup_controllers/setup_menu) - see UserPlans/KeyboardShortcuts.md.
        self.shortcuts = ShortcutController(
            self, self._actions, self._keyboard_only_shortcut_targets()
        )
        self.keyboard_echo = KeyboardEchoController(
            self, self.shortcuts, self._actions.keyboard_echo_mode, "keyboard_echo_mode"
        )

    def _keyboard_only_shortcut_targets(self) -> list:
        """The four window-level QShortcuts (Ref 12/13) that aren't menu
        QActions but are still single, rebindable commands - the "Keyboard
        only" category in the dialog. QShortcut.key()/setKey() take a single
        QKeySequence, not a list, so each target wraps them to match
        ShortcutTarget's get/set -> List[QKeySequence] contract."""
        def _target(id_, label, shortcut):
            def get():
                key = shortcut.key()
                return [] if key.isEmpty() else [key]

            def set_(seqs):
                shortcut.setKey(seqs[0] if seqs else QKeySequence())

            return ShortcutTarget(
                id=id_, category="Keyboard only", name=lambda: label, get=get, set=set_
            )

        return [
            _target("tempo_faster", "Tempo Faster", self.tempo_faster_shortcut),
            _target("tempo_slower", "Tempo Slower", self.tempo_slower_shortcut),
            _target("tempo_reset", "Reset Tempo", self.tempo_reset_shortcut),
            _target("chord_audition", "Play Selected Notes", self.chord_audition_shortcut),
        ]

    def connect_signals(self):
        """The one place the controllers are joined up. Each is otherwise
        unaware of the others."""
        self.session.score_loaded.connect(self._on_score_loaded)
        self.session.load_failed.connect(self._on_score_load_failed)

        # Both "the cursor moved" sources land on the same redraw.
        self.navigation.position_changed.connect(self.presenter.update_timeline_views)
        self.navigation.boundary_hit.connect(self.playback.play_boundary_cue)
        self.navigation.barline_crossed.connect(self.playback.play_barline_indicator)
        self.navigation.pending_digits_changed.connect(self.presenter.show_pending_digits)
        self.playback.cursor_moved.connect(self.presenter.update_timeline_views)
        self.playback.status_text_changed.connect(self.presenter.update_status_bar)
        self.playback.playback_state_changed.connect(
            self.presenter.update_playback_status_field
        )
        # Tools > Metronome Player is a standalone dialog that must not open
        # mid-playback (it seeds from, and clicks alongside nothing - but the
        # synth is busy). Grey it out whenever a play run is active.
        self.playback.playback_state_changed.connect(
            self._refresh_metronome_player_action_enabled
        )
        self._refresh_metronome_player_action_enabled()

        # Emitted from inside update_timeline_views, and delivered
        # synchronously, so the notes still sound before the performance cue.
        self.presenter.audition_requested.connect(self._audition_current_selection)

        # Multi-section MusicXML: the Region 1 tab bar emits intent; the
        # section-switch logic lives in NavigationController (invariant 5).
        # currentChanged is blocked while set_sections rebuilds the tabs on
        # load, so this cannot re-enter select_section from that path.
        self.region_1_section_tabs.section_selected.connect(
            self._on_section_tab_selected
        )

        self.region_2.filter_changed.connect(self.presenter.on_region_2_filter_changed)
        self.region_3.itemSelectionChanged.connect(
            self.presenter.on_region_3_selection_changed
        )

        # S6: the Note and Performance regions emit intent rather than
        # reaching back through self.window() - wired here like
        # region_2.filter_changed above.
        self.region_3.navigate_requested.connect(self.navigation.navigate)
        self.region_3.vertical_move_made.connect(self.on_region_3_vertical_move)
        self.region_3.loop_length_adjust_requested.connect(self._adjust_loop_length)
        self.region_3.attribute_number_requested.connect(
            self.presenter.announce_attribute_by_number
        )
        self.region_5.span_jump_requested.connect(self._jump_to_performance_span)
        self.region_4.context_menu_requested.connect(self.show_region_4_attribute_menu)

    # --- state exposed for the widgets and tests ----------------------

    @property
    def _music_data(self):
        return self.session.music_data

    @property
    def synth(self):
        return self.session.synth

    @property
    def sequencer(self):
        return self.playback.sequencer

    @property
    def _uk_terms(self) -> bool:
        return self.session.uk_terms

    @property
    def _load_thread(self):
        return self.session.load_thread

    @property
    def _last_focused_region(self):
        return self.focus.last_focused_region

    @property
    def _focus_tracking_connected(self) -> bool:
        return self.focus.tracking_connected

    # --- loading -------------------------------------------------------

    def open_file_dialog(self):
        self._open_score_file_dialog(start_dir=app_settings.load().last_open_dir or "")

    def _open_score_file_dialog(self, start_dir: str):
        # Only offer .mscz/.mscx when a MuseScore 4 executable can actually
        # be found - otherwise picking one just fails later on the load
        # thread with a silent print. The expensive probes inside are
        # memoised for the process (and warmed off-thread at startup), so
        # this is cheap on every open after the first; Options > Set
        # MuseScore Location... clears that cache, so the option reappears
        # with no restart.
        external_tool_available = (
            find_musescore_executable(app_settings.load().musescore_path) is not None
        )
        # S4: built from models/score_formats.py so the extension lists live
        # in one place. A format that requires_external_tool is only offered
        # once that tool is found (MuseScore's CLI); every other format is
        # always offered. Ask the format, never its key.
        included = [
            fmt
            for fmt in SCORE_FORMATS
            if not fmt.requires_external_tool or external_tool_available
        ]

        def _globs(fmt):
            return " ".join(f"*{ext}" for ext in fmt.extensions)

        combined = " ".join(_globs(fmt) for fmt in included)
        filters = [f"Score Files ({combined})"]
        filters += [f"{fmt.dialog_label} ({_globs(fmt)})" for fmt in included]
        filters.append("All Files (*)")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Score",
            start_dir,
            ";;".join(filters),
        )
        if file_path:
            self.load_score_from_file(file_path)

    def load_score_from_file(self, file_path: str):
        if self.session.is_loading():
            return
        # Fail fast, before anything is saved or swapped: a missing / empty /
        # unreadable file, or one whose contents don't match its extension,
        # is reported now and leaves the current score (and its .rsc)
        # completely untouched.
        try:
            precheck_score_file(file_path)
        except ScoreLoadError as e:
            self._show_load_error(e.user_message)
            return
        self._save_current_score_config()
        self.session.load(file_path)

    def close_score(self):
        """File > Close: commit the loaded score's .rsc, then blank the
        window back to how it looks before any file is opened - without
        quitting the app.

        Cross-controller orchestration, so it lives in the shell alongside
        _on_score_loaded (its rough inverse). A no-op with nothing loaded,
        or while a load is still in flight - the same guards
        load_score_from_file uses. The config must be written before the
        score is dropped (persistence reads session.music_data), so the
        order here is load-bearing the way _on_score_loaded's is."""
        if self._music_data is None or self.session.is_loading():
            return
        self._save_current_score_config()

        self.playback.detach_score()
        self.session.close()

        self.setWindowTitle("Recall Score")
        self._actions.close.setEnabled(False)
        self._actions.select_section.setEnabled(False)
        self._actions.strumming.setEnabled(False)
        self._actions.save_ug_import.setEnabled(False)
        # Reverts "go to bar N"'s vocabulary to nothing score-specific -
        # go_to_bar_phrases(0) is []. Safe whether or not voice control is
        # currently listening (see _on_score_loaded's own call).
        self.voice_control.rebuild_grammar(0)
        # A find target is just a (category, key) tag, not a reference into
        # the old score, but "back to first run" means nothing is armed.
        self.navigation.current_find_target = None

        self.presenter.clear_all()
        self.persistence.refresh_clear_action()
        self._actions.metronome.setChecked(False)
        self._actions.position_announcer.setChecked(False)
        self._actions.bar_line_indicator.setChecked(False)

        self.region_1.setFocus()

    def open_ultimate_guitar_import_dialog(self):
        """Experimental (feature/ug-import): File > Import from Ultimate
        Guitar... - no self._music_data guard, same as open_file_dialog,
        since this is a loading action that works with no score loaded
        yet."""
        dialog = UltimateGuitarImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_ultimate_guitar_url(dialog.url())

    def load_ultimate_guitar_url(self, url: str):
        if self.session.is_loading():
            return
        self._save_current_score_config()
        self.session.import_from_url(url)

    def save_ultimate_guitar_import_as(self):
        """Experimental (feature/ug-import): File > Save Ultimate Guitar
        Import As... - the app's first-ever save capability, deliberately
        scoped to just this one format (MusicXML/MIDI/GP files are already
        real files on disk; there's nothing to "save" there). Always
        prompts for a location rather than a silent-overwrite Save, to keep
        this first save path simple.

        After writing, the score behaves exactly like a file that was
        opened normally: file_path becomes the real saved path, so .rsc
        persistence/the window title/Edit > Open Local Folder all key off
        it the same way every other format already does."""
        if not self._music_data or not self._music_data.is_ug:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Ultimate Guitar Import",
            self._suggested_ug_filename(self._music_data),
            "Recall Score UG Import Files (*.ug)",
        )
        if not file_path:
            return
        write_ug_source(self._music_data.ug_source, file_path)
        self._music_data.file_path = file_path
        self.setWindowTitle(self._window_title_for(self._music_data))
        self.persistence.refresh_clear_action()
        self._save_current_score_config()
        app_settings.add_recent_file(file_path)
        self._refresh_recent_files_menu()

    def _refresh_recent_files_menu(self):
        """Rebuilds File > Recent Files from AppSettings - called on
        startup and again after every successful load/save, since either
        can change the list. A stale entry (moved/deleted since) is not
        specially detected or pruned here - clicking it just fails the same
        way opening any other missing file would, through the existing
        load_failed path."""
        menu = self.recent_files_menu
        menu.clear()
        recent_files = app_settings.load().recent_files
        if not recent_files:
            placeholder = QAction("No recent files", self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)
            return
        for file_path in recent_files:
            # Filename first, then its folder in brackets (P5) - the name is
            # what the user recognises. "&" -> "&&" so a real filename
            # containing one isn't eaten as a QAction mnemonic.
            base = os.path.basename(file_path)
            folder = os.path.dirname(file_path)
            label = (f"{base} ({folder})" if folder else base).replace("&", "&&")
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, p=file_path: self.load_score_from_file(p))
            menu.addAction(action)

    @staticmethod
    def _window_title_for(music_data) -> str:
        """A UG import shows its song / artist / Ultimate Guitar ID rather
        than a filename (a live URL import's file_path is only a synthetic
        slug); every other format shows its real filename."""
        if music_data.is_ug and music_data.ug_source is not None:
            s = music_data.ug_source
            return f"Recall Score - {s.song_name} - {s.artist_name} ({s.tab_id})"
        return f"Recall Score - {os.path.basename(music_data.file_path)}"

    @staticmethod
    def _suggested_ug_filename(music_data) -> str:
        """Prefill for File > Save Ultimate Guitar Import As... - song,
        artist and ID, with characters illegal in a Windows filename
        stripped."""
        s = music_data.ug_source
        raw = f"{s.song_name} - {s.artist_name} - {s.tab_id}.ug"
        return re.sub(r'[<>:"/\\|?*]', "", raw).strip()

    def _on_score_loaded(self, music_data):
        """Orchestration only - which is why it stays in the shell. The order
        matters: the saved config has to be applied to MusicData before the
        regions render, and Region 2's own per-node toggles have to be in
        effect before the first audition, or the opening chord includes
        voices the user had switched off."""
        self.setWindowTitle(self._window_title_for(music_data))
        self._actions.close.setEnabled(True)
        self._actions.select_section.setEnabled(music_data.has_multiple_sections)
        self._actions.strumming.setEnabled(bool(music_data.ug_strum_patterns))
        self._actions.save_ug_import.setEnabled(bool(music_data.is_ug))

        # Ref 19: "go to bar N"'s numeric vocabulary is bounded to this
        # score's own real measure numbers - see audio/voice_commands.
        # go_to_bar_phrases. Safe to call regardless of whether voice
        # control is currently enabled/listening - a no-op grammar rebuild
        # request queued for a stopped recognizer is simply picked up by the
        # next start().
        self.voice_control.rebuild_grammar(music_data.total_measures)

        # A URL-imported UG score's file_path is a synthetic slug with
        # nothing on disk at it (see UgReader) - os.path.exists naturally
        # excludes that case without needing to special-case is_ug here.
        if os.path.exists(music_data.file_path):
            app_settings.add_recent_file(music_data.file_path)
            app_settings.set_last_open_dir(os.path.dirname(music_data.file_path))
            self._refresh_recent_files_menu()

        saved_config = self.persistence.load_for_current()
        if saved_config is not None:
            music_data.apply_config(saved_config)
        self.persistence.refresh_clear_action()

        self.presenter.reset_performance_labels()
        self.playback.attach_score(music_data)

        # Suppress the initial audition when there's a config to restore,
        # and fire it once Region 2's restored state is actually in effect -
        # otherwise the first sound heard on load includes voices that were
        # saved as off, even though every later move excludes them.
        self._update_ui_regions(play_all=saved_config is None)
        if saved_config is not None:
            self.region_2.apply_muted_node_keys(
                saved_config.parts_muted, saved_config.staves_muted, saved_config.voices_muted
            )
            self.region_2.apply_soloed_node_keys(
                saved_config.parts_soloed, saved_config.staves_soloed, saved_config.voices_soloed
            )
            self._audition_current_selection()

    def _on_score_load_failed(self, error_text: str):
        print(f"[ERROR] Failed to load score file: {error_text}")
        self._show_load_error(error_text)

    def _show_load_error(self, message: str):
        """The one accessible surface for a load failure (Ref 25 / NFR-06).
        A native QMessageBox: it takes focus and is read aloud by NVDA and
        VoiceOver with no extra work, and the previously-loaded score is
        left exactly as it was."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Could not open score")
        box.setText(message)
        offer_musescore_picker = (
            "MuseScore" in message and "was not found" in message
        )
        if offer_musescore_picker:
            set_location = box.addButton(
                "Set MuseScore Location...", QMessageBox.ButtonRole.ActionRole
            )
            box.addButton(QMessageBox.StandardButton.Ok)
            box.setDefaultButton(set_location)
        else:
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        if offer_musescore_picker and box.clickedButton() is set_location:
            self.set_musescore_location()

    def _update_ui_regions(self, play_all: bool = True):
        if not self._music_data:
            return
        self.presenter.refresh_region_1()
        self.region_2.load_score_structure(
            self._music_data.get_score_structure(),
            collapse_to_parts=self._music_data.collapsed_part_ids,
        )
        self._actions.metronome.setChecked(self._music_data.metronome_enabled)
        self._actions.position_announcer.setChecked(self._music_data.position_announcer_enabled)
        self._actions.bar_line_indicator.setChecked(self._music_data.bar_line_indicator_enabled)
        self.presenter.update_timeline_views(play_all=play_all)

    # --- navigation (delegators) --------------------------------------

    def navigate_timeline_home(self):
        self.navigation.timeline_home()

    def navigate_timeline_end(self):
        self.navigation.timeline_end()

    def navigate_to_typed_measure(self, digits: str):
        self.navigation.to_typed_measure(digits)

    def jump_to_performance_span_start(self):
        self.navigation.jump_to_span(self.region_5.current_row_data(), is_start=True)

    def jump_to_performance_span_end(self):
        self.navigation.jump_to_span(self.region_5.current_row_data(), is_start=False)

    def _jump_to_performance_span(self, is_start: bool):
        """Slot for Region5ListWidget.span_jump_requested (S6): the widget
        no longer calls the two methods above directly."""
        if is_start:
            self.jump_to_performance_span_start()
        else:
            self.jump_to_performance_span_end()

    def find_next(self):
        self.navigation.find_next()

    def find_previous(self):
        self.navigation.find_previous()

    def next_section(self):
        self.navigation.next_section()

    def previous_section(self):
        self.navigation.previous_section()

    # --- playback (delegators) ----------------------------------------

    def toggle_play_stop(self):
        self.playback.toggle_play_stop()

    def toggle_pause_resume(self):
        self.playback.toggle_pause_resume()

    def toggle_play_metronome(self):
        self.playback.toggle_play_metronome()

    def audition_phrase(self):
        # Enter/Return now only commits a typed bar number (Preview is
        # gone - Space is the single play control). Kept named
        # audition_phrase because the menu_builder slot and tests reference
        # it by that name.
        self.navigation.commit_pending_digits()

    def commit_loop_length(self):
        """Ctrl+Enter/Ctrl+Return: a typed number becomes the loop length,
        not a bar jump. With looping off it would silently do nothing, which
        reads as "broken" to a screen-reader user - so it speaks "Looping is
        off" and clears the buffer instead."""
        digits = self.navigation.pending_digits
        if not digits:
            return
        if not self.playback.play_settings.loop_enabled:
            accessible_announcer.announce(self.region_3, "Looping is off")
            self.navigation.clear_pending_digits()
            return
        n = int(digits)
        self.playback.set_loop_length_bars(n)
        self.navigation.clear_pending_digits()
        self.presenter.announce_loop_length(self.playback.play_settings.loop_length_bars)

    def cycle_play_mode(self):
        """Ctrl+L: rotate play to end -> play loop once -> play loop until
        stopped. Non-checkable (three states), so the new mode is spoken
        aloud - the only other trace is the (unfocused) status bar."""
        mode = self.playback.cycle_play_mode()
        self.presenter.announce_play_mode(mode)

    def toggle_lead_in(self):
        self._actions.lead_in_toggle.setChecked(self.playback.toggle_lead_in())

    def cycle_loop_repeat_mode(self):
        """Ctrl+R: rotate how a repeat barline clipped by the loop window is
        read. Like commit_loop_length, it announces why nothing happened
        when it can't apply - looping off, or a score with no repeats -
        rather than silently doing nothing to a screen-reader user."""
        if not self.playback.play_settings.loop_enabled:
            accessible_announcer.announce(self.region_3, "Looping is off")
            return
        if not (self._music_data and self._music_data.repeat_spans):
            accessible_announcer.announce(self.region_3, "This score has no repeats")
            return
        mode = self.playback.cycle_loop_repeat_mode()
        self.presenter.announce_loop_repeat_mode(mode)

    def increase_loop_length(self):
        """Alt+PageUp in the Note region. Persisted globally right away,
        like Play Settings' own OK - a bar count set this way is a practice
        habit, not a per-score value. Announces the new length aloud since
        nothing else does - see RegionPresenter.announce_loop_length.
        adjust_loop_length_bars persists globally itself now."""
        self.playback.adjust_loop_length_bars(1)
        self.presenter.announce_loop_length(self.playback.play_settings.loop_length_bars)

    def decrease_loop_length(self):
        """Alt+PageDown counterpart of increase_loop_length."""
        self.playback.adjust_loop_length_bars(-1)
        self.presenter.announce_loop_length(self.playback.play_settings.loop_length_bars)

    def _adjust_loop_length(self, delta: int):
        """Slot for TimelineListWidget.loop_length_adjust_requested (S6):
        +1 from Alt+PageUp, -1 from Alt+PageDown."""
        self.increase_loop_length() if delta > 0 else self.decrease_loop_length()

    def toggle_mute_current_region2_row(self):
        self.region_2.toggle_mute_current()

    def toggle_solo_current_region2_row(self):
        self.region_2.toggle_solo_current()

    def unmute_all_region2(self):
        self.region_2.unmute_all()

    def unsolo_all_region2(self):
        self.region_2.unsolo_all()

    def tempo_faster(self):
        self.playback.tempo_faster()
        self.presenter.announce_tempo()

    def tempo_slower(self):
        self.playback.tempo_slower()
        self.presenter.announce_tempo()

    def tempo_reset(self):
        self.playback.tempo_reset()
        self.presenter.announce_tempo()

    def toggle_metronome(self):
        self._actions.metronome.setChecked(self.playback.toggle_metronome())

    def toggle_position_announcer(self):
        self._actions.position_announcer.setChecked(
            self.playback.toggle_position_announcer()
        )

    def toggle_bar_line_indicator(self):
        """Ctrl+B: on/off for the bar-line-crossing beep. Spoken aloud
        (a bare shortcut, so the checkable menu item's own state change
        isn't heard). Per-score - saved in the .rsc via MusicData.export_
        config, like the metronome and position announcer toggles."""
        enabled = self.playback.toggle_bar_line_indicator()
        self._actions.bar_line_indicator.setChecked(enabled)
        accessible_announcer.announce(
            self.region_3,
            f"Bar line indicator {'on' if enabled else 'off'}",
        )

    def toggle_live_midi_input(self):
        self._actions.live_midi_input.setChecked(self.live_midi.toggle_enabled())

    def toggle_voice_control(self):
        self._actions.voice_control.setChecked(self.voice_control.toggle_enabled())

    def _audition_current_selection(self, with_position_cues: bool = True):
        self.playback.audition_selection(
            self.presenter.selected_region_3_indices(),
            with_position_cues=with_position_cues,
        )

    def select_all_region_3(self):
        self.presenter.select_all_region_3()

    def on_region_3_vertical_move(self):
        # An in-slice Up/Down still cancels a half-typed bar number, the
        # same as any real cursor move (NavigationController clears it for
        # Left/Right/Home/End/Find).
        self.navigation.clear_pending_digits()
        # An Up/Down within the current slice is not a timeline move, so it
        # sounds the note only - no metronome click, no spoken beat position
        # (both would just repeat at the same position).
        self._audition_current_selection(with_position_cues=False)

    # --- focus (delegators) -------------------------------------------

    def focus_next_region(self, current):
        self.focus.focus_next(current)

    def focus_previous_region(self, current):
        self.focus.focus_previous(current)

    def _toggle_pane(self):
        self.focus.toggle_pane()

    def _navigation_menu_first_measure(self):
        self.navigate_timeline_home()
        self.region_3.setFocus()

    def _navigation_menu_last_measure(self):
        self.navigate_timeline_end()
        self.region_3.setFocus()

    def _navigation_menu_move_to_notes(self):
        self.region_3.setFocus()

    def _navigation_menu_move_to_metadata(self):
        # Z lands on the section tab bar when it is showing (a multi-section
        # score), on the property list otherwise.
        if self.region_1_section_tabs.isHidden():
            self.region_1.setFocus()
        else:
            self.region_1_section_tabs.setFocus()

    def _on_section_tab_selected(self, index: int):
        """Region 1's section tab bar changed. Wiring only - the switch
        logic is NavigationController's. announce=False: the tab bar's own
        NVDA "tab, N of M" already covers it."""
        self.navigation.select_section(index, announce=False)

    def _navigation_menu_select_section(self):
        """Navigation > Select Section...: just moves focus to the Region 1
        section tab bar (the control and the display both). Enabled only for
        a multi-section score, so the bar is always visible when this runs."""
        self.region_1_section_tabs.setFocus()

    def _navigation_menu_move_to_parts(self):
        self.region_2.setFocus()

    def _navigation_menu_move_to_attributes(self):
        self.region_4.setFocus()

    def _navigation_menu_move_to_performance(self):
        self.region_5.setFocus()

    # --- attributes (delegators) --------------------------------------

    def show_region_4_attribute_menu(self, row: int, global_pos):
        self.attributes.show_menu(row, global_pos)

    def _show_attribute_order_dialog(self):
        """Ref 15 AC4: scoped to whichever part/staff/voice Region 2 has
        selected."""
        node = self.attributes.scope_node()
        if node is None:
            return
        with self._preserving_focus():
            dialog = AttributeOrderDialog(
                self,
                pairs=self.attributes.order_pairs_for_node(node),
                scope_description=node_breadcrumb(node),
                initial_attribute_key=self.attributes.current_region_4_attribute_key(),
            )
            dialog.add_remove_requested.connect(
                lambda attribute_key: self.attributes.show_order_menu(dialog, node, attribute_key)
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.attributes.apply_order(node, dialog.ordered_keys())

    def _show_part_order_dialog(self):
        """Reported: NVDA reads whichever part's row Region 3 lands on
        first (always row 0 - see RegionPresenter.update_timeline_views's
        setCurrentRow(0, NoUpdate)) after every navigation step. This lets
        the user choose that order directly - most relevant for a UG
        import's Chords/Lyrics parts, but works for any multi-part score.

        Applying goes through MusicData.reorder_parts (the note-order
        half) and Region2ListWidget.reorder_parts (the Region 2 row-order
        half, an in-place reorder - NOT load_score_structure, which would
        reset every on/off toggle back to enabled).

        User-requested: the dialog opens pre-selected on whichever part
        Region 2's current selection belongs to (a staff/voice node's own
        part_id, not just a part row's), and Region 2's selection is
        restored to that exact node afterward regardless of Accept/Cancel
        - reorder_parts repositions the part's QTreeWidgetItem rather than
        rebuilding it, but leaves the tree's own "current item" undefined
        in the process, so without this the selection would land wherever
        Qt happens to leave it rather than following the part. Which
        widget actually holds keyboard focus is untouched here -
        _preserving_focus() below already restores that to wherever it
        was before the dialog opened, same as every other dialog."""
        if not self._music_data:
            return
        node = self.region_2.current_node()
        initial_part_id = node.part_id if node is not None else None
        selected_node_id = node.node_id if node is not None else None
        with self._preserving_focus():
            dialog = PartOrderDialog(
                self, parts=self.score_edit.part_rows(), initial_part_id=initial_part_id
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.score_edit.reorder_parts(dialog.part_order())
            if selected_node_id is not None:
                self.region_2.select_node(selected_node_id)

    def _show_strumming_dialog(self):
        """Tools > Strumming Patterns... (P2/P3) - a read-only view of a UG
        import's decoded pattern(s). Pure view: it emits
        play_pattern_requested / stop_requested / tempo_changed and this
        method drives the synth (demo playback, looped by the dialog's own
        timer) and the score's playback tempo. Anything currently sounding
        is stopped on close."""
        if not self._music_data or not self._music_data.ug_strum_patterns:
            return
        data = self._music_data
        default_display = data.tempo_bpm / data.tempo_beat_unit_quarter_length
        with self._preserving_focus():
            dialog = StrummingDialog(
                self,
                patterns=data.ug_strum_patterns,
                current_tempo_bpm=data.playback_tempo_display_bpm(),
                default_tempo_bpm=default_display,
            )
            dialog.play_pattern_requested.connect(
                lambda index: self._demo_strum_pattern(index, dialog.include_click())
            )
            dialog.stop_requested.connect(self._stop_strum_demo)
            dialog.tempo_changed.connect(self._on_strum_tempo_changed)
            dialog.exec()
            self._stop_strum_demo()

    def _on_strum_tempo_changed(self, bpm: int):
        """The Strumming dialog's Tempo spin box (and its S/F/D keys) edit
        the score's own playback tempo, so the value the dialog opens on is
        the one the user has already dialled in with the main-window keys."""
        self.playback.set_playback_tempo(float(bpm))
        self.presenter.announce_tempo()

    def _stop_strum_demo(self):
        if self._strum_click_timer is not None:
            self._strum_click_timer.stop()
        self.synth.stop_all_notes()

    def _demo_strum_pattern(self, index: int, with_click: bool = False):
        """Demo-play one strum pattern on the currently selected chord if
        there is one, else a fixed C major - see StrummingDialog. Plays at
        the score's current playback tempo, with an optional metronome
        click on each beat."""
        from audio.strum_schedule import slots_from_codes

        data = self._music_data
        if not data:
            return
        patterns = data.ug_strum_patterns
        if not (0 <= index < len(patterns)):
            return
        pattern = patterns[index]

        channel, program, pitches = 0, 24, [48, 52, 55, 60]
        events = data.get_playback_events_for_indices(
            self.presenter.selected_region_3_indices()
        )
        for event in events:
            if event[2]:
                channel, program, pitches = event[0], event[1], list(event[2])
                break

        slot_ms = pattern.slot_ms_at_bpm(data.effective_tempo_bpm())
        self.synth.play_strum_pattern(
            channel, program, pitches, slots_from_codes(pattern.codes), slot_ms
        )
        self._schedule_strum_clicks(pattern, slot_ms if with_click else None)

    def _schedule_strum_clicks(self, pattern, slot_ms):
        """Fire a metronome click on each beat of the pattern, re-armed each
        loop. Modelled on PlaybackController._sound_play_metronome_beat - a
        re-armed QTimer rather than merging clicks into the strum schedule,
        which is a different synth path (play_click, its own channel and
        soundfont). Not merged with the loop timer either: that fires once
        per whole pattern, this once per beat."""
        if self._strum_click_timer is None:
            self._strum_click_timer = QTimer(self)
            self._strum_click_timer.timeout.connect(self._strum_click_tick)
        self._strum_click_timer.stop()
        if not slot_ms:
            return

        slots_per_beat = max(1, round(pattern.slots_per_bar() / 4))  # 4/4 assumed
        self._strum_click_state = {
            "beat": 0,
            "total": max(1, round(len(pattern.codes) / slots_per_beat)),
        }
        self._strum_click_tick()  # downbeat now, aligned with the first attack
        self._strum_click_timer.start(int(slot_ms * slots_per_beat))

    def _strum_click_tick(self):
        state = self._strum_click_state
        click = click_event_for_beat(float(state["beat"] % 4 + 1))
        if click:
            self.synth.play_click(*click)
        state["beat"] += 1
        if state["beat"] >= state["total"]:
            self._strum_click_timer.stop()

    # --- Metronome Player (Tools menu) -------------------------------

    def _metronome_player_is_blocked(self) -> bool:
        seq = self.sequencer
        return self.playback.is_play_run_active or (seq is not None and seq.is_playing)

    def _refresh_metronome_player_action_enabled(self):
        self._actions.metronome_player.setEnabled(not self._metronome_player_is_blocked())

    def _show_metronome_player_dialog(self):
        """Tools > Metronome Player... (Ctrl+Shift+M) - a standalone practice
        metronome, independent of any loaded score. The first open seeds its
        time signature and tempo from the score at the cursor when one is
        loaded, else 4/4 120 BPM; every later open re-seeds from the settings
        the previous open closed with (_metronome_player_state), for the
        lifetime of the app session only. Pure view: it emits click_requested
        / stopped and this method drives the synth (one-shot clicks on the
        metronome channel). Construction stays here so tests can monkeypatch
        main_window.MetronomePlayerDialog."""
        if self._metronome_player_is_blocked():
            return  # belt-and-braces; the action is already greyed out
        if self._metronome_player_state is not None:
            num, den, pattern, tempo = self._metronome_player_state
        else:
            num, den, tempo = 4, 4, 120
            if self._music_data:
                slice_ = self._music_data.get_current_slice()
                if slice_ is not None and slice_.time_sig:
                    num, den = snap_time_signature(*slice_.time_sig)
                tempo = int(round(self._music_data.playback_tempo_display_bpm()))
            tempo = max(MusicData.MIN_TEMPO_BPM, min(MusicData.MAX_TEMPO_BPM, tempo))
            pattern = default_pattern(num)
        with self._preserving_focus():
            dialog = MetronomePlayerDialog(
                self, numerator=num, denominator=den,
                pattern=pattern, tempo_bpm=tempo,
            )
            dialog.click_requested.connect(self._play_metronome_pattern_click)
            dialog.exec()
            self._metronome_player_state = (
                dialog.numerator(), dialog.denominator(),
                dialog.pattern(), dialog.tempo_bpm(),
            )

    def _play_metronome_pattern_click(self, symbol: str):
        event = click_event_for_symbol(symbol)
        if event is not None:
            self.synth.play_click(*event)

    # --- persistence (delegators) -------------------------------------

    def _save_current_score_config(self):
        self.persistence.save_current()

    def _open_score_config_folder(self):
        self.persistence.open_config_folder()

    def _clear_preferences_action_text(self) -> str:
        return self.persistence.clear_action_text()

    def _clear_current_score_preferences(self):
        """Reported bug: clearing only deleted the on-disk .rsc - the
        already-loaded MusicData/Region 2 (mute/solo, voice_display_
        attributes, attribute_order, metronome...) kept whatever was in
        effect, so e.g. a solo toggled before clearing stayed soloed. Reload
        the same file straight after deleting, the same fresh-defaults path
        a normal open takes (saved_config is None in _on_score_loaded, since
        clear_current() just removed it) - not a hand-rolled reset of every
        live field, which would be a second place to keep in sync with
        apply_config(). Uses self.session.load(...) directly, NOT
        load_score_from_file(...), which saves the current (still stale,
        about to be discarded) config to disk BEFORE loading - that would
        silently recreate the very .rsc this action just deleted."""
        file_path = self._music_data.file_path if self._music_data else None
        self.persistence.clear_current()
        if file_path and not self.session.is_loading():
            self.session.load(file_path)

    # --- dialects ------------------------------------------------------

    def _select_uk_terms(self, checked: bool = False):
        self.set_uk_terms(True)

    def _select_us_terms(self, checked: bool = False):
        self.set_uk_terms(False)

    def set_uk_terms(self, uk_terms: bool):
        """Options > Terminology Language. Unlike toggle_metronome this must
        work with no score loaded - it is a global preference - and is
        persisted immediately rather than batched to closeEvent, so it
        survives a crash. Refreshes everything the vocabulary touches:
        Region 1, Regions 3/4 (via the lightweight label refresh, so no
        re-audition or lost selection) and the status bar."""
        self.session.set_uk_terms(uk_terms)
        # load-mutate-save, not a fresh AppSettings(uk_terms=uk_terms) -
        # the latter would silently wipe recent_files back to empty on
        # every terminology toggle.
        settings = app_settings.load()
        settings.uk_terms = uk_terms
        app_settings.save(settings)
        self._actions.uk_language.setChecked(uk_terms)
        self._actions.us_language.setChecked(not uk_terms)
        self._actions.goto_measure.setText(goto_measure_action_text(uk_terms))
        if not self._music_data:
            return
        self.presenter.refresh_region_1()
        self.presenter.refresh_region_3_labels()
        self.presenter.update_status_bar()

    # --- dialogs -------------------------------------------------------

    @contextmanager
    def _preserving_focus(self):
        """Restore keyboard focus to whatever held it before a modal dialog
        opened - the project's dialog-focus invariant (see CLAUDE.md /
        feedback_dialog_initial_focus). self.focusWidget() rather than
        QApplication.focusWidget() is deliberate: it reports focus within
        this window's subtree, the same reason FocusController uses it. The
        finally clause means an exception raised mid-dialog still restores
        focus instead of stranding it."""
        previous_focus = self.focusWidget()
        try:
            yield
        finally:
            if previous_focus is not None:
                previous_focus.setFocus()

    def _show_goto_measure_dialog(self):
        current_measure = None
        if self._music_data:
            current_slice = self._music_data.get_current_slice()
            if current_slice:
                current_measure = current_slice.measure
        dialog = GotoMeasureDialog(
            self, current_measure=current_measure,
            word=bar_word(self._uk_terms).capitalize(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            measure_number = dialog.measure_number()
            if measure_number is not None:
                self.navigate_to_typed_measure(str(measure_number))
                self.region_3.setFocus()

    def _show_find_dialog(self):
        """Navigation > Find... (Ctrl+F). OK arms the selected FindTarget
        and performs the initial jump in one step (NavigationController.
        find_next from wherever the cursor already is); Alt+Right/Alt+Left
        then cycle further occurrences without reopening this dialog."""
        if not self._music_data:
            return
        targets_with_counts = self._music_data.available_find_targets_with_counts()
        dialog = FindDialog(
            self,
            targets=[t for t, _ in targets_with_counts],
            counts={t: c for t, c in targets_with_counts},
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            target = dialog.selected_target()
            if target is not None:
                self.navigation.arm_find_target(target)
                self.find_next()
        self.region_3.setFocus()

    def _show_play_settings_dialog(self):
        """Playback > Play Settings... (Ctrl+Shift+P) - the one
        settings dialog for playback: the absolute tempo (per-score, saved
        in the .rsc), and the lead-in / looping habits (global, saved in
        app_settings like the UK/US dialect). Unlike GotoMeasureDialog
        there's no obvious "next place" for focus afterwards, so it returns
        to wherever it was."""
        with self._preserving_focus():
            current_tempo = (
                self._music_data.playback_tempo_display_bpm() if self._music_data else 120.0
            )
            dialog = PlaySettingsDialog(
                self,
                play_settings=self.playback.play_settings,
                current_tempo_display_bpm=current_tempo,
                uk_terms=self._uk_terms,
                score_has_repeats=bool(self._music_data and self._music_data.repeat_spans),
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                settings = dialog.play_settings()
                self.playback.set_play_settings(settings)
                app_settings.set_play_settings(settings)
                self._actions.lead_in_toggle.setChecked(settings.lead_in_enabled)
                if self._music_data:
                    self.playback.set_playback_tempo(dialog.tempo_display_bpm())

    def _show_performance_report_dialog(self):
        """Ref 29: read-only, no live signal wiring - build from current
        data, exec, restore previous focus."""
        if not self._music_data:
            return
        with self._preserving_focus():
            dialog = PerformanceReportDialog(
                self, lines=self._music_data.get_performance_report_lines()
            )
            dialog.exec()

    def _show_mixer_dialog(self):
        """Wishlist #4. rows/commit/cancel all live on PlaybackController -
        this dialog is a pure view (see widgets/mixer_dialog.py's own
        docstring), so the only thing this method does is wire its signals
        and decide commit vs. revert from exec()'s result."""
        if not self._music_data:
            return
        with self._preserving_focus():
            dialog = MixerDialog(self, rows=self.playback.begin_mixer_edit())
            dialog.volume_changed.connect(self.playback.set_mixer_volume)
            dialog.pan_changed.connect(self.playback.set_mixer_pan)
            dialog.preview_requested.connect(self.playback.toggle_play_stop)
            self.playback.end_mixer_edit(dialog.exec() == QDialog.DialogCode.Accepted)

    def _scan_devices_async(self, dialog, enumerate_fn, selected=_KEEP_SELECTION):
        """Fill an audio settings dialog's device combo without blocking the
        Qt main thread on enumeration (P1). `enumerate_fn` is a controller's
        `available_devices`; for voice control it spawns a subprocess, and a
        frozen main thread in a screen-reader-first app is silence with no
        cue. The combo shows "Scanning…" at once and set_devices() replaces
        it when the worker signals back.

        `selected` is the device name to re-select once the real list
        arrives - the saved setting on the first scan, and (the default)
        whatever is currently chosen for a Refresh, captured before the
        placeholder overwrites it."""
        if selected is _KEEP_SELECTION:
            data = dialog.device_combo.currentData()
            selected = data if isinstance(data, str) else None
        dialog.set_devices_scanning()
        thread = DeviceEnumerationThread(enumerate_fn, self)
        self._device_scan_threads.append(thread)
        thread.devices_found.connect(
            lambda devices: dialog.set_devices(devices, selected=selected)
        )
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._device_scan_threads.remove(thread)
            if thread in self._device_scan_threads else None
        )
        thread.start()

    def _show_live_midi_input_dialog(self):
        """Options > Live MIDI Input Settings... (Ctrl+Shift+L). Pure view
        (see widgets/live_midi_input_dialog.py's own docstring) - this
        method wires its signals and decides commit vs. revert from exec()'s
        result, the same shape _show_mixer_dialog already has. Unlike the
        Mixer dialog, this needs no loaded score at all - the feature is
        global, not per-score."""
        with self._preserving_focus():
            dialog = LiveMidiInputDialog(
                self,
                devices=[],
                settings=self.live_midi.begin_settings_edit(),
            )
            dialog.instrument_changed.connect(self.live_midi.preview_instrument)
            dialog.volume_changed.connect(self.live_midi.preview_volume)
            dialog.pan_changed.connect(self.live_midi.preview_pan)
            dialog.refresh_requested.connect(
                lambda: self._scan_devices_async(dialog, self.live_midi.available_devices)
            )
            self._scan_devices_async(
                dialog, self.live_midi.available_devices,
                selected=self.live_midi.settings.device_name,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.live_midi.commit_settings_edit(dialog.result_settings())
            else:
                self.live_midi.cancel_settings_edit()
            self._actions.live_midi_input.setChecked(self.live_midi.settings.enabled)

    def _show_voice_control_dialog(self):
        """Options > Voice Control Settings... (Ref 19). Pure view (see
        widgets/voice_control_dialog.py's own docstring) - this method wires
        its signals and decides commit vs. revert from exec()'s result, the
        same shape _show_live_midi_input_dialog already has. Needs no loaded
        score at all - the feature is global, not per-score."""
        with self._preserving_focus():
            dialog = VoiceControlDialog(
                self,
                devices=[],
                settings=self.voice_control.begin_settings_edit(),
            )
            dialog.refresh_requested.connect(
                lambda: self._scan_devices_async(dialog, self.voice_control.available_devices)
            )
            self._scan_devices_async(
                dialog, self.voice_control.available_devices,
                selected=self.voice_control.settings.device_name,
            )
            dialog.test_requested.connect(self._show_voice_control_test_dialog)
            dialog.cue_volume_changed.connect(self.voice_control.preview_cue_volume)
            dialog.cue_pan_changed.connect(self.voice_control.preview_cue_pan)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.voice_control.commit_settings_edit(dialog.result_settings())
            else:
                self.voice_control.cancel_settings_edit()
            self._actions.voice_control.setChecked(self.voice_control.settings.enabled)

    def set_musescore_location(self):
        """Options > Set MuseScore Location... - point at the MuseScore 4
        executable used to convert .mscz/.mscx files to MusicXML on open
        (parsers/musescore_reader.py). Global preference, not per-score;
        stored in AppSettings via load-mutate-save. Needs no loaded score."""
        with self._preserving_focus():
            start = app_settings.load().musescore_path or ""
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Locate MuseScore 4",
                start,
                "MuseScore 4 (MuseScore4.exe mscore mscore4 MuseScore*.app);;All Files (*)",
            )
            if path:
                # On macOS the user picks "MuseScore 4.app" (a directory);
                # normalise it to the runnable binary inside so every later
                # load can use the stored value directly.
                app_settings.set_musescore_path(
                    resolve_musescore_path(path) or path
                )
                # Drop the memoised "not found" probe results so the next
                # File > Open re-detects and offers the .mscz/.mscx filter.
                clear_musescore_detection_cache()

    def _show_tuner_dialog(self):
        """Tools > Tuner - a generic chromatic tuner (see controllers/
        tuner_controller.py's module docstring for the redesign that
        removed its old Instrument/String pickers). Pure view (see
        widgets/tuner_dialog.py's own docstring) - listening starts/stops
        with the dialog itself (listening_requested/listening_stopped,
        wired here) rather than being a persistent toggle - needs no loaded
        score at all, the feature is global, not per-score. Unlike before
        this redesign, the outer dialog itself has no editable settings of
        its own to commit/cancel - only its nested Settings dialog
        (_open_tuner_settings_dialog below) does."""
        with self._preserving_focus():
            dialog = TunerDialog(self)
            dialog.listening_requested.connect(lambda: self.tuner.start_listening(self.tuner.settings.input_device))
            dialog.listening_stopped.connect(self.tuner.stop_listening)
            self.tuner.pitch_result_changed.connect(dialog.update_pitch_display)
            # dialog.announce, not a controller-side QAccessible call - see
            # controllers/tuner_controller.py's module docstring GOTCHA and
            # widgets/tuner_dialog.py's own announce() for why: the controller
            # has no widget of its own to target, and a QAccessibleAnnouncement
            # Event aimed at a non-widget QObject was silently dropped. This was
            # briefly left unconnected during accuracy testing (a plain ~1s
            # throttle made the dialog hard to navigate with NVDA - talked over
            # while trying to Tab around), but the controller now pushes a
            # bounded WAITING/REPORTING sequence instead (see that module's
            # THIRD/FOURTH live-testing reports), which doesn't have that
            # problem - and, being a QAccessibleAnnouncementEvent, reaches NVDA
            # regardless of which control currently has keyboard focus.
            self.tuner.announcement_requested.connect(dialog.announce)
            dialog.settings_requested.connect(lambda: self._open_tuner_settings_dialog(dialog))
            dialog.exec()
            self.tuner.pitch_result_changed.disconnect(dialog.update_pitch_display)
            self.tuner.announcement_requested.disconnect(dialog.announce)

    def _open_tuner_settings_dialog(self, parent_dialog):
        """TunerDialog's Settings button - opened from within a slot while
        parent_dialog is still exec()'d, the same "open a second dialog from
        a still-open first one" pattern _show_voice_control_test_dialog
        already uses. Unlike that dialog (which pauses the real listening
        session to avoid two recognizers competing for one microphone), the
        tuner keeps listening the whole time this is open - its live-preview
        signals below take effect immediately, which is exactly why device
        selection here (unlike widgets/live_midi_input_dialog.py's) is live
        rather than deferred to OK - see widgets/tuner_settings_dialog.py's
        own docstring."""
        settings_dialog = TunerSettingsDialog(
            parent_dialog,
            devices=self.tuner.available_devices(),
            settings=self.tuner.begin_settings_edit(),
        )
        settings_dialog.a4_changed.connect(self.tuner.set_a4_reference)
        settings_dialog.threshold_changed.connect(self.tuner.set_signal_threshold)
        settings_dialog.device_changed.connect(self.tuner.start_listening)
        settings_dialog.refresh_requested.connect(
            lambda: settings_dialog.set_devices(self.tuner.available_devices())
        )
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            self.tuner.commit_settings_edit(settings_dialog.result_settings())
        else:
            self.tuner.cancel_settings_edit()

    def _show_voice_control_test_dialog(self, device_name: str, confidence_threshold: float):
        """Voice Control Settings' Test... button. Wiring only:
        VoiceControlTestDialog is a pure view, and VoiceControlController
        owns the diagnostic session on its single shared recognizer
        (begin/end_diagnostic_session) - including pausing and restoring any
        live listening session around it."""
        dialog = VoiceControlTestDialog(self, confidence_threshold=confidence_threshold)
        dialog.start_requested.connect(
            lambda: dialog.report_start_result(
                self.voice_control.begin_diagnostic_session(device_name, confidence_threshold)
            )
        )
        dialog.stop_requested.connect(self.voice_control.end_diagnostic_session)
        self.voice_control.diagnostic_reported.connect(dialog.report_diagnostic)
        try:
            dialog.exec()
        finally:
            self.voice_control.diagnostic_reported.disconnect(dialog.report_diagnostic)
            self.voice_control.end_diagnostic_session()

    def _show_instrument_dialog(self):
        """S5: rename a part and/or change its playback instrument, for both
        MusicXML and MIDI scores ("piano may not always be a suitable
        default"), plus wishlist #8's per-percussion-item name/sound rows.

        Wiring only - ScoreEditController.apply_instrument_overrides owns
        what the five results mean and how they reach Region 2 and the
        timeline views."""
        if not self._music_data:
            return
        with self._preserving_focus():
            dialog = InstrumentDialog(
                self,
                rows=self.score_edit.instrument_rows(),
                percussion_part_ids=self.score_edit.percussion_part_ids(),
                percussion_rows=self.score_edit.percussion_rows(),
                auto_correct_enabled=self._music_data.percussion_auto_correct_enabled,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.score_edit.apply_instrument_overrides(*dialog.overrides())

    def _show_keyboard_shortcuts_dialog(self):
        """Tools > Keyboard Shortcuts... - wiring only, per
        UserPlans/KeyboardShortcuts.md; every change the dialog makes is
        already live and saved via self.shortcuts before this returns."""
        with self._preserving_focus():
            KeyboardShortcutsDialog(self, self.shortcuts).exec()

    def _show_key_signature_dialog(self):
        """S6: a single whole-piece key signature override, for MIDI files
        that lack correct (or any) key metadata - its own dialog, not folded
        into Instruments above (see widgets/key_signature_dialog.py's own
        docstring for why).

        Wiring only - ScoreEditController.apply_key_signature_override owns
        applying it and refreshing what it affects."""
        if not self._music_data:
            return
        with self._preserving_focus():
            dialog = KeySignatureDialog(self, current_key=self.score_edit.current_key_override())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.score_edit.apply_key_signature_override(*dialog.key_override())

    def _toggle_keyboard_echo_mode(self):
        self.keyboard_echo.toggle()

    def _show_about_dialog(self):
        AboutDialog(self).exec()

    def _show_user_guide(self):
        guide_path = user_guide_html_path()
        if not os.path.exists(guide_path):
            notify_user(
                "error",
                "The user guide could not be found, so Help could not open "
                f"it.\n\nExpected it at: {guide_path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))

    # --- teardown -------------------------------------------------------

    def closeEvent(self, event):
        self._save_current_score_config()
        self.focus.disconnect_tracking()
        self.session.wait_for_load()
        # Directly, not via playback.stop(), for the same reason the
        # Sequencer is stopped directly below: no signals into regions that
        # are being torn down.
        self.playback.cancel_play_run()
        self.playback.stop_play_metronome()
        if self.playback.sequencer is not None:
            self.playback.sequencer.stop()
        # Before synth.close(): needs self._fs still alive to send the real
        # note-offs for any note still physically held on a live-input
        # device.
        self.live_midi.close()
        self.voice_control.close()
        self.tuner.stop_listening()
        self.synth.close()
        # Wait out any device scan still running (P1) so tearing down the
        # window - the threads' parent - can't orphan one mid-run.
        for thread in list(self._device_scan_threads):
            thread.wait()
        super().closeEvent(event)

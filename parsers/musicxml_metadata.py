# parsers/musicxml_metadata.py
"""RSBV 1.1: the ElementTree-only half of MusicXML loading - credits, key,
time, tempo and part structure - plus the step that assembles them into a
MusicData. Pure stdlib (plus models/ and the music21-free parsers/), so the
browser version can load a MusicXML score without music21.

MusicXMLReader (desktop) still parses with music21 and prefers its tempo,
key and time; it calls these functions for everything else and for the
fallbacks, so the two loaders share one copy of the logic.
load_musicxml_without_music21 is the browser's entry point: the same
assembly, with the ElementTree values as the only source.

Keep music21 out of this module's import chain -
tests/parsers/test_musicxml_without_music21.py checks it in a subprocess.
"""
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from models.duration_units import (
    QUARTER_LENGTH_BY_TYPE,
    beat_unit_display_name,
    beat_unit_quarter_length,
)
from models.key_signatures import FIFTHS_MAP
from models.music_data import MusicData
from models.parts_structure import PartStructureInfo
from models.synthetic_parts import (
    CHORDS_PART_ID,
    CHORDS_PART_NAME,
    LYRICS_PART_ID,
    LYRICS_PART_NAME,
)
from parsers.timeline_builder import (
    _percussion_instrument_map,
    has_harmony_elements,
    has_lyric_elements,
)
from parsers.xml_source import read_musicxml_root_and_origin

PLACEHOLDERS = {"untitled score", "composer / arranger", "subtitle"}

# (quarter BPM, display string, beat-unit quarter length, beat-unit name)
# when the score carries no readable tempo marking at all.
DEFAULT_TEMPO = (120, "120 quarter notes per minute", 1.0, "quarter")


def load_musicxml_without_music21(file_path: str) -> MusicData:
    """MusicXMLReader.load() without music21: tempo, key and time come
    from the ElementTree reads alone (the desktop reader's fallbacks), and
    MusicData.score stays None. Everything else - credits, parts, the
    sanitized root handed to the timeline builder - is identical.

    A malformed file raises ScoreLoadError, as on desktop."""
    root, _was_timewise = read_musicxml_root_and_origin(file_path)
    credits = extract_credits(root)
    key_sig, time_sig = extract_key_and_time(root)
    parts_info = extract_part_structure(root)
    # Same mutation as desktop, so the timeline builder reads the same tree.
    fill_empty_beat_units(root)
    return assemble_music_data(
        file_path,
        root,
        credits=credits,
        parts_info=parts_info,
        key_sig=key_sig,
        time_sig=time_sig,
        tempo=extract_tempo(root) or DEFAULT_TEMPO,
    )


def assemble_music_data(
    file_path: str,
    root: Optional[ET.Element],
    *,
    credits: Dict[str, str],
    parts_info: List[PartStructureInfo],
    key_sig: str,
    time_sig: str,
    tempo: Tuple[int, str, float, str],
    score: Optional[Any] = None,
) -> MusicData:
    """The MusicData both loaders return, from already-resolved metadata.
    `credits` is updated in place with the three header rows."""
    tempo_bpm, tempo_display, tempo_beat_unit_quarter_length, tempo_beat_unit_name = tempo

    credits["Key Signature"] = key_sig
    credits["Time Signature"] = time_sig
    credits["Tempo"] = tempo_display

    music_data = MusicData(
        credits=credits,
        parts_info=parts_info,
        file_path=file_path,
        score=score,
        tempo_bpm=tempo_bpm,
        tempo_beat_unit_quarter_length=tempo_beat_unit_quarter_length,
        tempo_beat_unit_name=tempo_beat_unit_name,
        xml_root=root,
    )

    # Ref 15 AC4-style default, same as GpReader's synthetic Chords
    # voice: the chord name (step), the beat it falls on (so repeated
    # "A minor" strokes within a bar aren't ambiguous - see
    # parsers/timeline_builder.py's chord-stroke entries) and any real
    # strum direction should be audible immediately, without the user
    # having to reach for the attribute context menu first.
    if any(p.part_id == CHORDS_PART_ID for p in parts_info):
        music_data.voice_display_attributes[(CHORDS_PART_ID, 1, 1)] = {
            "step", "beat position", "strum",
        }

    return music_data


def format_number(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def fill_empty_beat_units(root: Optional[ET.Element]) -> bool:
    """Replaces any textless <beat-unit/> with "quarter" so music21 can
    parse the file at all - see the comment at the call site in
    MusicXMLReader.load() for why this is necessary and safe. Returns whether anything was
    changed, so the caller only re-serializes the tree when it had to."""
    if root is None:
        return False
    changed = False
    for beat_unit in root.iter("beat-unit"):
        if not (beat_unit.text and beat_unit.text.strip()):
            beat_unit.text = "quarter"
            changed = True
    return changed


def extract_tempo(
    root: Optional[ET.Element]
) -> Optional[Tuple[int, str, float, str]]:
    """The first valid tempo marking in the score, read straight from
    the XML. Same return shape as
    MusicXMLReader._extract_tempo. Used when music21
    found nothing (or couldn't parse the file), so the opening tempo is
    still the score's own rather than the 120 fallback.

    "Valid" = a <direction-type>/<metronome> with a known <beat-unit>
    and a positive numeric <per-minute>. A <sound tempo="..."> (already
    in quarter-note BPM by the MusicXML spec) is remembered as a
    secondary fallback for a direction that has no readable metronome.
    Mirrors TimelineBuilder._tempo_change_from_direction, which does the
    same for every *later* marking."""
    if root is None:
        return None
    sound_fallback: Optional[Tuple[int, str, float, str]] = None
    # Structural facts come from the first part (the convention
    # _scan_first_part / _detect_pickup already follow); a global tempo
    # direction lives there too.
    first_part = root.find("part")
    if first_part is None:
        return None
    for measure in first_part.findall("measure"):
        for direction in measure.findall("direction"):
            metro = direction.find("direction-type/metronome")
            if metro is not None:
                beat_unit = (metro.findtext("beat-unit") or "").strip()
                per_minute_raw = (metro.findtext("per-minute") or "").strip()
                if beat_unit in QUARTER_LENGTH_BY_TYPE and per_minute_raw:
                    try:
                        per_minute = float(per_minute_raw)
                    except ValueError:
                        per_minute = 0.0
                    if per_minute > 0:
                        dots = len(metro.findall("beat-unit-dot"))
                        beat_unit_ql = beat_unit_quarter_length(beat_unit, dots)
                        name = beat_unit_display_name(beat_unit, dots)
                        # <sound tempo> in the same direction is
                        # authoritative for the quarter BPM when present
                        # (no float round-trip); otherwise derive it.
                        sound_el = direction.find("sound[@tempo]")
                        try:
                            quarter_bpm = (
                                float(sound_el.attrib["tempo"])
                                if sound_el is not None
                                else per_minute * beat_unit_ql
                            )
                        except (ValueError, KeyError):
                            quarter_bpm = per_minute * beat_unit_ql
                        return (
                            int(round(quarter_bpm)),
                            f"{format_number(per_minute)} {name} notes per minute",
                            beat_unit_ql,
                            name,
                        )
            if sound_fallback is None:
                sound_el = direction.find("sound[@tempo]")
                if sound_el is not None:
                    try:
                        quarter_bpm = float(sound_el.attrib["tempo"])
                    except (ValueError, KeyError):
                        quarter_bpm = 0.0
                    if quarter_bpm > 0:
                        sound_fallback = (
                            int(round(quarter_bpm)),
                            f"{format_number(quarter_bpm)} quarter notes per minute",
                            1.0,
                            "quarter",
                        )
    return sound_fallback


def extract_key_and_time(root: Optional[ET.Element]) -> Tuple[str, str]:
    key_sig = "C major / A minor"
    time_sig = "4/4"

    if root is None:
        return key_sig, time_sig

    try:
        fifths_elem = root.find(".//attributes/key/fifths")
        if fifths_elem is not None and fifths_elem.text:
            fifths = int(fifths_elem.text.strip())
            key_sig = FIFTHS_MAP.get(fifths, f"{fifths} sharps/flats")

        beats_elem = root.find(".//attributes/time/beats")
        beat_type_elem = root.find(".//attributes/time/beat-type")

        if (
            beats_elem is not None
            and beats_elem.text
            and beat_type_elem is not None
            and beat_type_elem.text
        ):
            time_sig = f"{beats_elem.text.strip()}/{beat_type_elem.text.strip()}"

    except Exception as e:
        print(f"[ERROR] Parsing Key/Time XML: {e}")

    return key_sig, time_sig


def extract_credits(root: Optional[ET.Element]) -> Dict[str, str]:
    credits_found: Dict[str, str] = {}
    if root is None:
        return credits_found

    untyped_count = 1

    try:
        for credit in root.findall("credit"):
            type_elem = credit.find("credit-type")
            words_texts = [
                w.text.strip()
                for w in credit.findall(".//credit-words")
                if w.text and w.text.strip()
            ]
            text = " ".join(words_texts) if words_texts else ""

            if not text:
                continue

            if type_elem is not None and type_elem.text:
                key = type_elem.text.strip().capitalize()
            else:
                key = f"Credit {untyped_count}"
                untyped_count += 1

            if key in credits_found:
                existing = credits_found[key]
                if existing.lower() in PLACEHOLDERS:
                    credits_found[key] = text
                elif (
                    text.lower() not in PLACEHOLDERS
                    and text not in existing
                ):
                    credits_found[key] += f" | {text}"
            else:
                credits_found[key] = text

    except Exception as e:
        print(f"[ERROR] Parsing credits XML: {e}")

    return credits_found


def extract_part_structure(root: Optional[ET.Element]) -> List[PartStructureInfo]:
    parts_list: List[PartStructureInfo] = []
    if root is None:
        return parts_list

    try:
        part_names = {}
        for sp in root.findall(".//part-list/score-part"):
            p_id = sp.attrib.get("id", "")
            p_name_elem = sp.find("part-name")
            p_name = p_name_elem.text.strip() if p_name_elem is not None and p_name_elem.text else "Classical Guitar"
            part_names[p_id] = p_name

        # Region 2 follow-up: shared with TimelineBuilder's own
        # per-note resolution (same map, same source-part-list read) so
        # the two can't disagree on a percussion item's name/key - see
        # _percussion_instrument_map's own docstring.
        percussion_instruments = _percussion_instrument_map(root)

        for part_elem in root.findall("part"):
            p_id = part_elem.attrib.get("id", "")
            p_info = PartStructureInfo(part_id=p_id, name=part_names.get(p_id, "Classical Guitar"))

            midi_prog_elem = root.find(f".//score-part[@id='{p_id}']//midi-program")
            if midi_prog_elem is not None and midi_prog_elem.text:
                p_info.gmidi_program = int(midi_prog_elem.text.strip())
            else:
                p_info.gmidi_program = 25

            staves_clefs: Dict[int, str] = {}
            staves_voices: Dict[int, List[int]] = {}
            is_percussion = False

            for c in part_elem.findall(".//attributes/clef"):
                staff_num = int(c.attrib.get("number", "1"))
                sign_elem = c.find("sign")
                sign = sign_elem.text.strip() if sign_elem is not None and sign_elem.text else "G"

                if sign == "TAB":
                    staves_clefs[staff_num] = "Tab stave"
                elif sign == "G":
                    staves_clefs[staff_num] = "Treble stave"
                elif sign == "F":
                    staves_clefs[staff_num] = "Bass stave"
                elif sign == "percussion":
                    staves_clefs[staff_num] = "Percussion stave"
                    is_percussion = True
                else:
                    staves_clefs[staff_num] = f"{sign} stave"

            if 1 not in staves_clefs:
                staves_clefs[1] = "Treble stave"

            # An "alternate" stave repeats the stave before it in
            # another notation (classical guitar's TAB under the
            # treble) - see PartStructureInfo.alternate_staves.
            for details in part_elem.findall(".//attributes/staff-details"):
                staff_num = int(details.attrib.get("number", "1"))
                type_elem = details.find("staff-type")
                if (
                    staff_num > 1
                    and type_elem is not None
                    and (type_elem.text or "").strip() == "alternate"
                ):
                    p_info.alternate_staves[staff_num] = staff_num - 1

            # Wishlist #8: gmidi_program is meaningless for a percussion
            # part (see PartStructureInfo.is_percussion) - MusicData
            # routes its playback to the GM percussion bank instead of
            # ever reading gmidi_program.
            p_info.is_percussion = is_percussion

            for note in part_elem.findall(".//note"):
                staff_id = int(note.find("staff").text.strip()) if note.find("staff") is not None else 1

                # Region 2 follow-up (user: "the pitch defines the
                # instrument - that is the defining feature"): a
                # percussion note's Region 2 "voice" is its own item's
                # declared key, not the real notated <voice> several
                # different percussion items may share (Hit It.mxl's
                # hi-hat and snare are both real voice 1) - this is what
                # splits them into their own independently
                # mute/soloable rows, reusing the existing part/staff/
                # voice tree untouched (TimelineBuilder makes the exact
                # same substitution for NoteData.voice - see there).
                unpitched_el = note.find("unpitched")
                if unpitched_el is not None:
                    instr_el = note.find("instrument")
                    instr_id = instr_el.attrib.get("id") if instr_el is not None else None
                    item_name, item_key = percussion_instruments.get(instr_id, (None, None))
                    if item_key is None:
                        continue
                    voice_id = item_key
                    p_info.voice_names[(staff_id, voice_id)] = item_name
                elif is_percussion:
                    # A rest (or any other non-<unpitched> note) inside
                    # a percussion part has no item identity of its own
                    # to become a voice - unlike a pitched part, where a
                    # rest's real <voice> still matters (a whole passage
                    # of one voice can legitimately be nothing but
                    # rests), skip it rather than fabricating a bogus
                    # extra voice row from its raw notated <voice>
                    # (reported: Hit It.mxl's kick voice ends in a
                    # <rest>, which produced a stray "Voice 2" row).
                    continue
                else:
                    voice_id = int(note.find("voice").text.strip()) if note.find("voice") is not None else 1

                if staff_id not in staves_voices:
                    staves_voices[staff_id] = []
                if voice_id not in staves_voices[staff_id]:
                    staves_voices[staff_id].append(voice_id)

            for s_id in staves_voices:
                staves_voices[s_id].sort()

            p_info.staves_clefs = staves_clefs
            p_info.staves_voices = staves_voices

            parts_list.append(p_info)

        # A real notated score (piano/guitar lead sheet, e.g.) can carry
        # <harmony>/<lyric> markup alongside its real notes - added here
        # as two more parts, the same "an instrument called Chords" /
        # "the lyrics are also an instrument/part" UX
        # parsers/ug_timeline_builder.py already established for a pure
        # Ultimate Guitar import. One staff, one voice each - not zero,
        # which would make Region2HierarchyModel.get_active_voice_tuples()
        # treat the part as having nothing to show regardless of its
        # on/off state (the same gotcha CLAUDE.md documents for MIDI's
        # collapse_to_parts and UgReader). Added only when the file
        # actually has the markup, so an ordinary score gets no empty
        # "Chords"/"Lyrics" rows.
        if has_harmony_elements(root):
            parts_list.append(
                PartStructureInfo(
                    part_id=CHORDS_PART_ID,
                    name=CHORDS_PART_NAME,
                    gmidi_program=25,  # Acoustic Guitar (nylon), same as UG's Chords part
                    staves_clefs={1: "Chord chart"},
                    staves_voices={1: [1]},
                )
            )
        if has_lyric_elements(root):
            parts_list.append(
                PartStructureInfo(
                    part_id=LYRICS_PART_ID,
                    name=LYRICS_PART_NAME,
                    gmidi_program=25,  # unused - the Lyrics part never carries a real midi_pitch
                    staves_clefs={1: "Lyrics"},
                    staves_voices={1: [1]},
                )
            )

    except Exception as e:
        print(f"[ERROR] Parsing part structure XML: {e}")

    return parts_list

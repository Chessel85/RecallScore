# parsers/musicXML_reader.py
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

import music21

from models.duration_units import beat_unit_display_name
from models.key_signatures import FIFTHS_MAP
from models.music_data import MusicData
from parsers.musicxml_metadata import (
    DEFAULT_TEMPO,
    assemble_music_data,
    extract_credits,
    extract_key_and_time,
    extract_part_structure,
    extract_tempo,
    fill_empty_beat_units,
    format_number,
)
from parsers.xml_source import read_musicxml_root_and_origin

class MusicXMLReader:
    """Parses MusicXML metadata via ElementTree and streams via music21 into MusicData.

    The ElementTree reads live in parsers/musicxml_metadata.py, shared with
    the browser version's music21-free loader; this class adds music21's
    tempo/key/time on top."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._was_timewise = False

    def load(self) -> MusicData:
        root = self._parse_xml_root()

        credits_dict = extract_credits(root)
        etree_key, etree_time = extract_key_and_time(root)
        etree_parts_info = extract_part_structure(root)

        # Some notation software exports a metronome mark's note-head glyph
        # as an empty <beat-unit/> (seen on files from at least one
        # scanning/OMR tool) instead of a real duration name. music21's
        # xmlToM21.musicXMLTypeToType(None) treats that as fatal and aborts
        # parsing the WHOLE score - not just that one marking - which used
        # to take down every music21-derived field (key/time/tempo
        # elsewhere in the piece) even though the actual note timeline
        # (parsers/timeline_builder.py, walked straight from `root`) never
        # touches `score` at all and would have loaded fine regardless.
        # Filling the empty tag with a harmless "quarter" default before
        # handing the tree to music21 only changes that one marking's
        # cosmetic note-head glyph, never a pitch or duration anyone reads
        # or hears - see musicxml_metadata.extract_tempo, whose own
        # fallback already produces the identical display string via
        # <sound tempo=...>.
        sanitized = fill_empty_beat_units(root)

        score = None
        try:
            if self._was_timewise or sanitized:
                score = music21.converter.parseData(
                    ET.tostring(root, encoding="unicode"), format="musicxml"
                )
            else:
                score = music21.converter.parse(self.file_path)
        except Exception as e:
            print(f"[ERROR] music21 parse failed: {e}")

        # music21's tempo read is preferred, but it returns None when the
        # file has no usable MetronomeMark *or* when music21 couldn't parse
        # the file at all (score is None - a single malformed <metronome>
        # later in the piece aborts its whole parse). The ElementTree scan
        # then finds the first valid tempo marking straight from the XML, so
        # the header and playback show the real opening tempo rather than
        # the 120 fallback.
        tempo = (
            (self._extract_tempo(score) if score else None)
            or extract_tempo(root)
            or DEFAULT_TEMPO
        )
        key_sig = self._extract_key(score) or etree_key
        time_sig = self._extract_time(score) or etree_time

        return assemble_music_data(
            self.file_path,
            root,
            credits=credits_dict,
            parts_info=etree_parts_info,
            key_sig=key_sig,
            time_sig=time_sig,
            tempo=tempo,
            score=score,
        )

    def _parse_xml_root(self) -> Optional[ET.Element]:
        """Parses the file once; every etree-based extractor below reads
        from this same root rather than re-parsing. The returned root is
        always <score-partwise> - a <score-timewise> file is converted in
        memory (parsers/xml_source.py::timewise_to_partwise) - and
        self._was_timewise records whether that happened, so load() knows to
        hand music21 the converted tree via parseData rather than parse()ing
        the (timewise) file directly, since music21 refuses timewise outright.

        A genuine parse failure (malformed XML, broken .mxl container) is
        raised, not swallowed - read_musicxml_root_and_origin raises
        ScoreLoadError for those, and the load worker turns it into an
        accessible error dialog. Degrading to an empty score here would
        report a corrupt file as a blank piece."""
        root, self._was_timewise = read_musicxml_root_and_origin(self.file_path)
        return root

    def _extract_tempo(
        self, score: music21.stream.Score
    ) -> Optional[Tuple[int, str, float, str]]:
        """(quarter-note BPM for playback timing, display string in the
        score's OWN beat unit, that unit's quarter-length ratio, its name),
        or None when the score carries no usable MetronomeMark - the caller
        then falls back to the ElementTree scan.

        A score marked eighth=96 yields 48 BPM internally but must display
        as "96 eighth notes per minute" - the ratio and name are what let
        the status bar and tempo dialog convert back live (Ref 12)."""
        try:
            tempos = score.flatten().getElementsByClass(music21.tempo.MetronomeMark)
            for mm in tempos:
                quarter_bpm = mm.getQuarterBPM()
                if quarter_bpm and mm.number and mm.referent:
                    beat_unit = self._beat_unit_name(mm.referent)
                    number = format_number(mm.number)
                    return (
                        int(quarter_bpm),
                        f"{number} {beat_unit} notes per minute",
                        float(mm.referent.quarterLength),
                        beat_unit,
                    )
        except Exception as e:
            print(f"[WARN] Error reading tempo: {e}")
        return None

    def _beat_unit_name(self, duration: music21.duration.Duration) -> str:
        return beat_unit_display_name(duration.type, duration.dots)

    def _extract_key(self, score: music21.stream.Score) -> Optional[str]:
        try:
            keys = score.flatten().getElementsByClass(music21.key.KeySignature)
            if keys:
                ks = keys[0]
                return FIFTHS_MAP.get(ks.sharps, f"{ks.sharps} sharps/flats")
            
            explicit_keys = score.flatten().getElementsByClass(music21.key.Key)
            if explicit_keys:
                k = explicit_keys[0]
                return f"{k.tonic.name} {k.mode}"
        except Exception as e:
            print(f"[WARN] Error extracting key via music21: {e}")
        return None

    def _extract_time(self, score: music21.stream.Score) -> Optional[str]:
        try:
            times = score.flatten().getElementsByClass(music21.meter.TimeSignature)
            if times:
                ts = times[0]
                return f"{ts.numerator}/{ts.denominator}"
        except Exception as e:
            print(f"[WARN] Error extracting time via music21: {e}")
        return None

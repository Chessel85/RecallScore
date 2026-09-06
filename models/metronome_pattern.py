# models/metronome_pattern.py
"""Pure helpers for the Metronome Player tool's time signature + per-beat
click pattern (Tools > Metronome Player...).

Qt-free and fully unit-testable, the same category as models/strum_pattern.py.
A "pattern" is a short string, one character per beat: A/B/C/D pick one of the
four click samples (audio/metronome.py's click_event_for_symbol), '.' is a
silent beat.
"""

# A/B/C/D = the four click samples, '.' = a silent beat. Exported so the
# dialog's QRegularExpressionValidator and this module stay in step.
PATTERN_CHARS = "ABCD."
# Case-insensitive at keystroke time; normalise_pattern upper-cases for
# matching. '*' not '+' so an empty field is still a valid intermediate state
# while the user is typing.
PATTERN_REGEX = r"[AaBbCcDd.]*"

ALLOWED_DENOMINATORS = (2, 4, 8, 16)
MIN_NUMERATOR = 1
MAX_NUMERATOR = 12


def normalise_pattern(text: str) -> str:
    """Strip all whitespace and upper-case, so 'a . b' -> 'A.B'."""
    return "".join(str(text).split()).upper()


def default_pattern(numerator: int) -> str:
    """Accent on beat 1, a plain click on every other beat: 'ABBB' for 4,
    'A' for 1. numerator is clamped to at least 1."""
    n = max(1, int(numerator))
    return "A" + "B" * (n - 1)


def pattern_length_matches(pattern: str, numerator: int) -> bool:
    """True when the pattern has exactly one position per beat in the bar."""
    return len(normalise_pattern(pattern)) == int(numerator)


def snap_time_signature(num: int, den: int) -> tuple:
    """Clamp the numerator to MIN_NUMERATOR..MAX_NUMERATOR and snap the
    denominator to the nearest allowed value (2/4/8/16, falling back to 4) -
    used when seeding from a loaded score whose current slice carries an
    exotic time signature the dialog's own controls can't represent."""
    n = max(MIN_NUMERATOR, min(MAX_NUMERATOR, int(num)))
    try:
        d = int(den)
    except (TypeError, ValueError):
        return n, 4
    if d in ALLOWED_DENOMINATORS:
        return n, d
    # Nearest allowed value; an exact tie (e.g. 3, equidistant from 2 and 4)
    # resolves to 4 - the plan's stated fallback.
    d = min(ALLOWED_DENOMINATORS, key=lambda a: (abs(a - d), a != 4))
    return n, d

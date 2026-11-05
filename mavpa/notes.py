"""Note names <-> MIDI numbers. Scientific pitch: middle C = C4 = 60."""
import re

PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_RX = re.compile(r"^([A-Ga-g])([#b♯♭]*)(-?\d+)$")
MODES = ["ionian", "dorian", "phrygian", "lydian", "mixolydian", "aeolian", "locrian"]
MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11]


def num(note):
    """'E1' -> 28, 'F#3' -> 54, 60 -> 60."""
    if isinstance(note, (int, float)):
        return int(note)
    m = _RX.match(str(note).strip())
    if not m:
        raise ValueError(f"not a note name: {note!r} (use e.g. E1, F#3, Bb4; middle C = C4)")
    letter, acc, octave = m.groups()
    pc = _PC[letter.upper()] + sum(1 if a in "#♯" else -1 for a in acc)
    return 12 * (int(octave) + 1) + pc


def name(midi):
    midi = int(round(midi))
    return f"{PC_NAMES[midi % 12]}{midi // 12 - 1}"


def pc_name(pc):
    return PC_NAMES[int(pc) % 12]


def pc_of(note_name):
    """'E' / 'F#' / 'Bb' -> pitch class."""
    return num(f"{note_name}4") % 12


def scale_pcs(tonic, mode):
    """Pitch classes of a diatonic mode, e.g. ('E', 'phrygian') -> {0,2,4,5,7,9,11}."""
    deg = MODES.index(mode.lower())
    parent = (pc_of(tonic) - MAJOR_STEPS[deg]) % 12
    return {(parent + s) % 12 for s in MAJOR_STEPS}, parent


def key_signature_sharps(parent_pc):
    """Number of sharps (+) / flats (-) of a major key by pitch class."""
    table = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}
    return table[parent_pc % 12]

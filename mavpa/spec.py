"""song.json -> concrete notes.

A layer is a set of short patterns (loops) plus a list of "play" entries that say
where each pattern runs. That mirrors how producers build songs: a few loops,
copy-pasted and muted per section. See skills/mavpa/reference/spec.md.

Note tuple everywhere: (song_bar, step, length_in_steps, midi_pitch, velocity, pattern_name)
(pattern_name is "" for literal one-off notes).
"""
from .notes import num

DEFAULT_VEL = {"X": 110, "x": 90, "g": 60}


class SpecError(ValueError):
    pass


def last_bar(spec):
    if spec.get("bars"):
        return int(spec["bars"])
    ends = [s.get("to", 0) for s in spec.get("sections", [])]
    return max(ends) if ends else 1


def entry_bars(entry, last):
    if "bars" in entry:
        bars = [int(b) for b in entry["bars"]]
    else:
        bars = list(range(int(entry.get("from", 1)), int(entry.get("to", last)) + 1))
    skip = {int(b) for b in entry.get("except", [])}
    return [b for b in bars if b not in skip]


def pattern_pos(bar, anchor, length):
    """1-based position of a song bar inside a pattern that starts at `anchor`."""
    return (bar - anchor) % length + 1


def _vel(v, entry):
    if "velocity" in entry:
        v = entry["velocity"]
    v = v + entry.get("velocity_offset", 0)
    return int(max(entry.get("min_velocity", 1), min(127, v)))


def drum_note(layer, inst):
    kit = layer.get("kit", {})
    if inst not in kit:
        raise SpecError(f"layer {layer.get('id')}: drum '{inst}' missing from kit map")
    v = kit[inst]
    return int(v["note"] if isinstance(v, dict) else v)


def render_layer(layer, spec):
    """All notes of one layer, in song bars."""
    last = last_bar(spec)
    out = []
    pats = layer.get("patterns", {})
    is_drums = bool(layer.get("drums"))
    vmap = {**DEFAULT_VEL, **layer.get("velocity", {})}
    for i, entry in enumerate(layer.get("play", [])):
        pname = entry.get("pattern")
        if pname not in pats:
            raise SpecError(f"layer {layer.get('id')}: play[{i}] uses unknown pattern {pname!r}")
        pat = pats[pname]
        length = int(pat.get("bars", 1))
        anchor = int(entry.get("anchor", entry.get("from", (entry.get("bars") or [1])[0])))
        only = set(entry.get("only", []))
        tr = int(entry.get("transpose", 0))
        for bar in entry_bars(entry, last):
            k = str(pattern_pos(bar, anchor, length))
            if is_drums:
                for inst, rows in pat.get("grid", {}).items():
                    if only and inst not in only:
                        continue
                    row = rows.get(k, "")
                    for s, ch in enumerate(row):
                        if ch in ".-_ ":
                            continue
                        if ch not in vmap:
                            raise SpecError(f"layer {layer.get('id')}: unknown drum velocity mark {ch!r} in {inst} bar {k}")
                        out.append((bar, s, 1, drum_note(layer, inst), _vel(vmap[ch], entry), pname))
            else:
                for n in pat.get("notes", {}).get(k, []):
                    vel = n[3] if len(n) > 3 else 90
                    out.append((bar, n[0], n[1], num(n[2]) + tr, _vel(vel, entry), pname))
    for bar, notes in layer.get("notes", {}).items():
        for n in notes:
            if is_drums and isinstance(n[2], str) and n[2] in layer.get("kit", {}):
                pitch = drum_note(layer, n[2])
            else:
                pitch = num(n[2])
            out.append((int(bar), n[0], n[1], pitch, int(n[3]) if len(n) > 3 else 90, ""))
    return out


def pattern_notes(layer, pattern):
    """{pos: [{s, l, p, v}]} for melodic patterns, {inst: {pos: 'X..x'}} for drums."""
    pat = layer.get("patterns", {}).get(pattern)
    if pat is None:
        raise SpecError(f"layer {layer.get('id')}: no pattern {pattern!r}")
    if layer.get("drums"):
        return pat.get("grid", {})
    return {k: [{"s": n[0], "l": n[1], "p": num(n[2]), "v": n[3] if len(n) > 3 else 90} for n in v]
            for k, v in pat.get("notes", {}).items()}


def pattern_positions(layer, pattern, spec):
    """For each pattern bar k: the song bars where it plays, e.g. {1: [1, 9, 17, ...]}."""
    last = last_bar(spec)
    pat = layer["patterns"][pattern]
    length = int(pat.get("bars", 1))
    pos = {k: [] for k in range(1, length + 1)}
    for entry in layer.get("play", []):
        if entry.get("pattern") != pattern:
            continue
        anchor = int(entry.get("anchor", entry.get("from", (entry.get("bars") or [1])[0])))
        for bar in entry_bars(entry, last):
            pos[pattern_pos(bar, anchor, length)].append(bar)
    return {k: sorted(set(v)) for k, v in pos.items()}


def render(spec):
    return {ly["id"]: render_layer(ly, spec) for ly in spec.get("layers", [])}


def active_bars(notes, grid_steps_per_bar):
    """Song bars in which a layer sounds (a note starts or is held)."""
    bars = set()
    for bar, s, ln, *_ in notes:
        end = s + max(ln, 1) - 1e-6
        for b in range(int(bar + s // grid_steps_per_bar), int(bar + end // grid_steps_per_bar) + 1):
            bars.add(b)
    return bars


def ranges(bars):
    """{1,2,3,7,8} -> [[1,3],[7,8]]"""
    out = []
    for b in sorted(bars):
        if out and b == out[-1][1] + 1:
            out[-1][1] = b
        else:
            out.append([b, b])
    return out


def validate(spec):
    """Return a list of human-readable problems (empty = fine)."""
    probs = []
    if not spec.get("grid", {}).get("bpm"):
        probs.append("grid.bpm missing (run: mavpa grid <ws> --write)")
    ids = set()
    for ly in spec.get("layers", []):
        lid = ly.get("id")
        if not lid:
            probs.append("a layer has no id")
            continue
        if lid in ids:
            probs.append(f"duplicate layer id {lid!r}")
        ids.add(lid)
        try:
            render_layer(ly, spec)
        except (SpecError, ValueError, KeyError, IndexError, TypeError) as e:
            probs.append(f"layer {lid}: {e}")
    for lp in spec.get("loops", []):
        if lp.get("layer") not in ids:
            probs.append(f"loop {lp.get('name')!r} refers to unknown layer {lp.get('layer')!r}")
    return probs

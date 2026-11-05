"""mavpa build: song.json -> the monkey kit.

kit/
  README.txt, guide.html
  audio/00_full_mix_ALIGNED.wav + one aligned WAV per stem
  midi/00_ALL_PARTS_full_song.mid (with section markers)
  midi/full_song/NN_<layer>.mid   one answer key per layer, aligned to the audio
  midi/loops/*.mid                 pattern building blocks, starting at their own bar 1
"""
import shutil
import unicodedata
from pathlib import Path

from . import audio as A
from .notes import pc_of, scale_pcs
from .spec import SpecError, pattern_positions, render, validate

DEFAULT_AUDIO = [("drums", "01_drums"), ("bass", "02_bass"), ("other", "03_music"), ("vocals", "04_vocals")]
ROLE_PROGRAM = {"bass": 38, "harmony": 48, "pad": 89, "lead": 80, "pluck": 45, "keys": 4, "vocal": 53,
                "fx": 98, "drums": 0}


def safe_name(text):
    return text.replace(" ", "_").replace("/", "-")


def ascii_text(text):
    text = text.replace("′", "'").replace("–", "-").replace("—", "-").replace("→", "->")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def program_of(layer):
    if "program" in layer:
        return int(layer["program"])
    return ROLE_PROGRAM.get(layer.get("role", ""), 0)


def midi_key_number(spec):
    """pretty_midi key number (0-11 = major keys) of the parent major scale."""
    key = spec.get("key") or {}
    if key.get("midi_key"):
        return pc_of(key["midi_key"])
    if key.get("tonic") and key.get("mode"):
        return scale_pcs(key["tonic"], key["mode"])[1]
    return None


def _pm(grid, spec):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=grid.bpm, resolution=960)
    pm.time_signature_changes.append(pretty_midi.TimeSignature(grid.beats_per_bar, grid.beat_unit, 0))
    k = midi_key_number(spec)
    if k is not None:
        pm.key_signature_changes.append(pretty_midi.KeySignature(k, 0))
    return pm


def _instrument(layer):
    import pretty_midi
    return pretty_midi.Instrument(program=program_of(layer), is_drum=bool(layer.get("drums")),
                                  name=layer.get("name", layer["id"]))


def _add_notes(ins, notes, grid, layer, bar_to_time):
    import pretty_midi
    scale = float(layer.get("length_scale", 0.5 if layer.get("drums") else 1.0))
    for bar, s, ln, p, v, *_ in notes:
        t0 = bar_to_time(bar, s)
        if t0 < 0:
            continue
        ins.notes.append(pretty_midi.Note(velocity=int(v), pitch=int(p), start=t0,
                                          end=t0 + ln * grid.step * scale))


def add_markers(path, markers, bpm):
    """Insert MIDI marker meta events (section names) into track 0 of a written file."""
    import mido
    mf = mido.MidiFile(str(path))
    tr = mf.tracks[0]
    abs_msgs, t, eot = [], 0, None
    for m in tr:
        t += m.time
        if m.type == "end_of_track":
            eot = t
            continue
        abs_msgs.append((t, m))
    tpb = mf.ticks_per_beat
    for sec, text in markers:
        tick = int(round(sec / (60.0 / bpm) * tpb))
        abs_msgs.append((tick, mido.MetaMessage("marker", text=ascii_text(text)[:60], time=0)))
    abs_msgs.sort(key=lambda x: x[0])
    new, prev = mido.MidiTrack(), 0
    for tick, m in abs_msgs:
        new.append(m.copy(time=tick - prev))
        prev = tick
    end = max(eot or 0, prev)
    new.append(mido.MetaMessage("end_of_track", time=end - prev))
    mf.tracks[0] = new
    mf.save(str(path))


def default_loops(spec):
    """One loop file per (layer, pattern): taken from the first place it plays from its bar 1."""
    loops = []
    for ly in spec.get("layers", []):
        for pname, pat in ly.get("patterns", {}).items():
            pos = pattern_positions(ly, pname, spec)
            if not pos.get(1):
                continue
            n = int(pat.get("bars", 1))
            loops.append({"name": f"loop{n}_{ly['id']}" + ("" if pname == "loop" else f"_{pname}"),
                          "layer": ly["id"], "from": pos[1][0], "bars": n})
    return loops


def build(ws, out=None, clean=True, with_audio=True):
    spec = ws.spec()
    problems = validate(spec)
    if problems:
        raise SpecError("song.json has problems:\n  - " + "\n  - ".join(problems))
    grid = ws.grid()
    out = Path(out) if out else ws.kit
    if clean and out.exists():
        for sub in ("midi", "audio"):
            shutil.rmtree(out / sub, ignore_errors=True)
    for sub in ("midi/full_song", "midi/loops", "audio"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    layers = spec.get("layers", [])
    notes = render(spec)
    files = {"audio": [], "full_song": [], "loops": [], "all": None}

    # ---- full-song answer keys, one file per layer
    def song_time(bar, s):
        return grid.daw_t(bar, s)

    for i, ly in enumerate(layers, 1):
        pm = _pm(grid, spec)
        ins = _instrument(ly)
        _add_notes(ins, sorted(notes[ly["id"]], key=lambda n: (n[0], n[1], n[3])), grid, ly, song_time)
        pm.instruments.append(ins)
        name = ly.get("file") or f"{i:02d}_{safe_name(ly.get('name', ly['id']))}"
        pm.write(str(out / "midi/full_song" / f"{name}.mid"))
        files["full_song"].append(f"{name}.mid")

    # ---- everything in one multitrack file, with section markers
    pm = _pm(grid, spec)
    for ly in layers:
        ins = _instrument(ly)
        _add_notes(ins, sorted(notes[ly["id"]], key=lambda n: (n[0], n[1], n[3])), grid, ly, song_time)
        pm.instruments.append(ins)
    all_path = out / "midi/00_ALL_PARTS_full_song.mid"
    pm.write(str(all_path))
    markers = [(grid.daw_t(s["from"]) if s["from"] >= 1 else 0.0, s["name"])
               for s in spec.get("sections", []) if s.get("name")]
    if markers:
        add_markers(all_path, markers, grid.bpm)
    files["all"] = all_path.name

    # ---- loop building blocks
    by_id = {ly["id"]: ly for ly in layers}
    for lp in spec.get("loops") or default_loops(spec):
        ly = by_id[lp["layer"]]
        b0, nb = int(lp["from"]), int(lp["bars"])
        sel = [n for n in notes[ly["id"]] if b0 <= n[0] < b0 + nb]
        if lp.get("pattern"):
            sel = [n for n in sel if n[5] == lp["pattern"]]
        pm = _pm(grid, spec)
        ins = _instrument(ly)
        _add_notes(ins, sorted(sel, key=lambda n: (n[0], n[1], n[3])), grid, ly,
                   lambda bar, s: (bar - b0) * grid.bar + s * grid.step)
        pm.instruments.append(ins)
        pm.write(str(out / "midi/loops" / f"{lp['name']}.mid"))
        files["loops"].append(f"{lp['name']}.mid")

    # ---- aligned audio
    if with_audio:
        A.write_aligned(ws.source, out / "audio/00_full_mix_ALIGNED.wav", grid.pad_s)
        files["audio"].append("00_full_mix_ALIGNED.wav")
        for item in spec.get("audio") or [{"stem": s, "name": n} for s, n in DEFAULT_AUDIO]:
            src = ws.stems_dir / f"{item['stem']}.wav"
            if not src.exists():
                print(f"  (skipping {item['name']}: no stem {src})")
                continue
            A.write_aligned(src, out / "audio" / f"{item['name']}.wav", grid.pad_s)
            files["audio"].append(f"{item['name']}.wav")

    from .guide import write_guide, write_readme
    write_readme(spec, grid, files, out / "README.txt")
    write_guide(ws, spec, grid, notes, files, out / "guide.html")
    counts = {ly["id"]: len(notes[ly["id"]]) for ly in layers}
    return out, files, counts


def kit_end_bar(ws, grid):
    """DAW bar in which the aligned audio ends."""
    import math
    try:
        dur = A.duration(ws.source) + grid.pad_s
    except Exception:
        return None
    return int(math.floor(dur / grid.bar)) + 1

"""mavpa draft: a complete first song.json from the analysis, so `mavpa build` works at once.

The draft is deliberately plain: one layer per stem, loops from consensus, one-off notes
where the loop does not apply. The agent (or you) then refines it: split layers (a hook
hiding in the 'other' stem), fix octaves, name sections, write the lesson text.
"""
import shutil
from collections import Counter

from .notes import name as note_name

DRUM_KIT = {"kick": {"note": 36, "label": "Kick"}, "snare": {"note": 38, "label": "Snare / clap / rim"},
            "hat": {"note": 42, "label": "Hats / shaker"}}


def _play(segs, active, stem, pattern="loop"):
    out = []
    for a, z, anc in segs:
        bars = [b for b in range(a, z + 1) if stem in active.get(b, ())]
        if not bars:
            continue
        a2, z2 = bars[0], bars[-1]
        skip = [b for b in range(a2, z2 + 1) if stem not in active.get(b, ())]
        e = {"pattern": pattern, "from": a2, "to": z2, "anchor": anc}
        if skip:
            e["except"] = skip
        out.append(e)
    return out


def _literal(notes, bars_ok, max_per_bar=48):
    out = {}
    for n in notes:
        if n["bar"] in bars_ok:
            out.setdefault(str(n["bar"]), []).append([n["step"], n["len"], note_name(n["pitch"]), n["vel"]])
    return {k: v for k, v in out.items() if len(v) <= max_per_bar}


def draft(ws, force=False):
    from .analyze import analyze
    from .drums import draft_drums
    from .tempo import estimate_grid
    from .transcribe import consensus, consensus_mono, get_notes

    spec = ws.spec()
    if spec.get("layers") and not force:
        raise SystemExit("song.json already has layers (maybe curated by hand). Re-run with --force to replace them; "
                         "the current file is kept as song.before-draft.json")
    if spec.get("layers"):
        shutil.copy2(ws.spec_path, ws.root / "song.before-draft.json")
    if not spec.get("grid", {}).get("bpm"):
        estimate_grid(ws, write=True)
        spec = ws.spec()
    grid = ws.grid()
    a = ws.load("analysis.json")
    if not a or a.get("grid") != grid.to_dict():
        a = analyze(ws, quiet=True)
    nbars, P = a["bars"], a["loop"]["period"]
    segs = [(s["from"], s["to"], s["anchor"]) for s in a["loop"]["segments"]] or [(1, nbars, 1)]
    active = {r["bar"]: set(r["active"]) for r in a["per_bar"]}
    in_seg = {b for s0, s1, _ in segs for b in range(s0, s1 + 1)}
    stems_on = {s for r in a["per_bar"] for s in r["active"]}
    layers, report = [], []

    if "drums" in stems_on:
        pats, info, _ = draft_drums(ws, grid, segs, P)
        pats = {k: v for k, v in pats.items() if any(set(r) != {"."} for r in v.values())}
        layers.append({"id": "drums", "name": "drums", "role": "drums", "stem": "drums", "drums": True,
                       "kit": {k: DRUM_KIT[k] for k in pats}, "velocity": {"X": 110, "x": 90, "g": 60},
                       "patterns": {"loop": {"bars": P, "grid": pats}}, "play": _play(segs, active, "drums")})
        report.append(f"drums: {', '.join(pats)} from {P}-bar loop folds")

    if "bass" in stems_on:
        notes, _ = get_notes(ws, "bass")
        pat, nrep, _ = consensus_mono(ws, grid, segs, P, 0.5)
        lit = _literal(notes, {b for b in active if "bass" in active[b] and b not in in_seg})
        layers.append({"id": "bass", "name": "bass", "role": "bass", "stem": "bass", "program": 38,
                       "patterns": {"loop": {"bars": P, "notes": pat}}, "play": _play(segs, active, "bass"), "notes": lit})
        report.append(f"bass: loop consensus over {nrep} repeats + {sum(len(v) for v in lit.values())} one-off notes")

    if "other" in stems_on:
        notes, eng = get_notes(ws, "music")
        pat, nrep, _ = consensus(notes, grid, segs, P, 0.6)
        lit = _literal(notes, {b for b in active if "other" in active[b] and b not in in_seg}, max_per_bar=24)
        layers.append({"id": "music", "name": "music (chords + hooks)", "role": "harmony", "stem": "other", "program": 48,
                       "patterns": {"loop": {"bars": P, "notes": pat}}, "play": _play(segs, active, "other"), "notes": lit})
        report.append(f"music: {eng} notes, loop consensus over {nrep} repeats")

    if "vocals" in stems_on:
        notes, _ = get_notes(ws, "vocals")
        lit = _literal(notes, {b for b in active if "vocals" in active[b]})
        first = min((int(k) for k in lit), default=1)
        card = {"answer": {"rolls": [{"from_song": {"from": first, "to": first + P - 1}, "parts": [{"layer": "vocal"}],
                                      "bar_labels": [f"bar {grid.daw_bar(b)}" for b in range(first, first + P)]}],
                           "note": "A contour, not a score: the singer slides between notes. Use it to find target notes."}}
        layers.append({"id": "vocal", "name": "vocal guide melody", "role": "vocal", "stem": "vocals", "program": 53,
                       "patterns": {}, "play": [], "notes": lit, "card": card})
        report.append(f"vocal: {sum(len(v) for v in lit.values())} guide notes (contour)")

    # harmony table: the most common chord per loop bar
    from .spec import pattern_pos
    per_pos = {k: Counter() for k in range(1, P + 1)}
    per_rom = {k: Counter() for k in range(1, P + 1)}
    for r in a["per_bar"]:
        for s0, s1, anc in segs:
            if s0 <= r["bar"] <= s1:
                k = pattern_pos(r["bar"], anc, P)
                per_pos[k][r["chord"]] += 1
                per_rom[k][r["roman"]] += 1
    chords = [per_pos[k].most_common(1)[0][0] if per_pos[k] else "" for k in range(1, P + 1)]
    romans = [per_rom[k].most_common(1)[0][0] if per_rom[k] else "" for k in range(1, P + 1)]
    ids = {ly["id"] for ly in layers}
    harmony = []
    if "music" in ids:
        h = {"title": "The loop: bass + harmony", "voicing": {"layer": "music", "pattern": "loop"}, "chords": chords,
             "functions": romans, "intro": f"The {P}-bar loop that carries most of the song. Learn it first.",
             "rolls": [{"parts": [{"layer": "music", "pattern": "loop"}], "bar_labels": chords}]}
        if "bass" in ids:
            h["bass"] = {"layer": "bass", "pattern": "loop"}
            h["rolls"].append({"parts": [{"layer": "bass", "pattern": "loop"}], "bar_labels": "loop {k}", "row": 11})
        harmony.append(h)

    key = a["key"]
    minor = key["mode"] in ("aeolian", "dorian", "phrygian")
    spec.update({
        "bars": nbars,
        "key": {"tonic": key["tonic"], "mode": key["mode"], "name": key["name"], "midi_key": key["parent_major"],
                "summary": f"Scale: {key['scale_hint']}. Home chord: {key['tonic']}{'m' if minor else ''}.",
                "readme": f"{key['name']} = {key['scale_hint']}, home chord {key['tonic']}{'m' if minor else ''}"},
        "sections": [{"name": s["name"], "from": s["from"], "to": s["to"]} for s in a["sections"]],
        "marks": [{"bars": m["bars"], "label": f"{' + '.join(m['lost'])} out",
                   "strength": "hard" if len(m["lost"]) > 1 else "soft"} for m in a["marks"]],
        "harmony": harmony,
        "layers": layers,
        "audio": [{"stem": "drums", "name": "01_drums"}, {"stem": "bass", "name": "02_bass"},
                  {"stem": "other", "name": "03_music"}, {"stem": "vocals", "name": "04_vocals"}],
    })
    spec.setdefault("guide", {})
    ws.save_spec(spec)
    print("draft song.json written:")
    for line in report:
        print(f"  {line}")
    print(f"  sections: {' | '.join(s['name'] + ' ' + str(s['from']) + '-' + str(s['to']) for s in spec['sections'])}")
    print(f"  loop chords: {' | '.join(chords)}")
    print(f"next: mavpa build {ws.root}   (then refine song.json, rebuild, mavpa verify)")
    return spec

"""guide.html + README.txt for a kit.

The guide is one self-contained HTML file (works offline). Every piece of text can
come from song.json -> "guide" / layer "card" (written by the agent); anything
missing is generated from the data. Text uses a tiny markup:
**bold**, *italic*, `mono`, and {{E4}} / {{E4 G4 B4}} / {{64}} note tokens that follow
the page's note-naming toggle (scientific C4, FL C5, Ableton C3).
"""
import base64
import json
from importlib import resources

from .notes import name as note_name
from .notes import num
from .spec import active_bars, last_bar, pattern_notes, pattern_positions, ranges

ROLE_COLOR = {"bass": "bass", "harmony": "pad", "pad": "pad", "keys": "pad2", "lead": "top", "pluck": "tick",
              "vocal": "vocal", "drums": "drums", "fx": "spark", "hook": "flick"}
COLORS = ["bass", "pad", "pad2", "flick", "tick", "top", "spark", "vocal", "drums"]


def color_of(layer):
    return layer.get("color") or ROLE_COLOR.get(layer.get("role", ""), "pad")


def count_text(grid):
    beats = "  ".join(f"{b} e & a" for b in range(1, grid.beats_per_bar + 1))
    return f"{beats} = {grid.steps_per_bar} sixteenths per bar"


def meter(grid):
    return f"{grid.beats_per_bar}/{grid.beat_unit}"


def fmt_bpm(bpm, digits=3):
    return f"{bpm:.{digits}f}".rstrip("0").rstrip(".") if abs(bpm - round(bpm)) > 1e-9 else f"{int(round(bpm))}"


def daw_list(bars, grid, n=3):
    d = [grid.daw_bar(b) for b in bars]
    if not d:
        return "—"
    return ", ".join(map(str, d[:n])) + ("…" if len(d) > n else "")


# ------------------------------------------------------------------------------------------------ rolls
def _roll(spec, layers, grid, rolld, notes_by_layer):
    by_id = {ly["id"]: ly for ly in layers}
    out = []
    bars = rolld.get("bars")
    for part in rolld.get("parts", []):
        ly = by_id[part["layer"]]
        c = part.get("color") or color_of(ly)
        mine = []
        if "from_song" in rolld:
            a, z = int(rolld["from_song"]["from"]), int(rolld["from_song"]["to"])
            bars = bars or (z - a + 1)
            for bar, s, ln, p, v, *_ in notes_by_layer[ly["id"]]:
                if a <= bar <= z:
                    mine.append({"b": bar - a + 1, "s": s, "l": ln, "p": p, "c": c})
        else:
            pat = part.get("pattern", "loop")
            pn = pattern_notes(ly, pat)
            bars = bars or int(ly["patterns"][pat].get("bars", 1))
            for k, lst in pn.items():
                for n in lst:
                    mine.append({"b": int(k), "s": n["s"], "l": n["l"], "p": n["p"], "c": c})
        for k, lst in (part.get("skip") or {}).items():
            drop = {num(x) for x in lst}
            mine = [n for n in mine if not (n["b"] == int(k) and n["p"] in drop)]
        out.extend(mine)
    ps = [n["p"] for n in out] or [60]
    lo = num(rolld["lo"]) if "lo" in rolld else min(ps) - 2
    hi = num(rolld["hi"]) if "hi" in rolld else max(ps) + 2
    labels = rolld.get("bar_labels")
    if isinstance(labels, str):
        labels = [labels.replace("{k}", str(k)) for k in range(1, bars + 1)]
    if labels is None:
        labels = [f"bar {k}" for k in range(1, bars + 1)]
    return {"title": rolld.get("title", ""), "bars": bars, "lo": lo, "hi": hi, "cell": rolld.get("cell", 10),
            "row": rolld.get("row", 12), "labels": labels, "notes": out,
            "legend": [{"label": p.get("label") or by_id[p["layer"]].get("name"),
                        "c": p.get("color") or color_of(by_id[p["layer"]])} for p in rolld.get("parts", [])]}


def _notes_table(ly, pat, notes_ann, grid):
    sn = grid.step_names()
    rows = []
    for k, lst in sorted(pattern_notes(ly, pat).items(), key=lambda kv: int(kv[0])):
        cells = " → ".join(f"{{{{{n['p']}}}}} @{sn[int(n['s']) % len(sn)]} for {n['l']}" for n in lst)
        ann = (notes_ann or {}).get(str(k))
        rows.append([f"**{k}**", cells + (f" *({ann})*" if ann else "")])
    return {"head": ["Pattern bar", "Notes (start @ step, length in 16ths)"], "rows": rows}


def _voicing_table(ly, pat, chords, extra, grid, by_id):
    sn = grid.step_names()
    rows = []
    ex = pattern_notes(by_id[extra["layer"]], extra.get("pattern", "loop")) if extra else {}
    for k, lst in sorted(pattern_notes(ly, pat).items(), key=lambda kv: int(kv[0])):
        on = sorted({n["p"] for n in lst if n["s"] == 0})
        late = ", ".join(f"{{{{{n['p']}}}}} @{sn[int(n['s']) % len(sn)]}" for n in lst if n["s"] > 0)
        tail = f" · {extra.get('label', '+ ' + by_id[extra['layer']].get('name', ''))}" if ex.get(k) else ""
        rows.append([f"**{k}**", (chords or {}).get(str(k), "") if isinstance(chords, dict) else
                     (chords[int(k) - 1] if chords and int(k) - 1 < len(chords) else ""),
                     "{{" + " ".join(map(str, on)) + "}}" if on else "—", (late or "—") + tail])
    return {"head": ["Pattern bar", "Chord", "On beat 1", "Enters later"], "rows": rows}


def _drums(ly, pat, grid):
    kit = ly.get("kit", {})
    grids = pattern_notes(ly, pat)
    insts = []
    for inst, rows in grids.items():
        meta = kit.get(inst, {})
        label = meta.get("label", inst.title()) if isinstance(meta, dict) else inst.title()
        insts.append({"label": label, "rows": [{"label": f"bar {k}", "steps": rows[k]}
                                               for k in sorted(rows, key=int)]})
    return {"instruments": insts}


def _card(c, ly, spec, layers, grid, notes, by_id):
    """One layer card. `ly` is the layer it belongs to (None for free cards such as FX notes)."""
    where = c.get("where")
    if where is None and ly is not None:
        rr = ranges(active_bars(notes[ly["id"]], grid.steps_per_bar))
        bars = ", ".join(f"{grid.daw_bar(a)}–{grid.daw_bar(b)}" if a != b else f"{grid.daw_bar(a)}" for a, b in rr[:6])
        where = f"stem {ly.get('stem', '?')} · " + (f"bars {bars}" + ("…" if len(rr) > 6 else "") if rr else "not used")
    ans = c.get("answer", {})
    answer = {"summary": ans.get("summary", "Show the answer"), "intro": ans.get("intro", ""),
              "note": ans.get("note", ""), "text": ans.get("text", ""), "rolls": [], "tables": [], "drums": None}
    for r in ans.get("rolls", []):
        answer["rolls"].append(_roll(spec, layers, grid, r, notes))
    for t in ans.get("tables", []):
        tl = by_id[t.get("layer", ly["id"] if ly else None)]
        if t["type"] == "notes":
            answer["tables"].append(_notes_table(tl, t.get("pattern", "loop"), t.get("notes"), grid))
        elif t["type"] == "voicing":
            answer["tables"].append(_voicing_table(tl, t.get("pattern", "loop"), t.get("chords"), t.get("extra"), grid, by_id))
    if ans.get("drums") or (ly is not None and ly.get("drums") and "drums" not in ans):
        d = ans.get("drums") or {}
        dl = by_id[d.get("layer", ly["id"] if ly else None)]
        answer["drums"] = _drums(dl, d.get("pattern", next(iter(dl.get("patterns", {"loop": 0})))), grid)
    if ly is not None and not ly.get("drums") and not (answer["rolls"] or answer["tables"] or answer["text"]):
        for pat in list(ly.get("patterns", {}))[:2]:
            answer["rolls"].append(_roll(spec, layers, grid, {"parts": [{"layer": ly["id"], "pattern": pat}],
                                                              "title": pat if len(ly["patterns"]) > 1 else "",
                                                              "bar_labels": "bar {k}"}, notes))
    default_color = color_of(ly) if ly is not None else "muted"
    return {"id": c.get("id") or (ly["id"] if ly else "card"),
            "title": c.get("title") or (ly.get("name", ly["id"]) if ly else ""),
            "color": c.get("color", default_color), "where": where or "", "about": c.get("about", ""),
            "monkey": c.get("monkey", default_monkey(ly, grid) if ly is not None else []),
            "answer": answer, "recipes": c.get("recipes", {}), "sound": c.get("sound", ""), "list": c.get("list", [])}


# ------------------------------------------------------------------------------------------------ data
def guide_data(ws, spec, grid, notes, files):
    from .build import kit_end_bar
    layers = spec.get("layers", [])
    by_id = {ly["id"]: ly for ly in layers}
    g = spec.get("guide", {})
    key = spec.get("key", {})
    nb = last_bar(spec)
    total_daw = grid.daw_bar(nb) + 1
    end_bar = kit_end_bar(ws, grid) or total_daw
    dur = (end_bar - 1) * grid.bar - grid.pad_s
    mins = f"{int(dur // 60)}:{int(dur % 60):02d}"

    # song map
    secs = []
    for s in spec.get("sections", []):
        a, b = grid.daw_bar(s["from"]), grid.daw_bar(s["to"])
        secs.append({"name": s.get("name", ""), "a": a, "b": b,
                     "t_daw": round((a - 1) * grid.bar, 1), "t_orig": round(max(0.0, grid.t(s["from"])), 1)})
    lanes = []
    lane_defs = g.get("lanes") or [{"layer": ly["id"]} for ly in layers]
    for ld in lane_defs:
        ly = by_id[ld["layer"]]
        sel = [n for n in notes[ly["id"]] if not ld.get("patterns") or n[5] in ld["patterns"]]
        bars = active_bars(sel, grid.steps_per_bar)
        lanes.append({"name": ld.get("name", ly.get("name", ly["id"])), "c": ld.get("color", color_of(ly)),
                      "r": [[grid.daw_bar(a), grid.daw_bar(b)] for a, b in ranges(bars)]})
    marks = [{"bars": [grid.daw_bar(b) for b in m.get("bars", [])], "label": m.get("label", ""),
              "strength": m.get("strength", "soft")} for m in spec.get("marks", [])]

    # harmony tables
    harmony = []
    for h in spec.get("harmony", []):
        bl, vl = h.get("bass"), h.get("voicing")
        n = int(h.get("bars") or by_id[vl["layer"]]["patterns"][vl.get("pattern", "loop")].get("bars", 1))
        posd = pattern_positions(by_id[vl["layer"]], vl.get("pattern", "loop"), spec)
        bpn = pattern_notes(by_id[bl["layer"]], bl.get("pattern", "loop")) if bl else {}
        vpn = pattern_notes(by_id[vl["layer"]], vl.get("pattern", "loop"))
        extras = [(e, pattern_notes(by_id[e["layer"]], e.get("pattern", "loop"))) for e in h.get("extras", [])]
        sn = grid.step_names()
        rows = []
        for k in range(1, n + 1):
            ks = str(k)
            bass = " → ".join(f"{{{{{x['p']}}}}} *@{sn[int(x['s']) % len(sn)]}*" for x in bpn.get(ks, []))
            voic = sorted({x["p"] for x in vpn.get(ks, [])})
            ext = "".join(f" + {e.get('label', by_id[e['layer']].get('name'))}" for e, pn in extras if pn.get(ks))
            chords, funcs = h.get("chords", []), h.get("functions", [])
            rows.append([f"**{k}**", daw_list(posd.get(k, []), grid), bass or "—",
                         f"**{chords[k - 1]}**" if k - 1 < len(chords) else "",
                         f"*{funcs[k - 1]}*" if k - 1 < len(funcs) else "",
                         ("{{" + " ".join(map(str, voic)) + "}}" if voic else "—") + ext])
        harmony.append({"title": h.get("title", "The loop: bass + harmony"), "intro": h.get("intro", ""),
                        "callout": h.get("callout", ""), "note": h.get("note", ""),
                        "table": {"head": ["Pattern bar", "DAW bars", by_id[bl["layer"]].get("name", "Bass") if bl else "Bass",
                                           "Chord", "Function", "Voicing (low → high)"], "rows": rows},
                        "rolls": [_roll(spec, layers, grid, r, notes) for r in h.get("rolls", [])],
                        "rolls_summary": h.get("rolls_summary", "Show the loop as a piano roll")})

    # layer cards: guide.cards (ordered, may reference a layer) or one card per layer
    card_defs = g.get("cards")
    if card_defs is None:
        card_defs = [{**(ly.get("card") or {}), "layer": ly["id"]} for ly in layers if ly.get("card") is not False]
    cards = [_card(c, by_id.get(c.get("layer")), spec, layers, grid, notes, by_id) for c in card_defs]

    verify = ws.load("verify.json")
    chips = g.get("chips") or [f"{meter(grid)} time", f"{fmt_bpm(grid.bpm)} BPM",
                               key.get("name", "key ?"), f"{nb} bars · {mins}"]
    return {
        "title": g.get("title", spec.get("title", "Untitled")),
        "page_title": f"{spec.get('title', 'Untitled')} · mavpa kit",
        "eyebrow": g.get("eyebrow", "Monkey kit · split into parts · rebuild by hand"),
        "lede": g.get("lede", "Every part of the track, decoded from the audio: the grid, the loops, the chords, "
                              "the bass, the hooks, the vocal line and the drums. Each layer is an ear-first "
                              "exercise with a hidden answer, plus a sound recipe for FL Studio, Ableton Live "
                              "and GarageBand."),
        "chips": chips,
        "grid": {"bpm": grid.bpm, "bpb": grid.beats_per_bar, "unit": grid.beat_unit, "spb": grid.steps_per_bar,
                 "lead": grid.lead_in_bars, "bar_s": grid.bar, "down": grid.downbeat, "end_bar": end_bar},
        "dna": g.get("dna") or default_dna(spec, grid, nb),
        "setup": default_setup(spec, grid, end_bar, g.get("setup", {})),
        "map": {"nb": max(total_daw, max((s["b"] for s in secs), default=0)), "sections": secs, "marks": marks,
                "lanes": lanes, "note": g.get("map_note", "")},
        "harmony": harmony,
        "cards": cards,
        "cards_intro": g.get("cards_intro", "How to use each card: do the **Monkey it** steps with the stem soloed "
                                            "*before* you open the answer. Then open the answer, fix what you "
                                            "missed, and only then build the sound."),
        "method": g.get("method") or default_method(grid),
        "plan": g.get("plan") or default_plan(layers, grid),
        "files": default_files(files, grid),
        "accuracy": g.get("accuracy") or default_accuracy(verify),
        "footer": g.get("footer", "Built with mavpa from the audio file alone: stem separation, pitch tracking and "
                                  "loop averaging, checked against the stems. For personal study only."),
    }


def default_monkey(ly, grid):
    if ly.get("drums"):
        return ["Loop 4–8 bars with the drum stem soloed. Count " + f"`{'  '.join(f'{b} e & a' for b in range(1, grid.beats_per_bar + 1))}`.",
                "Kick first: mark where the low boom lands.", "Then the snare/clap/rim, then hats, then the rest.",
                "Look for the fill bars at the end of each loop."]
    return ["Solo the stem and loop one or two bars.", "Hum the part, then find the notes on a plain sine or piano.",
            "Get *when* first (which 16th), then *what* (which note).", "Compare with the answer, fix, then build the sound."]


def default_dna(spec, grid, nb):
    key = spec.get("key", {})
    out = [f"**Meter: {meter(grid)}.** Count every bar as `{count_text(grid)}`. Set the time signature in your DAW before anything else.",
           f"**Tempo: {fmt_bpm(grid.bpm)} BPM** on a rigid grid.",
           f"**Key: {key.get('name', '?')}.** {key.get('summary', '')}".strip(),
           f"**Bar 1 is at {grid.downbeat:.3f} s in the original file.** In this kit everything is padded so that "
           f"downbeat lands exactly on **DAW bar {grid.lead_in_bars + 1}**. All bar numbers below are DAW bars."]
    return out


def default_setup(spec, grid, end_bar, over):
    bpm = fmt_bpm(grid.bpm)
    m = meter(grid)
    fl = over.get("fl") or [
        f"Set the tempo to **{grid.bpm:.3f}**.",
        f"Open *Options → Project general settings* and set the time signature to **{grid.beats_per_bar} beats per bar, "
        f"{grid.steps_per_beat} steps per beat**. The Channel Rack should now show {grid.steps_per_bar} steps per bar.",
        f"Drag every file from `audio/` into the Playlist at **bar 1**. They are already at {bpm} BPM, so make sure no "
        f"auto-stretch is applied: the clip should end just after the start of bar {end_bar}.",
        "Add Playlist markers from the song map below (right-click the time ruler → add marker), or import "
        "`midi/00_ALL_PARTS_full_song.mid`, which carries the section markers.",
        "MIDI answer keys: open a channel's Piano roll → *File → Import MIDI file*, or drag a `.mid` onto the channel. "
        "Files in `midi/full_song/` go at bar 1.",
        "Naming trap: FL calls middle C **C5**. Use the toggle at the top so every note on this page matches your piano roll."]
    abl = over.get("ableton") or [
        f"Set the tempo to **{grid.bpm:.2f}**. Click the `4 / 4` field and type **{m.replace('/', ' / ')}**.",
        "Drag the files from `audio/` to audio tracks at **1.1.1**. In each clip turn **Warp off**; they are already "
        f"exactly {bpm} BPM, and auto-warp might guess wrong.",
        "Add Locators at the section starts from the song map (*Create → Add Locator*).",
        f"MIDI answer keys: drag a file from `midi/full_song/` into a MIDI track at 1.1.1. Loop files go at bar {grid.lead_in_bars + 1} "
        "(or any loop start).",
        f"To slow down for transcription, turn Warp on (Complex Pro, Seg. BPM {bpm}) and set the song tempo to "
        f"{fmt_bpm(grid.bpm / 2, 2)}. Pitch stays, speed halves.",
        live_tracks(spec),
        "Naming trap: Ableton calls middle C **C3**. Use the toggle at the top."]
    gb = over.get("garageband") or [
        f"New empty project → set the tempo to **{int(round(grid.bpm))}** and the time signature to **{m}** "
        "(click the LCD at the top).",
        "Drag `midi/00_ALL_PARTS_full_song.mid` into the empty track area: GarageBand creates one track per part.",
        "Drag the WAVs from `audio/` in at **bar 1**. Turn off *Follow Tempo & Pitch* for each audio region "
        "(Region inspector) so nothing gets stretched.",
        "Pick sounds per track from the Library (left panel). The MIDI only carries notes, not sounds.",
        "GarageBand uses C3 for middle C, like Ableton. Use the toggle at the top."]
    if abs(grid.bpm - round(grid.bpm)) > 0.01:
        gb.insert(1, f"GarageBand only takes whole-number tempos, but this song is {grid.bpm:.3f} BPM, "
                     "so long sections will drift a little.")
    return {"fl": fl, "ableton": abl, "garageband": gb}


def live_tracks(spec):
    n = len(spec.get("layers", [])) + len(spec.get("audio") or [1, 2, 3, 4]) + 1
    if n <= 8:
        return f"Any Live edition works: the kit needs {n} tracks at most (Lite has 8, Intro 16)."
    if n <= 16:
        return f"Live Intro is enough: the kit needs {n} tracks at most (Intro has 16)."
    return f"The kit has {n} tracks: more than Live Intro's 16, so leave out the stems you don't need."


def default_method(grid):
    return [
        f"**Grid first.** Find the BPM and meter, then line the audio up so your metronome clicks with the drums. "
        f"Counting wrong (4 instead of 3, or the wrong beat as \"1\") breaks everything after it.",
        "**Map it.** Put markers at every section change before transcribing. Most songs are 2–3 loops rearranged.",
        "**Bass before chords.** The lowest note is almost always the chord root. Use a sine an octave above the "
        "bass when the sub is hard to hear.",
        "**Chords from the scale.** Once you know the key, each bass note has only one or two natural triads. "
        "Test them; your ear picks the one that \"disappears\" into the record.",
        "**Top note, then bottom, then the middle.** Ears hear outer voices best. Fill inner voices last.",
        "**Hooks are rhythm + interval.** First get *when* (which 16th), then *what* (which notes).",
        "**Melody slowed and looped.** Use 50% speed, a 2-bar loop, hum, then find the note. Write targets, not slides.",
        "**Verify with tools, not instead of ears.** Ableton's Spectrum and FL's Parametric EQ 2 both show the note "
        "name under the cursor, which is good for confirming a bass note.",
        "**Sound design last.** Notes and rhythm carry 80% of the resemblance. Then match envelope (attack/release), "
        "brightness (filter), and space (reverb).",
        "**A/B at equal loudness.** Your version will sound \"worse\" just because it's quieter, so match levels "
        "before judging.",
        "**Check against the answer key.** Mute a `midi/full_song` part under yours and compare piano rolls bar by bar."]


def default_plan(layers, grid):
    roles = [ly.get("role") for ly in layers]
    plan = [f"**Session 1, grid + bass:** set up {meter(grid)} at {fmt_bpm(grid.bpm)} and transcribe the bass loop. "
            "Checkpoint: your sine locks with the stem in every bar."]
    if any(r in ("harmony", "pad", "keys") for r in roles):
        plan.append("**Session 2, harmony:** chords for the main loop, then the voicings. Checkpoint: soloed with "
                    "the bass, it sounds like the record.")
    if any(r in ("lead", "pluck", "hook") for r in roles):
        plan.append("**Session 3, hooks:** the short melodic parts. Checkpoint: they sit on the right 16ths.")
    if "drums" in roles:
        plan.append("**Session 4, drums:** kick → snare → hats → the rest, then the fills.")
    if "vocal" in roles:
        plan.append("**Session 5, vocal guide + arrangement:** one phrase of the vocal, then lay everything out on "
                    "the song map with the drop-outs.")
    plan.append("**Last session, sound + mix:** match each patch to its stem, then A/B the whole track at equal loudness.")
    return plan


def default_files(files, grid):
    stems = ", ".join(f"`{a.rsplit('.', 1)[0]}`" for a in files["audio"][1:])
    return [f"`audio/00_full_mix_ALIGNED.wav`: the original, padded so the first downbeat = DAW bar "
            f"{grid.lead_in_bars + 1} at {fmt_bpm(grid.bpm)} BPM.",
            f"`audio/` {stems}: AI-separated stems (Demucs), same alignment. Expect some bleed.",
            "`midi/full_song/`: one answer-key file per layer, full length, aligned to the audio (drop at bar 1).",
            "`midi/00_ALL_PARTS_full_song.mid`: all layers in one multitrack file, with section markers.",
            "`midi/loops/`: building blocks that start at their own bar 1. Place them at any loop start."]


def default_accuracy(verify):
    if not verify:
        return ["Not verified yet: run `mavpa verify` and rebuild to fill this in."]
    out = []
    for item in verify.get("summary", []):
        out.append(item)
    return out or ["See work/verify.json."]


# ------------------------------------------------------------------------------------------------ writers
def fonts_css():
    """@font-face rules with the guide's fonts inlined as data URIs, so a kit's guide.html works offline.
    The fonts (Outfit, Onest; SIL OFL 1.1) live in templates/fonts/ with their licences."""
    root = resources.files("mavpa").joinpath("templates/fonts")
    meta = json.loads(root.joinpath("fonts.json").read_text(encoding="utf-8"))
    rules = ["/* Outfit and Onest, SIL Open Font License 1.1, embedded unmodified so the guide works offline */"]
    for f in meta["faces"]:
        b64 = base64.b64encode(root.joinpath(f["file"]).read_bytes()).decode("ascii")
        rules.append(f"@font-face {{ font-family: '{f['family']}'; font-style: normal; font-weight: {f['weight']}; "
                     f"font-display: swap; src: url(data:font/woff2;base64,{b64}) format('woff2'); "
                     f"unicode-range: {f['unicode_range']}; }}")
    return "\n".join(rules)


def write_guide(ws, spec, grid, notes, files, path):
    data = guide_data(ws, spec, grid, notes, files)
    tpl = resources.files("mavpa").joinpath("templates/guide.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    html = html.replace("/*__FONTS__*/", fonts_css())
    html = html.replace("__PAGE_TITLE__", _esc(data["page_title"]))
    path.write_text(html, encoding="utf-8")
    return path


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_readme(spec, grid, files, path):
    key = spec.get("key", {})
    title = spec.get("title", "Untitled").upper()
    lead = spec.get("guide", {}).get("lead_in", "lead-in (anything before the first downbeat, like a pickup, sits here)")
    drums = []
    for ly in spec.get("layers", []):
        if ly.get("drums"):
            for inst, v in ly.get("kit", {}).items():
                n = int(v["note"] if isinstance(v, dict) else v)
                drums.append((inst, n))
    abl = lambda n: note_name(n - 12).replace("#", "#")  # noqa: E731  Ableton names: middle C = C3
    lines = [
        f"{title} — MONKEY KIT", "=" * (len(title) + 14), "",
        "Open guide.html in your browser first. It is the full lesson (works offline).", "",
        "PROJECT SETTINGS",
        f"  Tempo ............ {fmt_bpm(grid.bpm)} BPM (exact, rigid grid)",
        f"  Time signature ... {meter(grid)}  (count: {count_text(grid)})",
        f"  Scale ............ {key.get('readme', key.get('name', '?'))}", "",
        "ALIGNMENT",
        "  Everything in audio/ and midi/full_song/ is aligned: drop it at bar 1.",
        f"  DAW bar 1 = {lead}.",
        f"  DAW bar {grid.lead_in_bars + 1} = the song's first downbeat.",
        "  Ableton: turn Warp OFF on the audio clips. FL Studio: make sure nothing is auto-stretched.",
        "  GarageBand: set tempo + time signature first, turn off Follow Tempo & Pitch on audio regions.", "",
        "FOLDERS",
        "  audio/00_full_mix_ALIGNED.wav ...... the original, padded to the grid",
        f"  audio/01-{len(files['audio']) - 1:02d} ........................ separated stems ("
        + ", ".join(a.rsplit('.', 1)[0][3:] for a in files["audio"][1:]) + ")",
        "  midi/full_song/ .................... answer key, one file per layer, full length",
        "  midi/00_ALL_PARTS_full_song.mid .... all layers in one multitrack file (+ section markers)",
        "  midi/loops/ ........................ pattern building blocks (each starts at its own bar 1)", "",
        "NOTE NAMES",
        "  This kit uses scientific names (middle C = C4).",
        "  FL Studio calls middle C \"C5\" (add 1 to the octave).",
        "  Ableton and GarageBand call middle C \"C3\" (subtract 1 from the octave).",
    ]
    if drums:
        lines.append("  Drum MIDI: " + ", ".join(f"{i} {n}" for i, n in drums)
                     + "  (Ableton Drum Rack " + ", ".join(abl(n) for _, n in drums) + ").")
    lines += ["", "Made with mavpa — https://github.com/WorldInnovationsDepartment/mavpa", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

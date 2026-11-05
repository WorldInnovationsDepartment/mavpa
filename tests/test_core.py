"""Fast tests: no stems, no models. Run: python -m pytest tests -q"""
import json

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from mavpa.grid import Grid
from mavpa.notes import name, num, scale_pcs
from mavpa.spec import SpecError, pattern_pos, render, validate


def test_notes_roundtrip():
    assert num("C4") == 60 and num("E1") == 28 and num("F#3") == 54 and num("Bb4") == 70
    assert name(28) == "E1" and name(61) == "C#4"
    pcs, parent = scale_pcs("E", "phrygian")
    assert parent == 0 and pcs == {0, 2, 4, 5, 7, 9, 11}


def test_grid_math():
    g = Grid(bpm=103, beats_per_bar=3, downbeat=0.5772)
    assert g.steps_per_bar == 12
    assert abs(g.pad_s - (g.bar - 0.5772)) < 1e-9
    assert abs(g.daw_t(1) - g.bar) < 1e-9            # song bar 1 = DAW bar 2
    assert g.step_names()[:5] == ["1", "1e", "1&", "1a", "2"]
    with pytest.raises(ValueError):
        Grid.from_dict({"bpm": 100, "beats_per_bar": 4, "downbeat": 5.0})


def _spec():
    return {
        "grid": {"bpm": 120, "beats_per_bar": 4, "downbeat": 0.0},
        "bars": 12,
        "layers": [
            {"id": "bass", "role": "bass", "patterns": {"loop": {"bars": 2, "notes": {"1": [[0, 16, "E1", 100]], "2": [[2, 14, "G1", 90]]}}},
             "play": [{"pattern": "loop", "from": 1, "to": 4}, {"pattern": "loop", "from": 5, "to": 12, "anchor": 6, "except": [9]}]},
            {"id": "drums", "drums": True, "kit": {"kick": {"note": 36}, "hat": 42},
             "patterns": {"loop": {"bars": 1, "grid": {"kick": {"1": "X...x..........."}, "hat": {"1": "x.x.x.x.x.x.x.x."}}}},
             "play": [{"pattern": "loop", "from": 1, "to": 2}, {"pattern": "loop", "bars": [3], "only": ["hat"], "velocity_offset": -30, "min_velocity": 40}]},
        ],
    }


def test_render_patterns_anchor_except_only():
    out = render(_spec())
    bass = out["bass"]
    assert [(b, p) for b, s, ln, p, v, pat in bass if b <= 4] == [(1, 28), (2, 31), (3, 28), (4, 31)]
    b5 = [n for n in bass if n[0] == 5][0]
    assert pattern_pos(5, 6, 2) == 2 and b5[3] == 31          # anchor 6 -> bar 5 is pattern bar 2
    assert not [n for n in bass if n[0] == 9]                   # except
    drums = out["drums"]
    assert len([n for n in drums if n[0] == 1]) == 2 + 8
    bar3 = [n for n in drums if n[0] == 3]
    assert {n[3] for n in bar3} == {42} and min(n[4] for n in bar3) == 60


def test_validate_reports_problems():
    s = _spec()
    s["layers"][0]["play"].append({"pattern": "nope"})
    s["loops"] = [{"name": "x", "layer": "missing", "from": 1, "bars": 1}]
    probs = validate(s)
    assert any("unknown pattern" in p for p in probs) and any("unknown layer" in p for p in probs)
    with pytest.raises(SpecError):
        render(s)


def test_build_writes_full_kit(tmp_path):
    from mavpa.build import build
    from mavpa.workspace import Workspace
    sr = 22050
    (tmp_path / "input").mkdir()
    sf.write(tmp_path / "input/track.wav", np.zeros((sr * 26, 2)), sr)
    spec = {"mavpa": 1, "title": "Test Song", "source": "input/track.wav", **_spec(),
            "sections": [{"name": "A", "from": 1, "to": 6}, {"name": "B", "from": 7, "to": 12}]}
    (tmp_path / "song.json").write_text(json.dumps(spec))
    out, files, counts = build(Workspace(tmp_path), with_audio=False)
    assert files["full_song"] == ["01_bass.mid", "02_drums.mid"]
    pm = pretty_midi.PrettyMIDI(str(out / "midi/full_song/01_bass.mid"))
    first = pm.instruments[0].notes[0]
    assert first.pitch == 28 and abs(first.start - 2.0) < 1e-6   # 120 BPM 4/4: song bar 1 = DAW bar 2 = 2.0 s
    assert pm.time_signature_changes[0].numerator == 4
    html = (out / "guide.html").read_text()
    assert "Test Song" in html and "/*__DATA__*/" not in html
    assert (out / "README.txt").read_text().startswith("TEST SONG")
    assert (out / "midi/loops").exists() and files["loops"]


def test_fit_bpm_on_clicks():
    from mavpa.tempo import _onset_env, fit_bpm
    sr = 22050
    y = np.zeros(sr * 20)
    for k in range(int(20 / 0.6)):
        i = int((0.31 + k * 0.6) * sr)
        y[i:i + 200] += np.hanning(200)
    oenv = _onset_env(y, 64)
    bpm, ph, _ = fit_bpm(oenv, sr / 64, 99.0, 19.5)
    assert abs(bpm - 100) < 0.05 and abs(ph - 0.31) < 0.02

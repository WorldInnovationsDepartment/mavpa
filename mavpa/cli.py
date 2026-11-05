"""mavpa command line. Every command prints evidence an agent (or a person) can reason about.

    mavpa doctor                         check the toolbox
    mavpa new AUDIO                      make a workspace (copy + decode)
    mavpa separate WS                    Demucs stems -> work/stems/
    mavpa grid WS [--write]              tempo, meter, downbeat (+ evidence)
    mavpa analyze WS                     key, chords per bar, stem activity, loop period, sections
    mavpa transcribe WS --part bass      draft notes for one stem + loop consensus
    mavpa drums WS                       drum hits folded over the loop (+ draft grid)
    mavpa view WS loop|spec|overlay|structure ...   pictures to look at
    mavpa draft WS                       write a complete first song.json from the analysis
    mavpa build WS                       song.json -> kit/ (audio, MIDI, loops, guide.html, README)
    mavpa verify WS                      score the kit against the stems
"""
import argparse
import sys


def _bars(text):
    if not text:
        return None
    a, _, b = text.partition("-")
    return int(a), int(b or a)


def cmd_doctor(a):
    from .doctor import doctor
    sys.exit(doctor())


def cmd_new(a):
    from .workspace import create
    root = create(a.audio, home=a.home, name=a.name, title=a.title)
    print(f"workspace: {root}")
    print(f"next: mavpa separate {root}")


def cmd_separate(a):
    from .separate import separate
    from .workspace import Workspace
    ws = Workspace(a.ws)
    out = separate(ws, model=a.model, device=a.device, shifts=a.shifts)
    print(f"stems: {out}")


def cmd_grid(a):
    from .tempo import estimate_grid
    from .workspace import Workspace
    ws = Workspace(a.ws)
    estimate_grid(ws, bpm=a.bpm, meter=a.meter, downbeat=a.downbeat, lo=a.min_bpm, hi=a.max_bpm, write=a.write)


def cmd_analyze(a):
    from .analyze import analyze
    from .workspace import Workspace
    analyze(Workspace(a.ws), period=a.period, quiet=a.quiet)


def cmd_transcribe(a):
    from .transcribe import transcribe_cmd
    from .workspace import Workspace
    transcribe_cmd(Workspace(a.ws), a.part, bars=_bars(a.bars), period=a.period, anchor=a.anchor,
                   min_frac=a.min_frac, engine=a.engine)


def cmd_drums(a):
    from .drums import drums_cmd
    from .workspace import Workspace
    drums_cmd(Workspace(a.ws), bars=_bars(a.bars), period=a.period, anchor=a.anchor, components=a.components)


def cmd_view(a):
    from .views import view_cmd
    from .workspace import Workspace
    path = view_cmd(Workspace(a.ws), a.kind, stem=a.stem, bars=_bars(a.bars), period=a.period, anchor=a.anchor,
                    lo=a.lo, hi=a.hi, layer=a.layer, out=a.out)
    print(f"wrote {path}")


def cmd_draft(a):
    from .draft import draft
    from .workspace import Workspace
    draft(Workspace(a.ws), force=a.force)


def cmd_build(a):
    from .build import build
    from .workspace import Workspace
    out, files, counts = build(Workspace(a.ws), out=a.out, with_audio=not a.no_audio)
    print(f"kit: {out}")
    print(f"  audio: {len(files['audio'])} files · full_song MIDI: {len(files['full_song'])} · loops: {len(files['loops'])}")
    print("  notes per layer: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"  open: {out / 'guide.html'}")


def cmd_verify(a):
    from .verify import verify
    from .workspace import Workspace
    ok = verify(Workspace(a.ws))
    sys.exit(0 if ok else 2)


def main(argv=None):
    import warnings
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser(prog="mavpa", description="Monkey see, monkey do: split a track into parts, rebuild it by hand.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="check dependencies")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("new", help="create a workspace from an audio file")
    s.add_argument("audio")
    s.add_argument("--home", help="parent folder for workspaces (default $MAVPA_HOME or ~/mavpa)")
    s.add_argument("--name", help="workspace folder name (default: slug of the title)")
    s.add_argument("--title", help="song title (default: from the file name)")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("separate", help="split into stems with Demucs")
    s.add_argument("ws")
    s.add_argument("--model", default="htdemucs_ft", help="htdemucs_ft (4 stems, best), htdemucs, htdemucs_6s (+piano, guitar)")
    s.add_argument("--device", default="auto", help="auto | cpu | cuda | mps")
    s.add_argument("--shifts", type=int, default=1, help="more = slightly better, slower")
    s.set_defaults(fn=cmd_separate)

    s = sub.add_parser("grid", help="tempo, meter and downbeat")
    s.add_argument("ws")
    s.add_argument("--bpm", type=float, help="force a tempo (still refines phase)")
    s.add_argument("--meter", type=int, choices=[2, 3, 4, 5, 6, 7], help="force beats per bar")
    s.add_argument("--downbeat", type=float, help="force the time (s) of a downbeat")
    s.add_argument("--min-bpm", type=float, default=70)
    s.add_argument("--max-bpm", type=float, default=180)
    s.add_argument("--write", action="store_true", help="store the result in song.json")
    s.set_defaults(fn=cmd_grid)

    s = sub.add_parser("analyze", help="key, chords, stem activity, loop period, sections")
    s.add_argument("ws")
    s.add_argument("--period", type=int, help="force the loop length in bars")
    s.add_argument("--quiet", action="store_true", help="skip the per-bar table")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("transcribe", help="draft notes for a stem (+ loop consensus)")
    s.add_argument("ws")
    s.add_argument("--part", required=True, help="bass | music | vocals (or a stem name)")
    s.add_argument("--bars", help="song bars A-B for the consensus, e.g. 9-52")
    s.add_argument("--period", type=int, help="loop length in bars for the consensus")
    s.add_argument("--anchor", type=int, help="a song bar where the loop starts (default: --bars start)")
    s.add_argument("--min-frac", type=float, default=0.5, help="keep notes present in at least this share of repeats")
    s.add_argument("--engine", default="auto", help="music engine: auto | basic-pitch | cqt")
    s.set_defaults(fn=cmd_transcribe)

    s = sub.add_parser("drums", help="drum hits per band folded over the loop")
    s.add_argument("ws")
    s.add_argument("--bars", help="song bars A-B")
    s.add_argument("--period", type=int, help="loop length in bars")
    s.add_argument("--anchor", type=int)
    s.add_argument("--components", type=int, default=0, help="also run NMF with this many components")
    s.set_defaults(fn=cmd_drums)

    s = sub.add_parser("view", help="draw a picture into views/")
    s.add_argument("ws")
    s.add_argument("kind", choices=["loop", "spec", "overlay", "structure"])
    s.add_argument("--stem", default="other")
    s.add_argument("--bars", help="song bars A-B")
    s.add_argument("--period", type=int, help="loop length (loop view)")
    s.add_argument("--anchor", type=int)
    s.add_argument("--lo", default=None, help="lowest note, e.g. C2")
    s.add_argument("--hi", default=None, help="highest note, e.g. C7")
    s.add_argument("--layer", help="overlay: song.json layer id to draw on top")
    s.add_argument("--out", help="output png path")
    s.set_defaults(fn=cmd_view)

    s = sub.add_parser("draft", help="write a complete first song.json from the analysis")
    s.add_argument("ws")
    s.add_argument("--force", action="store_true", help="overwrite layers/sections already in song.json")
    s.set_defaults(fn=cmd_draft)

    s = sub.add_parser("build", help="song.json -> kit")
    s.add_argument("ws")
    s.add_argument("--out", help="kit folder (default <ws>/kit)")
    s.add_argument("--no-audio", action="store_true", help="skip the aligned WAVs (fast rebuilds)")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("verify", help="score the kit against the stems")
    s.add_argument("ws")
    s.set_defaults(fn=cmd_verify)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()

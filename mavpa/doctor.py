"""mavpa doctor: is the toolbox ready?"""
import importlib
import platform
import shutil
import sys

CORE = ["numpy", "scipy", "librosa", "soundfile", "pretty_midi", "mido", "matplotlib", "sklearn"]
HEAVY = ["torch", "demucs"]
OPTIONAL = ["basic_pitch", "onnxruntime"]


def _ver(mod):
    import logging
    logging.getLogger().setLevel(logging.ERROR)     # basic-pitch warns about optional backends on import
    try:
        m = importlib.import_module(mod)
        return getattr(m, "__version__", "ok")
    except Exception as e:  # noqa: BLE001
        return None if isinstance(e, ImportError) else f"error: {e}"


def doctor():
    from . import __version__
    print(f"mavpa {__version__} · Python {sys.version.split()[0]} · {platform.system()} {platform.machine()}")
    bad = 0
    for group, mods, need in (("core", CORE, True), ("stems", HEAVY, True), ("music notes", OPTIONAL, False)):
        for mod in mods:
            v = _ver(mod)
            ok = v is not None and not str(v).startswith("error")
            bad += (not ok) and need
            print(f"  {'ok ' if ok else ('-- ' if not need else 'NO ')} {group:12s} {mod:14s} {v or 'missing'}")
    ff = shutil.which("ffmpeg")
    print(f"  {'ok ' if ff else '-- '} {'decode':12s} {'ffmpeg':14s} {ff or 'missing (mp3 decoding falls back to librosa)'}")
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  ok  {'device':12s} {'demucs on':14s} {dev}")
    except ImportError:
        pass
    from .workspace import DEFAULT_HOME
    print(f"  workspaces go to {DEFAULT_HOME} (set MAVPA_HOME to change)")
    print("ready" if not bad else f"{bad} required package(s) missing: run bin/mavpa once (it installs them)")
    return 0 if not bad else 1

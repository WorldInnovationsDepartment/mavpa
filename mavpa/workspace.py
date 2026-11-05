"""A workspace is one folder per track:

    <ws>/song.json        the curated answer (the agent edits this)
    <ws>/input/           original file + decoded track.wav
    <ws>/work/            stems, analysis json, draft transcriptions, verify.json
    <ws>/views/           pictures for eyes (human or agent)
    <ws>/kit/             the finished monkey kit (mavpa build)
"""
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

from .grid import Grid

DEFAULT_HOME = os.environ.get("MAVPA_HOME", "~/mavpa")
STEMS4 = ("drums", "bass", "other", "vocals")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "track"


def title_from_filename(path):
    stem = Path(path).stem
    stem = re.sub(r"\s*\(\d+\)$", "", stem)          # "Song (1)" download duplicates
    stem = re.sub(r"[_]+", " ", stem).strip()
    return stem or "Untitled"


class Workspace:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise SystemExit(f"workspace not found: {self.root}  (create one with: mavpa new <audio>)")

    # ---------------------------------------------------------------- paths
    @property
    def spec_path(self):
        return self.root / "song.json"

    @property
    def work(self):
        p = self.root / "work"
        p.mkdir(exist_ok=True)
        return p

    @property
    def views(self):
        p = self.root / "views"
        p.mkdir(exist_ok=True)
        return p

    @property
    def kit(self):
        return self.root / "kit"

    def path(self, rel):
        p = Path(rel)
        return p if p.is_absolute() else self.root / p

    @property
    def source(self):
        return self.path(self.spec().get("source", "input/track.wav"))

    @property
    def stems_dir(self):
        return self.path(self.spec().get("stems", "work/stems/htdemucs_ft"))

    def stem(self, name):
        if name in ("mix", "full", "track"):
            return self.source
        p = self.stems_dir / f"{name}.wav"
        if not p.exists():
            raise SystemExit(f"stem '{name}' not found at {p}. Run: mavpa separate {self.root}")
        return p

    def has_stems(self):
        return all((self.stems_dir / f"{s}.wav").exists() for s in STEMS4)

    # ---------------------------------------------------------------- json
    def spec(self):
        if not self.spec_path.exists():
            raise SystemExit(f"no song.json in {self.root}")
        with open(self.spec_path, encoding="utf-8") as f:
            return json.load(f)

    def save_spec(self, spec):
        dump_json(self.spec_path, spec)

    def grid(self):
        g = self.spec().get("grid")
        if not g or not g.get("bpm"):
            raise SystemExit("song.json has no grid yet. Run: mavpa grid <ws> --write")
        return Grid.from_dict(g)

    def load(self, name, default=None):
        p = self.work / name
        if not p.exists():
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def save(self, name, data):
        dump_json(self.work / name, data)
        return self.work / name


def dump_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=_np_default)
        f.write("\n")
    os.replace(tmp, path)


def _np_default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    raise TypeError(f"not JSON serialisable: {type(o)}")


def create(audio, home=None, name=None, title=None):
    """mavpa new: copy + decode the audio into a fresh workspace."""
    from .audio import decode

    audio = Path(audio).expanduser().resolve()
    if not audio.exists():
        raise SystemExit(f"audio file not found: {audio}")
    title = title or title_from_filename(audio)
    root = Path(home or DEFAULT_HOME).expanduser().resolve() / (name or slugify(title))
    (root / "input").mkdir(parents=True, exist_ok=True)
    original = root / "input" / f"original{audio.suffix.lower()}"
    if not original.exists():
        shutil.copy2(audio, original)
    track = root / "input" / "track.wav"
    if not track.exists():
        decode(original, track)
    ws_spec = root / "song.json"
    if not ws_spec.exists():
        dump_json(ws_spec, {
            "mavpa": 1,
            "title": title,
            "source": "input/track.wav",
            "stems": "work/stems/htdemucs_ft",
        })
    for d in ("work", "views"):
        (root / d).mkdir(exist_ok=True)
    return root

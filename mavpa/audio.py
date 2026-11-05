"""Audio I/O helpers (decode, load, align)."""
import shutil
import subprocess

import numpy as np
import soundfile as sf


def decode(src, dst, sr=44100):
    """Decode any audio file to 16-bit stereo WAV. Uses ffmpeg when present."""
    src, dst = str(src), str(dst)
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-ac", "2", "-ar", str(sr),
                        "-c:a", "pcm_s16le", dst], check=True)
        return dst
    import librosa
    y, _ = librosa.load(src, sr=sr, mono=False)
    if y.ndim == 1:
        y = np.vstack([y, y])
    sf.write(dst, y[:2].T, sr, subtype="PCM_16")
    return dst


def load_mono(path, sr=22050):
    import librosa
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y


def duration(path):
    return sf.info(str(path)).duration


def write_aligned(src, dst, pad_s):
    """Prepend pad_s seconds of silence so the song's bar 1 lands on a DAW bar line."""
    y, sr = sf.read(str(src), always_2d=True)
    pad = np.zeros((int(round(pad_s * sr)), y.shape[1]), dtype=y.dtype)
    sf.write(str(dst), np.vstack([pad, y]), sr, subtype="PCM_16")


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-9))

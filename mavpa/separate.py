"""mavpa separate: Demucs stems (drums, bass, other, vocals) via the Python API.

Audio I/O goes through soundfile (not torchaudio), so it works across torch versions.
Apple MPS fails on Demucs' large convolutions, so "auto" means CUDA if present, else CPU.
First run downloads the model weights (~300 MB for htdemucs_ft) into the torch cache.
"""
import numpy as np
import soundfile as sf


def pick_device(device):
    import torch
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def separate(ws, model="htdemucs_ft", device="auto", shifts=1, out=None):
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    out = out or (ws.work / "stems" / model)
    out.mkdir(parents=True, exist_ok=True)
    m = get_model(model)
    m.eval()
    y, sr = sf.read(str(ws.source), always_2d=True, dtype="float32")
    if sr != m.samplerate:
        import librosa
        y = librosa.resample(y.T, orig_sr=sr, target_sr=m.samplerate).T
        sr = m.samplerate
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    y = y[:, :2]
    wav = torch.from_numpy(np.ascontiguousarray(y.T))
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    dev = pick_device(device)
    print(f"demucs {model} on {dev}: {y.shape[0] / sr:.0f}s of audio "
          f"({'a laptop CPU needs roughly 2-4x the song length; --model htdemucs is ~4x faster' if dev == 'cpu' else 'GPU: about a minute'})")
    with torch.no_grad():
        sources = apply_model(m, ((wav - mean) / std)[None], device=dev, shifts=shifts, split=True, overlap=0.25,
                              progress=True)[0]
    sources = sources * std + mean
    for name, src in zip(m.sources, sources):
        sf.write(str(out / f"{name}.wav"), src.cpu().numpy().T, sr, subtype="FLOAT")
    spec = ws.spec()
    rel = out.relative_to(ws.root) if out.is_relative_to(ws.root) else out
    if spec.get("stems") != str(rel):
        spec["stems"] = str(rel)
        ws.save_spec(spec)
    return out

"""Render an arbitrary text file in the cloned voice on the GPU station.

Usage: python soc_read_remote.py <textfile> <out_wav>
Env: REF (default ~/cb_stage/reference_new.wav), MODEL_DIR, CFG=0.3, EXAG=0.4, TEMP_AUDIO=0.9, MAX_WORDS=55
"""
import os, re, sys, time
import torch, torchaudio as ta, librosa
from pathlib import Path

HOME = Path.home()
REF = os.environ.get("REF", str(HOME / "cb_stage" / "reference_new.wav"))
MODEL_DIR = os.environ.get("MODEL_DIR")
if not MODEL_DIR:
    for c in [HOME/"cb_stage"/"models"/"full", HOME/"cb_stage"/"models", HOME/"models"/"full"]:
        if (c / "t3_cfg.safetensors").exists():
            MODEL_DIR = str(c); break
    else:
        MODEL_DIR = str(HOME/"cb_stage"/"models"/"full")
GAP = 0.30
MAX_WORDS = int(os.environ.get("MAX_WORDS", "55"))

text = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# pronunciation layer (TTS input only)
text = text.replace("zero-nine-three-zero", "zero nine three zero")
text = re.sub(r"\bSOC\b", "sock", text)
text = re.sub(r"\bEXCON\b", "ex con", text)
text = re.sub(r"\bENDEX\b", "end ex", text)
text = re.sub(r"\bLANTERN\b", "Lantern", text)
text = re.sub(r"\bS6\b", "S six", text)
text = re.sub(r"\bIT\b", "I T", text)
text = re.sub(r"\bZulu\b", "zoo loo", text)

paras = [p.strip() for p in text.split("\n\n") if p.strip()]
chunks, cur, cur_w = [], [], 0
for p in paras:
    w = len(p.split())
    if cur and cur_w + w > MAX_WORDS:
        chunks.append(" ".join(cur)); cur, cur_w = [], 0
    cur.append(p); cur_w += w
if cur:
    chunks.append(" ".join(cur))

sys.path.insert(0, str(HOME / "cb_remote"))
from chatterbox.tts import ChatterboxTTS
device = "cuda" if torch.cuda.is_available() else "cpu"
print("DEVICE", device, "chunks", len(chunks), flush=True)
model = ChatterboxTTS.from_local(MODEL_DIR, device=device)
model.prepare_conditionals(REF, exaggeration=0.4)
wavs = []
for i, c in enumerate(chunks):
    t = time.time()
    w = model.generate(c, cfg_weight=0.3, exaggeration=0.4, temperature=0.9).squeeze(0).cpu()
    wavs.append(w)
    print(f"chunk {i+1}/{len(chunks)} {len(w)/model.sr:.1f}s ({time.time()-t:.1f}s)", flush=True)
gap = torch.zeros(int(GAP * model.sr))
full = wavs[0]
for w in wavs[1:]:
    full = torch.cat([full, gap, w])
y48 = librosa.resample(full.numpy(), orig_sr=model.sr, target_sr=48000)
y48 = y48 / float(abs(y48).max()) * 0.891
ta.save(str(out), torch.from_numpy(y48).unsqueeze(0), 48000, encoding="PCM_S", bits_per_sample=16)
print(f"[done] {out} {len(y48)/48000:.2f}s", flush=True)

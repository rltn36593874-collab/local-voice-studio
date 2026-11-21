"""Supertonic-3 음성 스타일 × 말 속도 변형 생성(QA 재청취용). 사용: python supertonic_variants.py <out_root> <styles,..> <speeds,..> <sent.tsv>...
출력: out_root/<스타일>_sp<속도>/<라벨>.wav (16bit PCM). 마지막 줄 RESULT json."""
import json, os, sys, time
import numpy as np
import soundfile as sf
from supertonic import TTS

out_root, styles, speeds = sys.argv[1], sys.argv[2].split(","), [float(x) for x in sys.argv[3].split(",")]
sents = [l.rstrip("\n").split("\t", 1) for f in sys.argv[4:] for l in open(f, encoding="utf-8") if l.strip()]
t0 = time.perf_counter()
m = TTS(model="supertonic-3", intra_op_num_threads=10)
load_s = time.perf_counter() - t0
rows = []
for st in styles:
    style = m.get_voice_style(st)
    for sp in speeds:
        d = os.path.join(out_root, f"{st}_sp{sp:.2f}")
        os.makedirs(d, exist_ok=True)
        a = p = 0.0
        for label, text in sents:
            t1 = time.perf_counter()
            wav, _ = m.synthesize(text, style, speed=sp, lang="ko")
            p += time.perf_counter() - t1
            wav = np.clip(np.asarray(wav, dtype=np.float32).squeeze(), -1, 1)
            a += len(wav) / m.sample_rate
            sf.write(os.path.join(d, f"{label}.wav"), wav, m.sample_rate, subtype="PCM_16")
        rows.append({"style": st, "speed": sp, "audio_s": round(a, 1), "proc_s": round(p, 1), "rtf": round(p / a, 3)})
print("RESULT " + json.dumps({"engine": "supertonic-3", "load_s": round(load_s, 2), "sentences": len(sents), "rows": rows}, ensure_ascii=False))

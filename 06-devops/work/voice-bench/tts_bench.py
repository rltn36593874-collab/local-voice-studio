"""TTS CPU 실측 (melo | supertonic). 사용: python tts_bench.py <engine> <threads> <out_dir> <sentences.tsv>
문장 파일: 라벨 \t 문장. 문장마다 16bit PCM WAV, 끝으로 1분 분량 문단(문장들을 이어 붙여 약 350자 이상)을 'P1min.wav'로 만든다.
첫 음성 시간 = 모델 로드 후 첫 문장(L1) 요청부터 WAV 배열이 나올 때까지(비스트리밍 엔진이라 문장 전체 생성 시간과 같다).
"""
import json, os, sys, time
import numpy as np
import soundfile as sf

engine, threads, out_dir, sent_file = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
os.makedirs(out_dir, exist_ok=True)
sents = [l.rstrip("\n").split("\t", 1) for l in open(sent_file, encoding="utf-8") if l.strip()]
para = " ".join(s for _, s in sents)
while len(para) < 350:
    para += " " + " ".join(s for _, s in sents)
sents.append(("P1min", para))

t0 = time.perf_counter()
if engine == "melo":
    import torch
    torch.set_num_threads(threads)
    from melo.api import TTS
    m = TTS(language="KR", device="cpu")
    spk = m.hps.data.spk2id["KR"]
    sr = m.hps.data.sampling_rate
    def synth(text):
        return m.tts_to_file(text, spk, None, speed=1.0, quiet=True)
elif engine == "supertonic":
    from supertonic import TTS
    m = TTS(model="supertonic-3", intra_op_num_threads=threads)
    style = m.get_voice_style("F1")
    sr = m.sample_rate
    def synth(text):
        wav, _ = m.synthesize(text, style, lang="ko")
        return np.asarray(wav).squeeze()
else:
    raise SystemExit("engine?")
load_s = time.perf_counter() - t0

rows, tot_a, tot_p = [], 0.0, 0.0
for label, text in sents:
    t1 = time.perf_counter()
    wav = np.asarray(synth(text), dtype=np.float32).squeeze()
    p = time.perf_counter() - t1
    a = len(wav) / sr
    sf.write(os.path.join(out_dir, f"{label}.wav"), np.clip(wav, -1, 1), sr, subtype="PCM_16")
    rows.append({"label": label, "chars": len(text), "audio_s": round(a, 2), "proc_s": round(p, 2), "rtf": round(p / a, 3)})
    if label != "P1min":
        tot_a += a; tot_p += p
p1 = rows[-1]
print("RESULT " + json.dumps({
    "engine": engine, "threads": threads, "sr": sr, "load_s": round(load_s, 2),
    "first_audio_s": rows[0]["proc_s"], "L1_5_audio_s": round(tot_a, 1), "L1_5_proc_s": round(tot_p, 1),
    "L1_5_rtf": round(tot_p / tot_a, 3), "p1min": p1,
    "sec_per_audio_min": round(p1["proc_s"] / p1["audio_s"] * 60, 1), "rows": rows}, ensure_ascii=False))

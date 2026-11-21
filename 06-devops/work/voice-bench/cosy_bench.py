"""Fun-CosyVoice3-0.5B CPU 실측(제로샷). 참조 음성은 TTS로 만든 합성음만 쓴다(실존 화자 복제 금지).
사용: python cosy_bench.py <model_dir> <threads> <out_dir> <ref.wav> <ref_text> <sentences.tsv>
측정: 로드, 참조 음성 등록(목소리 특징 추출), 문장별 생성(등록 화자 재사용), 첫 문장 스트리밍 첫 청크 시간."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "engines", "CosyVoice")
sys.path[:0] = [REPO, os.path.join(REPO, "third_party", "Matcha-TTS")]
import torch
import numpy as np
import soundfile as sf

model_dir, threads, out_dir, ref_wav, ref_text, sent_file = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
torch.set_num_threads(threads)
os.makedirs(out_dir, exist_ok=True)
sents = [l.rstrip("\n").split("\t", 1) for l in open(sent_file, encoding="utf-8") if l.strip()]

from cosyvoice.cli.cosyvoice import AutoModel
t0 = time.perf_counter()
cv = AutoModel(model_dir=model_dir)
load_s = time.perf_counter() - t0
sr = cv.sample_rate
prompt = "You are a helpful assistant.<|endofprompt|>" + ref_text

t1 = time.perf_counter()
assert cv.add_zero_shot_spk(prompt, ref_wav, "ref")
enroll_s = time.perf_counter() - t1


def gen(text, stream=False):
    return cv.inference_zero_shot(text, prompt, ref_wav, zero_shot_spk_id="ref", stream=stream)


# 첫 문장 스트리밍: 첫 청크까지 시간
t2 = time.perf_counter()
first_chunk = None
for out in gen(sents[0][1], stream=True):
    first_chunk = time.perf_counter() - t2
    break

rows, ta, tp = [], 0.0, 0.0
for label, text in sents:
    t3 = time.perf_counter()
    wav = torch.cat([o["tts_speech"] for o in gen(text)], dim=1).squeeze(0).numpy()
    p = time.perf_counter() - t3
    a = len(wav) / sr
    sf.write(os.path.join(out_dir, f"{label}.wav"), np.clip(wav, -1, 1), sr, subtype="PCM_16")
    rows.append({"label": label, "audio_s": round(a, 2), "proc_s": round(p, 2), "rtf": round(p / a, 3)})
    ta += a; tp += p
print("RESULT " + json.dumps({"engine": "Fun-CosyVoice3-0.5B", "threads": threads, "sr": sr, "load_s": round(load_s, 2),
                              "enroll_s": round(enroll_s, 2), "first_chunk_stream_s": round(first_chunk, 2) if first_chunk else None,
                              "first_audio_s": rows[0]["proc_s"], "audio_s": round(ta, 1), "proc_s": round(tp, 1),
                              "rtf": round(tp / ta, 3), "rows": rows}, ensure_ascii=False))

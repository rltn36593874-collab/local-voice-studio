"""faster-whisper CPU 실측. 사용:
python stt_fw.py <model> <threads> <out_dir> <manifest.tsv>   # manifest: wav경로 \t 정답(없으면 빈칸)
결과: out_dir/<이름>.txt, .srt, 마지막 줄 RESULT json
"""
import json, os, re, sys, time
import soundfile as sf

model_name, threads, out_dir, manifest = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
os.makedirs(out_dir, exist_ok=True)


def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return None
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1], len(r)


def ts(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


assert cer("가나다", "가나라") == (1, 3) and norm("A b,c!") == "abc"

from faster_whisper import WhisperModel
t0 = time.perf_counter()
model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads,
                     download_root=os.path.join(os.environ.get("HF_HOME", "."), "fw"))
load_s = time.perf_counter() - t0

rows = [l.rstrip("\n").split("\t") for l in open(manifest, encoding="utf-8") if l.strip()]
tot_audio = tot_proc = 0.0
edits = refs = 0
first_seg = []
for path, *ref in rows:
    dur = sf.info(path).duration
    t1 = time.perf_counter()
    segs, info = model.transcribe(path, beam_size=5, language="ko")
    out, first = [], None
    for s in segs:
        if first is None:
            first = time.perf_counter() - t1
        out.append(s)
    proc = time.perf_counter() - t1
    tot_audio += dur; tot_proc += proc
    if first is not None:
        first_seg.append(first)
    hyp = " ".join(s.text.strip() for s in out)
    name = os.path.basename(os.path.dirname(path)) + "_" + os.path.splitext(os.path.basename(path))[0]  # 폴더명 접두어: melo/L1, supertonic/L1 충돌 방지
    open(os.path.join(out_dir, name + ".txt"), "w", encoding="utf-8").write(hyp + "\n")
    with open(os.path.join(out_dir, name + ".srt"), "w", encoding="utf-8") as f:
        for i, s in enumerate(out, 1):
            f.write(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text.strip()}\n\n")
    if ref and ref[0]:
        c = cer(ref[0], hyp)
        if c:
            edits += c[0]; refs += c[1]

print("RESULT " + json.dumps({
    "engine": "faster-whisper", "model": model_name, "compute": "int8", "threads": threads,
    "files": len(rows), "load_s": round(load_s, 2), "audio_s": round(tot_audio, 1), "proc_s": round(tot_proc, 1),
    "rtf": round(tot_proc / tot_audio, 3) if tot_audio else None,
    "first_seg_s_avg": round(sum(first_seg) / len(first_seg), 2) if first_seg else None,
    "cer": round(edits / refs, 4) if refs else None, "ref_chars": refs}, ensure_ascii=False))

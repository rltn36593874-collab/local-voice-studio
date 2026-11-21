"""Build a blind, loudness-matched listening set + scorecard (stdlib only).

Usage:
  python -I make_listening_set.py build <manifest.csv> <out_dir> <round, e.g. R2> [--seed N]
  python -I make_listening_set.py selftest

manifest.csv (UTF-8, header): path,label,text
  path  = WAV (16-bit PCM or 32-bit float, any sample rate, mono or first channel)
  label = hidden answer (engine/voice/sentence id), written only to ANSWER_KEY.json
  text  = sentence shown to the listener next to the file
"""
import array
import csv
import json
import math
import os
import random
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir
from audio_check import read_audio  # noqa: E402

TARGET_DBFS = -20.0     # RMS of the voiced part after matching
PEAK_LIMIT_DBFS = -1.0  # never exceed; gain is lowered instead (recorded in the key)
REL_SILENCE_DB = 35.0   # frame is silence if > 35 dB below the loudest frame (works for very quiet recordings)
EDGE_SEC = 0.2          # leading/trailing silence kept
FRAME_SEC = 0.02


def _db(v):
    return 20 * math.log10(max(v, 1e-9) / 32768.0)


def prepare(path):
    sr, ch, a = read_audio(path)
    f = max(1, int(sr * FRAME_SEC))
    frames = [a[i:i + f] for i in range(0, len(a), f)]
    rms = [math.sqrt(sum(s * s for s in x) / len(x)) for x in frames]
    thr = max(rms) * 10 ** (-REL_SILENCE_DB / 20)
    voiced = [i for i, r in enumerate(rms) if r >= thr]
    if not voiced:
        raise ValueError(f"{path}: no voiced audio")
    edge = int(EDGE_SEC / FRAME_SEC)
    lo, hi = max(0, voiced[0] - edge), min(len(frames), voiced[-1] + 1 + edge)
    trimmed = array.array("d")
    for x in frames[lo:hi]:
        trimmed.extend(x)
    v = [s for i in voiced for s in frames[i]]
    voiced_rms = math.sqrt(sum(s * s for s in v) / len(v))
    gain_db = TARGET_DBFS - _db(voiced_rms)
    peak = max(abs(s) for s in trimmed)
    limited = False
    if _db(peak) + gain_db > PEAK_LIMIT_DBFS:
        gain_db = PEAK_LIMIT_DBFS - _db(peak)
        limited = True
    g = 10 ** (gain_db / 20)
    out = array.array("h", (max(-32768, min(32767, int(round(s * g)))) for s in trimmed))
    return sr, out, {"gain_db": round(gain_db, 1), "peak_limited": limited,
                     "voiced_rms_after": round(_db(voiced_rms) + gain_db, 1), "sec": round(len(out) / sr, 2)}


def build(manifest, out_dir, rnd, seed):
    with open(manifest, encoding="utf-8", newline="") as f:
        items = [(r["path"], r["label"], r["text"]) for r in csv.DictReader(f)]
    rng = random.Random(seed)
    rng.shuffle(items)
    os.makedirs(out_dir, exist_ok=True)
    key = {"round": rnd, "seed": seed, "target_voiced_rms_dbfs": TARGET_DBFS, "clips": {}}
    rows = []
    for n, (path, label, text) in enumerate(items, 1):
        sr, pcm, info = prepare(path)
        name = f"{rnd}-{n:02d}"
        if sys.byteorder == "big":
            pcm.byteswap()
        with wave.open(os.path.join(out_dir, name + ".wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
        key["clips"][name + ".wav"] = {"label": label, "source": path, "text": text, **info}
        rows.append((name, info["sec"], text))
    with open(os.path.join(out_dir, "ANSWER_KEY.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=1)
    lines = [
        f"# 음성 듣기 채점표 — {rnd} (약 {max(5, round(sum(r[1] for r in rows) / 60 * 4))}분)", "",
        f"- 듣는 파일: 이 폴더의 `{rnd}-01.wav` ~ `{rnd}-{len(rows):02d}.wav`({len(rows)}개, 순서 무작위). 음량은 모두 같게 맞췄습니다.",
        "- 헤드폰이나 이어폰으로, 조용한 곳에서 들어 주세요.",
        "- 어떤 엔진인지는 숨겼습니다. 사람이 직접 읽은 녹음도 섞여 있습니다. `ANSWER_KEY.json`은 채점이 끝난 뒤에만 열어 주세요.",
        "",
        "## 질문 (파일마다 ①~④)",
        "- ① 얼마나 자연스럽게 들리나요? — 5 사람 같다 · 4 조금 어색한 곳이 있다 · 3 기계 느낌이 있지만 괜찮다 · 2 자주 거슬린다 · 1 듣기 힘들다",
        "- ② 잘못 읽은 단어나 숫자가 있나요? — 없음 / 있음(어느 단어)",
        "- ③ 이 음성을 영상이나 보고서에 넣어 **외부에 그대로 내보낼 수 있나요?** — 예 / 아니오",
        "- ④ (선택) 한 줄 메모",
        "",
        "## 답안",
        "| 파일 | 원문 | ① 1~5 | ② 없음 / 있음(단어) | ③ 예 / 아니오 | ④ 메모 |",
        "|---|---|---|---|---|---|",
    ]
    lines += [f"| {n}{' (약 %d초)' % round(s) if s >= 20 else ''} | {t} | | | | |" for n, s, t in rows]
    with open(os.path.join(out_dir, "SCORECARD.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({k: (v["label"], v["gain_db"], v["peak_limited"], v["sec"]) for k, v in key["clips"].items()},
                     ensure_ascii=False))


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    sr = 16000

    def tone(path, amp, lead, body, tail):
        x = [0] * int(lead * sr) + [int(amp * math.sin(2 * math.pi * 200 * t / sr)) for t in range(int(body * sr))] \
            + [0] * int(tail * sr)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(array.array("h", x).tobytes())

    quiet, loud = os.path.join(d, "q.wav"), os.path.join(d, "l.wav")
    tone(quiet, 100, 2.0, 1.0, 2.0)     # ~ -53 dBFS speech with long silences (like the quiet FLEURS file)
    tone(loud, 20000, 0.1, 1.0, 0.1)
    man = os.path.join(d, "m.csv")
    with open(man, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["path", "label", "text"])
        w.writerow([quiet, "human-a", "조용한 녹음"]); w.writerow([loud, "tts-b", "큰 녹음"])
    out = os.path.join(d, "out")
    build(man, out, "T", 1)
    key = json.load(open(os.path.join(out, "ANSWER_KEY.json"), encoding="utf-8"))["clips"]
    for k, v in key.items():
        assert abs(v["voiced_rms_after"] - TARGET_DBFS) < 0.2, v       # both matched on voiced part
        assert 1.15 <= v["sec"] <= 1.45, v                              # 1.0 s body + <= 0.2 s of edge silence each side
        sr2, ch, a = read_audio(os.path.join(out, k))
        assert _db(max(abs(s) for s in a)) <= PEAK_LIMIT_DBFS + 0.1
    card = open(os.path.join(out, "SCORECARD.md"), encoding="utf-8").read()
    assert "조용한 녹음" in card and "human-a" not in card                # text shown, label hidden
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["selftest"]:
        selftest()
    elif a[:1] == ["build"] and len(a) >= 4:
        build(a[1], a[2], a[3], int(a[a.index("--seed") + 1]) if "--seed" in a else 20261122)
    else:
        print(__doc__)

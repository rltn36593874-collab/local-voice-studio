"""Build a 'meeting-like' Korean STT test set from single-speaker read utterances (stdlib only).

Spec: C:\\Users\\user\\agent-company\\05-qa\\work\\meeting-set-spec.md

Usage:
  python -I make_meeting_set.py build <manifest.csv> <out_dir> [--minutes 5 5 30] [--seed 20261121]
  python -I make_meeting_set.py selftest

manifest.csv columns (UTF-8, header required): path,speaker,text
  path    = 16 kHz mono WAV, 16-bit PCM or 32-bit float (convert FLAC first, e.g. ffmpeg -i x.flac -ar 16000 -ac 1 x.wav)
  speaker = speaker id
  text    = reference transcript
"""
import array
import csv
import json
import math
import os
import random
import sys
import wave

SR = 16000
GAP_RANGE = (0.3, 1.5)          # seconds of silence between utterances
TURN_UTTS = (1, 3)              # consecutive utterances per speaker turn
MAIN_SPEAKERS = 4               # speakers talking in each meeting
BABBLE_SPEAKERS = 4             # other speakers summed into babble noise (never transcribed)
NOISE_ONLY_SEC = 20.0           # one noise-only stretch per file, for hallucination checks
CONDITIONS = [("clean", None, None), ("pink15", "pink", 15.0), ("pink10", "pink", 10.0),
              ("babble15", "babble", 15.0), ("babble10", "babble", 10.0)]


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir; we need our own audio_check
from audio_check import read_audio  # noqa: E402


def read_wav(path):
    sr, ch, a = read_audio(path)  # 16-bit PCM or 32-bit float WAV -> array('d') on int16 scale
    if (sr, ch) != (SR, 1):
        raise ValueError(f"{path}: need 16 kHz mono WAV (got {sr} Hz, {ch} ch)")
    return a


def write_wav(path, samples):
    peak = max(1.0, max(abs(s) for s in samples))
    scale = min(1.0, 32000.0 / peak)            # avoid clipping after noise is added
    a = array.array("h", (int(round(s * scale)) for s in samples))
    if sys.byteorder == "big":
        a.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())


def rms(x):
    return math.sqrt(sum(s * s for s in x) / len(x)) if x else 0.0


def pink(n, rng):
    # Paul Kellet's economy pink-noise filter on white noise.
    b0 = b1 = b2 = 0.0
    out = array.array("d")
    for _ in range(n):
        w = rng.uniform(-1, 1)
        b0 = 0.99765 * b0 + w * 0.0990460
        b1 = 0.96300 * b1 + w * 0.2965164
        b2 = 0.57000 * b2 + w * 1.0526913
        out.append(b0 + b1 + b2 + w * 0.1848)
    return out


def babble(n, pool, rng):
    out = array.array("d", [0.0]) * n
    for _ in range(BABBLE_SPEAKERS):
        pos = 0
        while pos < n:
            u = rng.choice(pool)
            for i, s in enumerate(u):
                if pos + i >= n:
                    break
                out[pos + i] += s
            pos += len(u)
    return out


def mix(speech, speech_mask, kind, snr_db, babble_pool, rng):
    n = len(speech)
    noise = pink(n, rng) if kind == "pink" else babble(n, babble_pool, rng)
    active = [s for s, m in zip(speech, speech_mask) if m]
    gain = rms(active) / (rms(noise) * 10 ** (snr_db / 20)) if rms(noise) > 0 else 0.0
    return array.array("d", (s + gain * v for s, v in zip(speech, noise)))


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_one(target_sec, by_spk, main, rng):
    speech, mask, segs = array.array("d"), bytearray(), []
    noise_at = rng.uniform(0.3, 0.7) * target_sec     # where the noise-only stretch goes
    noise_done, prev = False, None
    queues = {s: list(by_spk[s]) for s in main}
    for q in queues.values():
        rng.shuffle(q)
    while len(speech) < target_sec * SR:
        if not noise_done and len(speech) >= noise_at * SR:
            k = int(NOISE_ONLY_SEC * SR)
            speech.extend(array.array("d", [0.0]) * k); mask += bytes(k)
            segs.append({"start": round((len(speech) - k) / SR, 3), "end": round(len(speech) / SR, 3),
                         "speaker": None, "text": "", "noise_only": True})
            noise_done = True
        spk = rng.choice([s for s in main if s != prev and queues[s]] or [s for s in main if queues[s]] or [None])
        if spk is None:
            break  # ran out of utterances; file ends shorter than target
        for _ in range(rng.randint(*TURN_UTTS)):
            if not queues[spk]:
                break
            path, text = queues[spk].pop()
            x = read_wav(path)
            start = len(speech) / SR
            speech.extend(x); mask += bytes([1]) * len(x)
            segs.append({"start": round(start, 3), "end": round(len(speech) / SR, 3), "speaker": spk, "text": text})
            k = int(rng.uniform(*GAP_RANGE) * SR)
            speech.extend(array.array("d", [0.0]) * k); mask += bytes(k)
        prev = spk
    return speech, mask, segs


def build(manifest, out_dir, minutes, seed):
    rng = random.Random(seed)
    by_spk = {}
    with open(manifest, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            by_spk.setdefault(r["speaker"], []).append((r["path"], r["text"]))
    spks = sorted(by_spk)
    if len(spks) < MAIN_SPEAKERS + BABBLE_SPEAKERS:
        raise SystemExit(f"need >= {MAIN_SPEAKERS + BABBLE_SPEAKERS} speakers, got {len(spks)}")
    rng.shuffle(spks)
    babble_spk = spks[:BABBLE_SPEAKERS]
    main_pool = spks[BABBLE_SPEAKERS:]
    babble_pool = [read_wav(p) for s in babble_spk for p, _ in by_spk[s]]
    os.makedirs(out_dir, exist_ok=True)
    summary = {"seed": seed, "babble_speakers": babble_spk, "files": []}
    for i, mins in enumerate(minutes, 1):
        main = rng.sample(main_pool, min(MAIN_SPEAKERS, len(main_pool)))
        speech, mask, segs = build_one(mins * 60, by_spk, main, rng)
        name = f"meeting_{i:02d}_{mins}min"
        for cond, kind, snr in CONDITIONS:
            audio = speech if kind is None else mix(speech, mask, kind, snr, babble_pool, rng)
            write_wav(os.path.join(out_dir, f"{name}_{cond}.wav"), audio)
        with open(os.path.join(out_dir, f"{name}.segments.json"), "w", encoding="utf-8") as f:
            json.dump(segs, f, ensure_ascii=False, indent=1)
        spoken = [s for s in segs if not s.get("noise_only")]
        with open(os.path.join(out_dir, f"{name}.ref.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(s["text"] for s in spoken) + "\n")
        with open(os.path.join(out_dir, f"{name}.ref.srt"), "w", encoding="utf-8") as f:
            for k, s in enumerate(spoken, 1):
                f.write(f"{k}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n\n")
        summary["files"].append({"name": name, "speakers": main, "sec": round(len(speech) / SR, 1),
                                 "utterances": len(spoken)})
    with open(os.path.join(out_dir, "SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    rows = []
    for s in range(MAIN_SPEAKERS + BABBLE_SPEAKERS):
        for u in range(3):
            p = os.path.join(d, f"s{s}_{u}.wav")
            f0 = 120 + 30 * s
            write_wav(p, [8000 * math.sin(2 * math.pi * f0 * t / SR) for t in range(SR)])  # 1 s tone
            rows.append((p, f"spk{s}", f"문장 {s}-{u}"))
    man = os.path.join(d, "m.csv")
    with open(man, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["path", "speaker", "text"]); w.writerows(rows)
    global NOISE_ONLY_SEC
    NOISE_ONLY_SEC = 2.0
    out = os.path.join(d, "out")
    build(man, out, [0.5], 1)
    segs = json.load(open(os.path.join(out, "meeting_01_0.5min.segments.json"), encoding="utf-8"))
    spoken = [s for s in segs if not s.get("noise_only")]
    assert any(s.get("noise_only") for s in segs), "noise-only stretch missing"
    assert all(b["start"] >= a["end"] for a, b in zip(segs, segs[1:])), "segments overlap"
    gaps = [b["start"] - a["end"] for a, b in zip(spoken, spoken[1:]) if b["start"] - a["end"] < 1.6]
    assert gaps and all(0.29 <= g <= 1.51 for g in gaps), gaps
    assert {s["speaker"] for s in spoken} <= set(json.load(open(os.path.join(out, "SUMMARY.json"), encoding="utf-8"))["files"][0]["speakers"])
    for cond, _, _ in CONDITIONS:
        assert os.path.getsize(os.path.join(out, f"meeting_01_0.5min_{cond}.wav")) > 44
    # mask must mark exactly the speech samples (SNR is computed on them)
    by = {f"spk{i}": [(r[0], r[2]) for r in rows if r[1] == f"spk{i}"] for i in range(MAIN_SPEAKERS)}
    sp_, mk, sg = build_one(10, by, list(by), random.Random(2))
    spoken_samples = sum(round((s["end"] - s["start"]) * SR) for s in sg if not s.get("noise_only"))
    assert abs(sum(mk) - spoken_samples) <= len(sg), (sum(mk), spoken_samples)
    assert len(mk) == len(sp_)
    # SNR check on a pink mix
    rng = random.Random(0)
    sp = [8000 * math.sin(t / 5) for t in range(SR)]
    mixed = mix(sp, [True] * SR, "pink", 10.0, [], rng)
    nz = [m - s for m, s in zip(mixed, sp)]
    snr = 20 * math.log10(rms(sp) / rms(nz))
    assert abs(snr - 10.0) < 0.01, snr
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["selftest"]:
        selftest()
    elif a[:1] == ["build"] and len(a) >= 3:
        mins = [5, 5, 30]
        seed = 20261121
        if "--minutes" in a:
            i = a.index("--minutes"); j = i + 1
            mins = []
            while j < len(a) and not a[j].startswith("--"):
                mins.append(float(a[j]) if "." in a[j] else int(a[j])); j += 1
        if "--seed" in a:
            seed = int(a[a.index("--seed") + 1])
        build(a[1], a[2], mins, seed)
    else:
        print(__doc__)

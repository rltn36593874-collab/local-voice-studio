"""QA objective checks for voice samples (stdlib only).

Usage:
  python -I audio_check.py wav <file.wav> [...]   # level / clipping / silence per file
  python -I audio_check.py cer "<reference>" "<hypothesis>"
  python -I audio_check.py selftest
"""
import array
import math
import re
import sys
import unicodedata
import wave

SILENCE_DBFS = -45.0   # 20ms frame below this counts as silence
FRAME_MS = 20


def read_audio(path):
    """Return (sample_rate, channels, first channel as array('d') on the int16 scale).

    Reads 16-bit PCM (format 1) and 32-bit float (format 3, used by FLEURS) WAV.
    shortcut: no FLAC/MP3/24-bit; convert those to WAV first when needed.
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    pos, fmt, pcm = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, sr = (int.from_bytes(body[0:2], "little"), int.from_bytes(body[2:4], "little"),
                           int.from_bytes(body[4:8], "little"))
            bits = int.from_bytes(body[14:16], "little")
            if tag == 0xFFFE and len(body) >= 26:          # WAVE_FORMAT_EXTENSIBLE: real tag is in the subformat GUID
                tag = int.from_bytes(body[24:26], "little")
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            pcm = body
        pos += 8 + size + (size & 1)
    if fmt is None or pcm is None:
        raise ValueError(f"{path}: missing fmt or data chunk")
    tag, ch, sr, bits = fmt
    if (tag, bits) == (1, 16):
        a, scale = array.array("h"), 1.0
    elif (tag, bits) == (3, 32):
        a, scale = array.array("f"), 32768.0
    else:
        raise ValueError(f"{path}: unsupported WAV format tag={tag} bits={bits}")
    a.frombytes(pcm[:len(pcm) - len(pcm) % a.itemsize])
    if sys.byteorder == "big":
        a.byteswap()
    first = a[::ch] if ch > 1 else a  # first channel is enough for level checks
    return sr, ch, array.array("d", (s * scale for s in first))


def wav_stats(path):
    sr, ch, mono = read_audio(path)
    if not mono:
        raise ValueError(f"{path}: empty audio")
    full = 32768.0
    peak = max(abs(s) for s in mono)
    rms = math.sqrt(sum(s * s for s in mono) / len(mono))
    clipped = sum(1 for s in mono if abs(s) >= 32767)  # float input: |x| >= ~1.0 counts as clipped
    flen = max(1, sr * FRAME_MS // 1000)
    frames = range(0, len(mono), flen)
    quiet = []
    for i in frames:
        f = mono[i:i + flen]
        frms = math.sqrt(sum(s * s for s in f) / len(f))
        quiet.append(frms == 0 or 20 * math.log10(frms / full) < SILENCE_DBFS)
    silent, run, longest, inner = sum(quiet), 0, 0, 0
    voiced = [i for i, q in enumerate(quiet) if not q]
    lo, hi = (voiced[0], voiced[-1]) if voiced else (0, -1)
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        longest = max(longest, run)
        if q and lo < i < hi:            # pause between first and last voiced frame
            inner = max(inner, run)
    db = lambda v: 20 * math.log10(v / full) if v > 0 else float("-inf")
    return {
        "file": path, "sr": sr, "ch": ch, "sec": round(len(mono) / sr, 2),
        "rms_dbfs": round(db(rms), 1), "peak_dbfs": round(db(peak), 1),
        "clip_pct": round(100 * clipped / len(mono), 3),
        "silence_pct": round(100 * silent / len(frames), 1),
        "longest_silence_sec": round(longest * FRAME_MS / 1000, 2),
        "inner_pause_sec": round(inner * FRAME_MS / 1000, 2),  # excludes leading/trailing silence
    }


def _norm(text):
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"[^\w\s]", "", text)  # drop punctuation, keep Hangul/latin/digits


def _edit(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


_DIG = "영일이삼사오육칠팔구"


def sino(n):
    """Sino-Korean reading of a non-negative integer (1284 -> 천이백팔십사, 10000 -> 만)."""
    if n == 0:
        return "영"
    out = ""
    for big, unit in ((10 ** 12, "조"), (10 ** 8, "억"), (10 ** 4, "만"), (1, "")):
        q, n = divmod(n, big)
        if q:
            part = ""
            for v, u in ((1000, "천"), (100, "백"), (10, "십"), (1, "")):
                d, q = divmod(q, v)
                if d:
                    part += ("" if d == 1 and u else _DIG[d]) + u
            out += ("" if part == "일" and unit == "만" else part) + unit
    return out


def numbers_to_hangul(text):
    # shortcut: Sino-Korean only; native counters ("두 명" vs "2명") still differ -> report digit-free CER too.
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)                       # 1,284 -> 1284
    text = text.replace("%", "퍼센트")
    text = re.sub(r"(\d+)\.(\d+)", lambda m: sino(int(m.group(1))) + "점" + "".join(_DIG[int(c)] for c in m.group(2)), text)
    return re.sub(r"\d+", lambda m: sino(int(m.group(0))), text)


def cer(ref, hyp, numbers=False):
    if numbers:
        ref, hyp = numbers_to_hangul(ref), numbers_to_hangul(hyp)
    r, h = _norm(ref).replace(" ", ""), _norm(hyp).replace(" ", "")
    return _edit(r, h) / max(1, len(r))


def cer_counts(ref, hyp, numbers=False):
    """(edits, reference length) for corpus-level CER = sum(edits) / sum(lengths)."""
    if numbers:
        ref, hyp = numbers_to_hangul(ref), numbers_to_hangul(hyp)
    r, h = _norm(ref).replace(" ", ""), _norm(hyp).replace(" ", "")
    return _edit(r, h), len(r)


def wer(ref, hyp):
    r, h = _norm(ref).split(), _norm(hyp).split()
    return _edit(r, h) / max(1, len(r))


def selftest():
    import os
    import tempfile
    assert cer("안녕하세요.", "안녕하세요") == 0.0
    assert abs(cer("가나다라", "가나라") - 0.25) < 1e-9
    assert cer("띄어 쓰기", "띄어쓰기") == 0.0          # CER ignores spacing
    assert sino(1284) == "천이백팔십사" and sino(10000) == "만" and sino(20) == "이십" and sino(100) == "백"
    assert sino(1940) == "천구백사십" and sino(110000) == "십일만" and sino(0) == "영"
    assert numbers_to_hangul("12% 늘어난 1,284명") == "십이퍼센트 늘어난 천이백팔십사명"
    assert numbers_to_hangul("3.5배") == "삼점오배"
    assert cer("오후 3시", "오후 삼 시", numbers=True) == 0.0
    assert cer("지난주보다 12% 늘어난", "지난주보다 십이 퍼센트 늘어난", numbers=True) == 0.0
    assert abs(wer("the cat sat", "the cat sit") - 1 / 3) < 1e-9
    sr = 16000
    tone = [int(16384 * math.sin(2 * math.pi * 440 * t / sr)) for t in range(sr)]  # 1s at -6 dBFS peak
    data = array.array("h", tone + [0] * sr)                                       # + 1s silence
    path = os.path.join(tempfile.mkdtemp(), "t.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(data.tobytes())
    s = wav_stats(path)
    assert s["sec"] == 2.0 and s["clip_pct"] == 0.0
    assert -6.1 < s["peak_dbfs"] < -5.9
    assert 49 <= s["silence_pct"] <= 51 and s["longest_silence_sec"] == 1.0
    assert s["inner_pause_sec"] == 0.0, s          # trailing silence is not an inner pause
    gap = array.array("h", tone + [0] * (sr // 2) + tone)
    gpath = os.path.join(os.path.dirname(path), "g.wav")
    with wave.open(gpath, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(gap.tobytes())
    assert wav_stats(gpath)["inner_pause_sec"] == 0.5, wav_stats(gpath)
    # 32-bit float WAV (format 3), written by hand since the wave module cannot
    fl = array.array("f", (s / 32768.0 for s in data))
    if sys.byteorder == "big":
        fl.byteswap()
    pcm = fl.tobytes()
    fmt = (3).to_bytes(2, "little") + (1).to_bytes(2, "little") + sr.to_bytes(4, "little") + \
        (sr * 4).to_bytes(4, "little") + (4).to_bytes(2, "little") + (32).to_bytes(2, "little")
    riff = b"WAVE" + b"fmt " + len(fmt).to_bytes(4, "little") + fmt + b"data" + len(pcm).to_bytes(4, "little") + pcm
    fpath = os.path.join(os.path.dirname(path), "f.wav")
    with open(fpath, "wb") as f:
        f.write(b"RIFF" + len(riff).to_bytes(4, "little") + riff)
    sf = wav_stats(fpath)
    assert sf["sec"] == 2.0 and abs(sf["peak_dbfs"] - s["peak_dbfs"]) < 0.01, sf
    print("selftest ok")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "wav":
        keys = ["file", "sr", "ch", "sec", "rms_dbfs", "peak_dbfs", "clip_pct", "silence_pct", "longest_silence_sec", "inner_pause_sec"]
        print("\t".join(keys))
        for p in sys.argv[2:]:
            try:
                s = wav_stats(p)
                print("\t".join(str(s[k]) for k in keys))
            except Exception as e:  # report and continue with other files
                print(f"{p}\tERROR\t{e}")
    elif cmd == "cer" and len(sys.argv) == 4:
        print(f"CER={cer(sys.argv[2], sys.argv[3]):.4f}  WER={wer(sys.argv[2], sys.argv[3]):.4f}")
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__)

"""WAV 이어 붙이기, AI 표시 메타데이터(설계 §5), 선택적 MP3 변환(ffmpeg가 있을 때만)."""
import json
import re
import struct
import subprocess
import wave
from datetime import datetime

from . import config


def concat_wavs(parts, out):
    params, frames = None, []
    for p in parts:
        with wave.open(str(p)) as f:
            if params is None:
                params = f.getparams()
            elif (f.getnchannels(), f.getsampwidth(), f.getframerate()) != (params.nchannels, params.sampwidth, params.framerate):
                raise ValueError("엔진 출력 형식이 덩어리마다 달라요")
            frames.append(f.readframes(f.getnframes()))
    with wave.open(str(out), "wb") as f:
        f.setparams(params)
        for fr in frames:
            f.writeframes(fr)
    return sum(len(fr) for fr in frames) / (params.nchannels * params.sampwidth * params.framerate)


def normalize_loudness(path, target_dbfs=-20.0, peak_dbfs=-1.0, frame_sec=0.02, rel_silence_db=35.0):
    """말소리 구간 RMS를 목표값으로 맞춘다(QA 05-qa/work/make_listening_set.py prepare()와 같은 기준:
    20ms 프레임, 가장 큰 프레임보다 35dB 낮으면 무음). 봉우리는 peak_dbfs를 넘지 않게 이득을 줄인다. 반환: 적용 이득(dB)."""
    import array
    import math
    with wave.open(str(path)) as f:
        params = f.getparams()
        raw = f.readframes(f.getnframes())
    if params.sampwidth != 2 or not raw:
        return 0.0  # shortcut: 16bit만 처리. 다른 형식은 그대로 둔다
    a = array.array("h", raw)
    n = max(1, int(params.framerate * params.nchannels * frame_sec))
    frames = [a[i:i + n] for i in range(0, len(a), n)]
    frms = [math.sqrt(sum(x * x for x in fr) / len(fr)) for fr in frames]
    thr = max(frms) * 10 ** (-rel_silence_db / 20)
    voiced = [fr for fr, r in zip(frames, frms) if r >= thr and r > 0]
    if not voiced:
        return 0.0
    rms = math.sqrt(sum(x * x for fr in voiced for x in fr) / sum(len(fr) for fr in voiced))
    peak = max(abs(min(a)), max(a)) or 1
    gain = min(10 ** (target_dbfs / 20) * 32768 / rms, 10 ** (peak_dbfs / 20) * 32767 / peak)
    if abs(20 * math.log10(gain)) < 0.5:
        return 0.0
    out = array.array("h", (max(-32768, min(32767, int(x * gain))) for x in a))
    with wave.open(str(path), "wb") as f:
        f.setparams(params)
        f.writeframes(out.tobytes())
    return round(20 * math.log10(gain), 1)


def add_wav_info(path, tags):
    """RIFF LIST/INFO 청크(INAM 제목, IART 작가, ICMT 설명, ICRD 날짜, ISFT 소프트웨어)를 덧붙인다."""
    ids = {"title": b"INAM", "artist": b"IART", "comment": b"ICMT", "date": b"ICRD", "software": b"ISFT"}
    body = b"INFO"
    for k, v in tags.items():
        data = str(v).encode("utf-8") + b"\0"
        if len(data) % 2:
            data += b"\0"
        body += ids[k] + struct.pack("<I", len(data)) + data
    chunk = b"LIST" + struct.pack("<I", len(body)) + body
    with open(path, "r+b") as f:
        f.seek(0, 2)
        f.write(chunk)
        size = f.tell() - 8
        f.seek(4)
        f.write(struct.pack("<I", size))


KIND_LABEL = {"tts": "내레이션", "briefing": "브리핑"}


def file_stem(title, is_clone, kind="tts", out_dir=None, when=None):
    """디자인 02 §2-1: YYYYMMDD-HHMM_종류_제목_AI. 같은 분·같은 제목이면 -2, -3을 붙여 덮어쓰지 않는다."""
    when = when or datetime.now()
    slug = re.sub(r"[^\w가-힣-]+", "-", title or "voice").strip("-")[:40] or "voice"
    base = f"{when:%Y%m%d-%H%M}_{KIND_LABEL.get(kind, kind)}_{slug}"
    tail = "AI-clone" if is_clone else "AI"
    stem, n = f"{base}_{tail}", 2
    while out_dir is not None and any((out_dir / f"{stem}{ext}").exists() for ext in (".wav", ".mp3", ".ai.json")):
        stem, n = f"{base}-{n}_{tail}", n + 1
    return stem


def disclosure(engine, is_clone, subject=None):
    """법무 09 §2-3: 외부 공개물은 사람이 알아볼 수 있는 AI 표시가 필요하다(메타데이터만으로는 부족).
    반환 {caption_text: 영상 화면 자막, disclosure_text: 설명란 문구, required}. 지금은 모든 결과물에 required=True."""
    if is_clone:
        cap = f"AI로 복제한 {subject or '실제 인물'}의 음성입니다"
    else:
        cap = "이 영상의 음성은 AI로 생성했습니다"
    return {"caption_text": cap, "disclosure_text": f"※ {cap}.", "required": True}


def notice_text(is_clone, subject=None):
    """음성 단독 결과물 앞/뒤에 1회 넣는 음성 안내(시행령 제23조 ②제2호, 법무 09 §2-3 2번)."""
    if is_clone:
        return f"이 음성은 AI로 복제한 {subject or '실제 인물'}의 목소리입니다."
    return "이 음성은 AI로 생성했습니다."


def silence_like(ref, out, seconds):
    with wave.open(str(ref)) as f:
        params = f.getparams()
    with wave.open(str(out), "wb") as f:
        f.setparams(params)
        f.writeframes(b"\0" * int(params.framerate * seconds) * params.nchannels * params.sampwidth)


def finalize(wav_path, stem, out_dir, meta, want_mp3):
    """wav_path(임시)를 최종 이름으로 옮기고 메타데이터·옆 JSON을 쓴다. 반환 files dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    comment = f"AI 생성 음성 (사내 도구, 모델: {meta['engine']}, 음성: {meta['voice_name']}{', 복제' if meta['is_clone'] else ''})"
    tags = {"title": meta["title"], "artist": "AI voice", "comment": comment,
            "date": meta["created_at"][:10], "software": "사내 음성 도구"}
    final_wav = out_dir / f"{stem}.wav"
    wav_path.replace(final_wav)
    add_wav_info(final_wav, tags)
    files = {"wav": final_wav.name}
    ff = config.ffmpeg()
    if want_mp3 and ff:
        mp3 = out_dir / f"{stem}.mp3"
        args = [ff, "-y", "-loglevel", "error", "-i", str(final_wav), "-codec:a", "libmp3lame", "-b:a", "192k"]
        for k in ("title", "artist", "comment", "date"):
            args += ["-metadata", f"{k}={tags[k]}"]
        r = subprocess.run(args + [str(mp3)], capture_output=True, timeout=300)
        if r.returncode == 0:
            files["mp3"] = mp3.name
    side = {"ai_generated": True, "generator": "사내 음성 도구",
            **disclosure(meta["engine"], meta["is_clone"], meta.get("subject")), "ai_notice": meta.get("ai_notice"),
            **{k: meta[k] for k in (
        "engine", "engine_version", "voice_id", "voice_name", "is_clone", "consent_id", "created_at", "job_id", "text_sha256")}}
    (out_dir / f"{stem}.ai.json").write_text(json.dumps(side, ensure_ascii=False, indent=1), encoding="utf-8")
    files["sidecar"] = f"{stem}.ai.json"
    return files


def split_sentences(text, limit=200):
    """문장 단위로 나눈 뒤 limit자 안에서 묶는다(진행률·취소 지점)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if s.strip()]
    chunks, cur = [], ""
    for s in sents:
        while len(s) > limit:  # 마침표 없는 긴 문장은 쉼표·공백에서 자른다
            cut = max(s.rfind(",", 0, limit), s.rfind(" ", 0, limit))
            cut = cut if cut > 0 else limit
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:cut + 1].strip())
            s = s[cut + 1:].strip()
        if cur and len(cur) + 1 + len(s) > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks

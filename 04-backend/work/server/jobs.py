"""작업 대기열(설계 §2). 줄 두 개: cpu(tts·transcribe), llm(translate). 줄마다 스레드 하나 = 한 번에 하나."""
import hashlib
import json
import tempfile
import threading
import time
import traceback
from pathlib import Path

from . import audio, claude, config, db, engines, ledger, normalize, pseudonym

LANE = {"tts": "cpu", "transcribe": "cpu", "clone": "cpu", "translate": "llm"}
_wake = {"cpu": threading.Event(), "llm": threading.Event()}
_stop = threading.Event()


class JobFailed(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def enqueue(type_, payload):
    jid = db.new_id("job")
    db.run("INSERT INTO jobs(id,type,lane,status,progress,payload,created_at) VALUES(?,?,?,?,?,?,?)",
           jid, type_, LANE[type_], "queued", 0, json.dumps(payload, ensure_ascii=False), db.now())
    _wake[LANE[type_]].set()
    return jid


def view(j):
    if not j:
        return None
    pos = None
    if j["status"] == "queued":
        pos = db.one("SELECT COUNT(*) n FROM jobs WHERE lane=? AND status IN ('queued','preparing','running') AND created_at<=? AND id<>?",
                     j["lane"], j["created_at"], j["id"])["n"]
    return {"id": j["id"], "type": j["type"], "title": _title(j), "lane": j["lane"], "status": j["status"], "progress": j["progress"],
            "queue_position": pos, "eta_sec": j["eta_sec"], "cancel_requested": bool(j["cancel_requested"]),
            "created_at": j["created_at"], "started_at": j["started_at"], "finished_at": j["finished_at"],
            "result": json.loads(j["result"]) if j["result"] else None,
            "error": json.loads(j["error"]) if j["error"] else None}


def _title(j):
    """작업 서랍·완료 알림용(프론트 요청): TTS=제목 또는 앞 20자, 전사=파일명, 번역=언어."""
    try:
        p = json.loads(j["payload"] or "{}")
    except json.JSONDecodeError:
        return ""
    if j["type"] == "tts":
        return p.get("title") or (p.get("text") or "")[:20]
    if j["type"] == "transcribe":
        return p.get("source_name") or ""
    if j["type"] == "translate":
        return f"{LANG_KO.get(p.get('lang'), p.get('lang', ''))} 번역"
    return ""


def get(jid):
    return view(db.one("SELECT * FROM jobs WHERE id=?", jid))


def listing(recent=0):
    active = [view(j) for j in db.q("SELECT * FROM jobs WHERE status IN ('queued','preparing','running') ORDER BY created_at")]
    if not recent:
        return {"active": active}
    done = db.q("SELECT * FROM jobs WHERE status IN ('done','failed','canceled') ORDER BY finished_at DESC LIMIT ?", min(int(recent), 20))
    return {"active": active, "recent": [view(j) for j in done]}


def cancel(jid):
    j = db.one("SELECT status FROM jobs WHERE id=?", jid)
    if not j:
        return False
    if j["status"] == "queued":
        db.run("UPDATE jobs SET status='canceled', finished_at=? WHERE id=? AND status='queued'", db.now(), jid)
    elif j["status"] in ("preparing", "running"):
        db.run("UPDATE jobs SET cancel_requested=1 WHERE id=?", jid)
    return True


def _set(jid, **kw):
    cols = ", ".join(f"{k}=?" for k in kw)
    db.run(f"UPDATE jobs SET {cols} WHERE id=?", *kw.values(), jid)


def _canceled(jid):
    return bool(db.one("SELECT cancel_requested FROM jobs WHERE id=?", jid)["cancel_requested"])


# ---------- 작업 종류별 처리 ----------

def normalize_for_tts(raw, jid):
    """QA 필수 정규화(대표 지시 2026-11-22): Claude로 읽기 형태를 바꾸고, 남은 숫자·%·대문자는 로컬 규칙으로 마저 바꾼다.
    Claude를 못 쓰면(키 없음·한도·오류·거절) 로컬 규칙만 쓴다. 반환 (정규화 문장, 사용한 방식)."""
    try:
        text, _ = claude.call("tts_normalize", raw, job_id=jid, max_tokens=min(16000, len(raw) * 3 + 500))
        text, how = text.strip() or raw, f"claude:{claude.load_prompt('tts_normalize')[1]}"
        bad = normalize.suspicious(raw, text)
        if bad:  # 어순·분량이 바뀌면 Claude 결과를 버리고 로컬 규칙으로(내용 보존이 우선)
            db.log("normalize_rejected", job_id=jid, detail={"reason": bad, "claude_preview": text[:80]})
            text, how = raw, f"local(claude rejected: {bad})"
    except claude.ClaudeError as e:
        text, how = raw, f"local(claude {e.code})"
    if normalize.needs_fix(text):
        text = normalize.normalize(text)
        how += "+local" if how.startswith("claude") else ""
    return text, how


def do_tts(j, p):
    jid = j["id"]
    voice = BUILTIN_VOICES.get(p["voice_id"])
    if not voice:
        raise JobFailed("not_found", "음성을 찾을 수 없어요")
    _set(jid, status="running", progress=None)
    text, how = normalize_for_tts(p["text"], jid)
    chunks = audio.split_sentences(text)
    is_clone = voice.get("kind") == "clone"
    # 음성 안내 1회: 기본 켬. 복제 음성은 끌 수 없다(법무 09 §2-3 3번)
    notice_pos = p.get("ai_notice_position", "start") if (p.get("ai_notice", True) or is_clone) else None
    if notice_pos:
        nt = audio.notice_text(is_clone, voice.get("subject"))
        chunks = [nt] + chunks if notice_pos == "start" else chunks + [nt]
    t0 = time.process_time(), time.monotonic()
    tmp = Path(tempfile.mkdtemp(dir=config.DATA))
    parts = []
    try:
        for i, ch in enumerate(chunks):
            if _canceled(jid):
                raise engines.Canceled()
            part = tmp / f"{i:04d}.wav"
            engines.tts_chunk(ch, part, speed=p.get("speed", 1.0), voice=voice.get("engine_voice"),
                              on_preparing=lambda: _set(jid, status="preparing", progress=None))
            _set(jid, status="running", progress=round((i + 1) / len(chunks) * 0.95, 3))
            parts.append(part)
        if notice_pos:  # 안내와 본문 사이 0.5초 쉼
            gap = tmp / "gap.wav"
            audio.silence_like(parts[0], gap, 0.5)
            parts.insert(1 if notice_pos == "start" else len(parts) - 1, gap)
        merged = tmp / "merged.wav"
        dur = audio.concat_wavs(parts, merged)
        gain_db = audio.normalize_loudness(merged, config.TARGET_RMS_DBFS)
        created = db.now()
        oid = db.new_id("out")
        title = p.get("title") or p["text"][:20]
        ver = engines.tts_version()
        if voice.get("engine_voice"):  # 법무 §1-6: 모델 버전과 스타일·속도까지 기록
            ver = f"{ver} / style {voice['engine_voice']} / speed {p.get('speed', 1.0)}"
        meta = {"title": title, "engine": config.TTS_ENGINE, "engine_version": ver,
                "voice_id": p["voice_id"], "voice_name": voice["name"], "is_clone": is_clone, "consent_id": voice.get("consent_id"),
                "subject": voice.get("subject"), "ai_notice": notice_pos,
                "created_at": created, "job_id": jid, "text_sha256": hashlib.sha256(p["text"].encode()).hexdigest()}
        out_dir = config.OUTPUTS / created[:10]
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = audio.file_stem(title, is_clone, p.get("kind") or "tts", out_dir)
        files = audio.finalize(merged, stem, out_dir, meta, p.get("format") == "mp3")
        files = {k: f"{created[:10]}/{v}" for k, v in files.items()}
        db.run("""INSERT INTO outputs(id,kind,title,created_at,duration_sec,voice_id,voice_name,is_clone,consent_id,engine,
                  engine_version,files,text_sha256,job_id,text_original,text_normalized,normalizer,ai_notice)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", oid, p.get("kind") or "tts", title, created,
               round(dur, 2), p["voice_id"], voice["name"], int(is_clone), meta["consent_id"], meta["engine"],
               meta["engine_version"], json.dumps(files), meta["text_sha256"], jid, p["text"], text, how, notice_pos)
        db.log("job_done", job_id=jid, output_id=oid, voice_id=p["voice_id"],
               detail={"chars": len(p["text"]), "preview": p["text"][:50], "normalizer": how, "gain_db": gain_db,
                       "engine": meta["engine"], "engine_version": meta["engine_version"],  # 법무 §1-6: 로그에도 버전·리비전
                       "normalized_sha256": hashlib.sha256(text.encode()).hexdigest()})
        ledger.record_local("tts", jid, meta["engine"], "ok", round(time.process_time() - t0[0], 2),
                            audio_out_sec=round(dur, 2), chars_in=len(p["text"]))
        return {"output_id": oid}
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        tmp.rmdir()


def do_transcribe(j, p):
    jid = j["id"]
    segs = []

    def on_seg(e):
        segs.append({"start": e["start"], "end": e["end"], "text": e["text"]})
        _set(jid, status="running", progress=round(e["progress"], 3) if e.get("progress") is not None else None)

    _set(jid, status="running", progress=None)
    t0 = time.monotonic()
    dur, lang, ver = engines.transcribe(Path(p["upload_path"]), p.get("language") or "ko", on_seg,
                                        lambda: _canceled(jid),
                                        on_preparing=lambda: _set(jid, status="preparing", progress=None),
                                        model=p.get("model"))
    tid = db.new_id("tr")
    db.run("INSERT INTO transcripts VALUES(?,?,?,?,?,?,?,?,?)", tid, p["source_name"], dur, lang,
           json.dumps(segs, ensure_ascii=False), "{}", p["upload_path"], db.now(), jid)
    db.log("job_done", job_id=jid, detail={"transcript_id": tid, "engine": ver, "segments": len(segs)})
    # cpu_seconds 자리에 벽시계 시간(엔진은 별도 프로세스라 그 CPU 시간을 여기서 못 잰다)
    ledger.record_local("transcribe", jid, config.STT_ENGINE, "ok", round(time.monotonic() - t0, 2), audio_in_sec=dur)
    return {"transcript_id": tid}


TRANSLATE_SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"i": {"type": "integer"}, "text": {"type": "string"}},
    "required": ["i", "text"], "additionalProperties": False}}}, "required": ["items"], "additionalProperties": False}
LANG_NAMES = {"en": "English", "ja": "Japanese", "zh": "Simplified Chinese", "ko": "Korean", "vi": "Vietnamese",
              "es": "Spanish", "fr": "French", "de": "German"}
LANG_KO = {"en": "영어", "ja": "일본어", "zh": "중국어", "ko": "한국어", "vi": "베트남어", "es": "스페인어", "fr": "프랑스어", "de": "독일어"}


def do_translate(j, p):
    jid = j["id"]
    t = db.one("SELECT * FROM transcripts WHERE id=?", p["transcript_id"])
    segs = json.loads(t["segments"])
    # 해외 전송 전 가명처리(법무 09 L4). 대응표는 이 작업 메모리에만 있다
    ps = pseudonym.Pseudonymizer(db.get_setting("pseudonym_names", [])) if p.get("pseudonymize", True) else None
    out, batch = [], 150
    for start in range(0, len(segs), batch):
        if _canceled(jid):
            raise engines.Canceled()
        part = segs[start:start + batch]
        lines = "\n".join(json.dumps({"i": start + k, "text": ps.mask(s["text"]) if ps else s["text"]}, ensure_ascii=False)
                          for k, s in enumerate(part))
        msg = f"목표 언어: {LANG_NAMES.get(p['lang'], p['lang'])}\n구간 수: {len(part)}\n\n{lines}"
        for attempt in (1, 2):  # 구간 수가 안 맞으면 그 묶음만 1회 재시도
            data, _ = claude.call("srt_translate", msg, job_id=jid, max_tokens=16000, schema=TRANSLATE_SCHEMA)
            got = {x["i"]: x["text"] for x in data.get("items", [])}
            if all(start + k in got for k in range(len(part))):
                break
            if attempt == 2:
                raise JobFailed("claude_error", "번역 결과의 구간 수가 원본과 달라요")
        out += [{**s, "text": ps.unmask(got[start + k]) if ps else got[start + k]} for k, s in enumerate(part)]  # 타이밍은 원본 그대로
        _set(jid, status="running", progress=round(min(start + batch, len(segs)) / len(segs), 3))
    tr = json.loads(t["translations"] or "{}")
    tr[p["lang"]] = out
    db.run("UPDATE transcripts SET translations=? WHERE id=?", json.dumps(tr, ensure_ascii=False), t["id"])
    if ps:
        db.log("pseudonymized", job_id=jid, detail={"feature": "srt_translate", "counts": ps.stats()})
    return {"transcript_id": t["id"], "lang": p["lang"]}


HANDLERS = {"tts": do_tts, "transcribe": do_transcribe, "translate": do_translate}

# 기본 음성. 엔진이 바뀌면 여기만 고친다.
BUILTIN_VOICES = {
    "melo_kr": {"name": "기본 음성 (MeloTTS)", "engine": "melo", "engine_voice": None},
    # id는 고정, 실제 스타일은 설정값(QA R3 판정에 따라 바뀔 수 있음)
    "supertonic_female": {"name": f"기본 여성 (Supertonic {config.TTS_STYLE_FEMALE})", "engine": "supertonic",
                          "engine_voice": config.TTS_STYLE_FEMALE},
    "supertonic_male": {"name": f"기본 남성 (Supertonic {config.TTS_STYLE_MALE})", "engine": "supertonic",
                        "engine_voice": config.TTS_STYLE_MALE},
    "mock_tone": {"name": "시험용 신호음 (mock)", "engine": "mock", "engine_voice": None},
}


def voices():
    return [{"id": k, "name": v["name"], "kind": "builtin", "engine": v["engine"], "created_at": None}
            for k, v in BUILTIN_VOICES.items() if v["engine"] == config.TTS_ENGINE]


def _run_one(lane):
    j = db.one("SELECT * FROM jobs WHERE lane=? AND status='queued' ORDER BY created_at LIMIT 1", lane)
    if not j:
        return False
    _set(j["id"], status="running", started_at=db.now(), progress=None)
    try:
        res = HANDLERS[j["type"]](j, json.loads(j["payload"]))
        _set(j["id"], status="done", progress=1.0, result=json.dumps(res), finished_at=db.now())
    except engines.Canceled:
        _set(j["id"], status="canceled", finished_at=db.now())
        db.log("job_canceled", job_id=j["id"])
    except (JobFailed, engines.EngineError, claude.ClaudeError) as e:
        _fail(j, e.code, e.message)
    except ledger.UnknownModel as e:
        _fail(j, "config_error", f"단가표에 없는 모델: {e}")
    except Exception as e:
        traceback.print_exc()
        _fail(j, "engine_error", f"{type(e).__name__}: {e}"[:300])
    return True


def _fail(j, code, message):
    _set(j["id"], status="failed", finished_at=db.now(), error=json.dumps({"code": code, "message": message}, ensure_ascii=False))
    db.log("job_failed", job_id=j["id"], detail={"code": code, "message": message})


def _loop(lane):
    while not _stop.is_set():
        if not _run_one(lane):
            _wake[lane].wait(2)
            _wake[lane].clear()


def start():
    # 재시작: 실행 중이던 작업은 실패 처리, 대기 작업은 이어서(설계 §1)
    db.run("UPDATE jobs SET status='failed', finished_at=?, error=? WHERE status IN ('preparing','running')", db.now(),
           json.dumps({"code": "interrupted", "message": "서버가 다시 시작돼 작업이 중단됐어요"}, ensure_ascii=False))
    for lane in _wake:
        threading.Thread(target=_loop, args=(lane,), daemon=True, name=f"lane-{lane}").start()


def stop():
    _stop.set()
    for e in _wake.values():
        e.set()

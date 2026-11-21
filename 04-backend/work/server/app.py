"""로컬 API 서버(계약: shared/research/elevenlabs/04-backend-local-api.md §3, 프론트 합의 2026-11-22).
실행: run.ps1 (127.0.0.1:8000에만 바인딩)."""
import base64
import csv
import io
import json
import threading
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from . import audio, claude, config, db, engines, jobs, ledger, pseudonym, retention


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def cleanup_uploads():
    """업로드 원본 30일 보관(대표 승인). 동의 녹음·복제 샘플은 uploads에 두지 않는다."""
    cut = time.time() - config.UPLOAD_KEEP_DAYS * 86400
    for f in config.UPLOADS.glob("*"):
        if f.is_file() and f.stat().st_mtime < cut:
            f.unlink(missing_ok=True)


def _daily():
    while True:
        try:
            cleanup_uploads()
            retention.purge()
        except Exception:
            traceback.print_exc()
        time.sleep(86400)


@asynccontextmanager
async def lifespan(_app):
    db.init()
    retention.purge()
    jobs.start()
    threading.Thread(target=_daily, daemon=True).start()
    yield
    jobs.stop()
    engines.shutdown()  # 엔진 하위 프로세스도 함께 끈다


app = FastAPI(title="사내 음성 도구 로컬 API", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def guard(request: Request, call_next):
    # DNS 리바인딩·CSRF 방지(설계 §3.1). Origin은 있을 때만 검사(같은 출처 GET에는 안 붙음)
    if request.headers.get("host") not in config.ALLOWED_HOSTS:
        return _err(403, "forbidden_host", "허용되지 않은 Host")
    origin = request.headers.get("origin")
    if origin and origin not in config.ALLOWED_ORIGINS:
        return _err(403, "forbidden_origin", "허용되지 않은 Origin")
    return await call_next(request)


def _err(status, code, message):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(ApiError)
async def _api_err(_r, e: ApiError):
    return _err(e.status, e.code, e.message)


@app.exception_handler(claude.ClaudeError)
async def _claude_err(_r, e: claude.ClaudeError):
    return _err(e.status, e.code, e.message)


@app.exception_handler(ledger.UnknownModel)
async def _model_err(_r, e):
    return _err(500, "config_error", f"단가표에 없는 모델: {e}")


@app.exception_handler(404)
async def _nf(_r, _e):
    return _err(404, "not_found", "없는 주소예요")


@app.exception_handler(RequestValidationError)
async def _bad(_r, e):
    return _err(400, "bad_format", "요청 형식이 올바르지 않아요")


def must(row, what="항목"):
    if not row:
        raise ApiError(404, "not_found", f"{what}을(를) 찾을 수 없어요")
    return row


async def body_json(request):
    try:
        return await request.json()
    except Exception:
        raise ApiError(400, "bad_format", "JSON 본문이 필요해요")


# ---------- 상태 ----------
@app.get("/api/health")
def health():
    return {"ok": True, "engines": engines.status(), "claude_key_present": claude.key_present(),
            "ffmpeg": bool(config.ffmpeg())}


# ---------- 작업 ----------
@app.get("/api/jobs/{jid}")
def job(jid: str):
    return must(jobs.get(jid), "작업")


@app.get("/api/jobs")
def job_list(active: int = 1, recent: int = 0):
    return jobs.listing(recent)


@app.delete("/api/jobs/{jid}", status_code=202)
def job_cancel(jid: str):
    if not jobs.cancel(jid):
        raise ApiError(404, "not_found", "작업을 찾을 수 없어요")
    return jobs.get(jid)


# ---------- ① 음성 만들기 ----------
@app.get("/api/voices")
def voices():
    return jobs.voices()


@app.post("/api/script/refine")
async def refine(request: Request):
    b = await body_json(request)
    text = (b.get("text") or "").strip()
    if not text:
        raise ApiError(400, "too_short", "다듬을 원문을 입력해 주세요")
    if len(text) > 20000:
        raise ApiError(400, "too_long", "원문이 너무 길어요(2만 자 이하)")
    head = f"말투: {b.get('tone') or '기본'}\n목표 길이(초): {b.get('target_sec') or '지정 없음'}\n\n원문:\n{text}"
    out, usage = claude.call("script", head, max_tokens=4000)
    return {"text": out.strip(), "usage": usage}


@app.post("/api/tts", status_code=202)
async def tts(request: Request):
    b = await body_json(request)
    text = (b.get("text") or "").strip()
    if not text:
        raise ApiError(400, "too_short", "읽을 문장을 입력해 주세요")
    if len(text) > config.TTS_MAX_CHARS:
        raise ApiError(400, "too_long", f"한 번에 {config.TTS_MAX_CHARS:,}자까지 만들 수 있어요")
    if b.get("voice_id") not in {v["id"] for v in jobs.voices()}:
        raise ApiError(404, "not_found", "음성을 찾을 수 없어요")
    speed = float(b.get("speed") or config.TTS_DEFAULT_SPEED)  # 기본 0.95(QA A7-7)
    if not 0.7 <= speed <= 1.3:
        raise ApiError(400, "bad_format", "속도는 0.7~1.3 사이여야 해요")
    fmt = b.get("format") or "mp3"
    if fmt not in ("mp3", "wav"):
        raise ApiError(400, "bad_format", "형식은 mp3 또는 wav예요")
    pos = b.get("ai_notice_position") or "start"
    if pos not in ("start", "end"):
        raise ApiError(400, "bad_format", "ai_notice_position은 start 또는 end예요")
    kind = b.get("kind") or "tts"
    if kind not in ("tts", "briefing"):
        raise ApiError(400, "bad_format", "kind는 tts 또는 briefing이에요")
    return {"job_id": jobs.enqueue("tts", {"text": text, "voice_id": b["voice_id"], "speed": speed, "format": fmt,
                                             "title": (b.get("title") or "").strip()[:80], "kind": kind,
                                             "ai_notice": b.get("ai_notice", True) is not False, "ai_notice_position": pos})}


# ---------- ② 받아쓰기 ----------
async def save_upload(f: UploadFile, limit):
    config.UPLOADS.mkdir(parents=True, exist_ok=True)  # 폴더가 지워졌어도 다시 만든다
    suffix = Path(f.filename or "").suffix.lower()[:8]
    dest = config.UPLOADS / f"{db.new_id('up')}{suffix}"
    size = 0
    with open(dest, "wb") as out:
        while chunk := await f.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise ApiError(413, "file_too_large", f"파일이 너무 커요({limit // 1024**2:,}MB 이하)")
            out.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise ApiError(400, "too_short", "빈 파일이에요")
    return dest


@app.post("/api/transcribe", status_code=202)
async def transcribe(file: UploadFile = File(...), language: str = Form("ko"), quality: str = Form("accurate")):
    # quality: accurate(기본, medium) | draft(빠른 초안, small). QA A7-5
    if quality not in config.STT_MODELS:
        raise ApiError(400, "bad_format", "quality는 accurate 또는 draft예요")
    # shortcut: 형식 판별은 엔진(PyAV) 디코딩에 맡긴다. 디코딩 실패는 작업 실패로 돌아온다. ffprobe가 준비되면 업로드 단계에서 거른다.
    path = await save_upload(file, config.UPLOAD_MAX_BYTES)
    model = config.STT_MODELS[quality] if quality != "accurate" else config.STT_MODEL
    return {"job_id": jobs.enqueue("transcribe", {"upload_path": str(path), "source_name": file.filename,
                                                    "language": language or "ko", "quality": quality, "model": model})}


def transcript(tid):
    t = must(db.one("SELECT * FROM transcripts WHERE id=?", tid), "전사")
    t["segments"] = json.loads(t["segments"])
    t["translations"] = json.loads(t["translations"] or "{}")
    return t


@app.get("/api/transcripts/{tid}")
def get_transcript(tid: str):
    t = transcript(tid)
    return {"id": t["id"], "source_name": t["source_name"], "duration_sec": t["duration_sec"],
            "language": t["language"], "segments": t["segments"], "translations": sorted(t["translations"]),
            "source_expires_at": source_expiry(t)}


def source_expiry(t):
    """업로드 원본 삭제 예정 시각(30일 보관). 이미 지워졌으면 None."""
    p = Path(t["upload_path"] or "")
    if not p.is_file():
        return None
    return datetime.fromtimestamp(p.stat().st_mtime + config.UPLOAD_KEEP_DAYS * 86400).astimezone().isoformat(timespec="seconds")


def segs_for(t, lang):
    if not lang or lang == t["language"]:
        return t["segments"]
    if lang in t["translations"]:
        return t["translations"][lang]
    if lang == "ko":  # 언어 감지가 ko가 아니어도 원문을 준다
        return t["segments"]
    raise ApiError(404, "not_found", f"{lang} 번역이 아직 없어요")


def _ts(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


@app.get("/api/transcripts/{tid}/srt")
def srt(tid: str, lang: str = "ko"):
    segs = segs_for(transcript(tid), lang)
    body = "\n".join(f"{i}\n{_ts(s['start'])} --> {_ts(s['end'])}\n{s['text']}\n" for i, s in enumerate(segs, 1))
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


@app.get("/api/transcripts/{tid}/txt")
def txt(tid: str, lang: str = "ko"):
    return PlainTextResponse("\n".join(s["text"] for s in segs_for(transcript(tid), lang)),
                             media_type="text/plain; charset=utf-8")


SUMMARY_SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string"}, "decisions": {"type": "array", "items": {"type": "string"}},
    "todos": {"type": "array", "items": {"type": "string"}}},
    "required": ["summary", "decisions", "todos"], "additionalProperties": False}
SUMMARY_CHUNK = 60000  # 글자. 넘으면 나눠 요약한 뒤 합친다


async def optional_json(request):
    if not (await request.body()):
        return {}
    return await body_json(request)


@app.post("/api/transcripts/{tid}/summary")
async def summary(tid: str, request: Request):
    b = await optional_json(request)
    t = transcript(tid)
    full = "\n".join(s["text"] for s in t["segments"])
    if not full.strip():
        raise ApiError(400, "too_short", "전사 내용이 비어 있어요")
    # 해외(Claude) 전송 전 가명처리, 기본 켬(법무 09 L4). 결과에서 원래 값으로 되돌린다
    ps = pseudonym.Pseudonymizer(db.get_setting("pseudonym_names", [])) if b.get("pseudonymize", True) is not False else None
    if ps:
        full = ps.mask(full)
    total = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "est_usd": 0.0}

    def add(u):
        for k in total:
            total[k] += u[k]

    if len(full) <= SUMMARY_CHUNK:
        data, u = claude.call("stt_summary", f"전사문:\n{full}", max_tokens=4000, schema=SUMMARY_SCHEMA)
        add(u)
    else:
        parts = []
        for i in range(0, len(full), SUMMARY_CHUNK):
            d, u = claude.call("stt_summary", f"전사문(일부 {i // SUMMARY_CHUNK + 1}):\n{full[i:i + SUMMARY_CHUNK]}",
                               max_tokens=4000, schema=SUMMARY_SCHEMA)
            add(u)
            parts.append(d)
        data, u = claude.call("stt_summary", "아래는 한 녹음을 나눠 요약한 결과다. 하나의 요약으로 합쳐라.\n"
                              + json.dumps(parts, ensure_ascii=False), max_tokens=4000, schema=SUMMARY_SCHEMA)
        add(u)
    total["est_usd"] = round(total["est_usd"], 6)
    if ps:
        data = ps.unmask(data)
        db.log("pseudonymized", detail={"feature": "stt_summary", "transcript_id": tid, "counts": ps.stats()})
    return {**data, "usage": total, "pseudonymized": ps.stats() if ps else None}


@app.post("/api/transcripts/{tid}/translate", status_code=202)
async def translate(tid: str, request: Request):
    b = await body_json(request)
    lang = (b.get("lang") or "").strip()
    if lang not in jobs.LANG_NAMES or lang == "ko":
        raise ApiError(400, "bad_format", f"지원 언어: {', '.join(k for k in jobs.LANG_NAMES if k != 'ko')}")
    transcript(tid)
    claude.client()  # 키가 없으면 작업을 만들기 전에 503
    return {"job_id": jobs.enqueue("translate", {"transcript_id": tid, "lang": lang,
                                                   "pseudonymize": b.get("pseudonymize", True) is not False})}


# ---------- ③ 브리핑 ----------
@app.post("/api/summarize")
async def summarize(request: Request):
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        f, length = form.get("file"), form.get("length") or "short"
        if not hasattr(f, "read"):
            raise ApiError(400, "bad_format", "파일이 필요해요")
        raw = await f.read(config.SUMMARY_MAX_BYTES + 1)
        if len(raw) > config.SUMMARY_MAX_BYTES:
            raise ApiError(413, "file_too_large", "파일이 너무 커요(30MB 이하)")
        ext = Path(f.filename or "").suffix.lower()
        if ext == ".pdf":
            if not raw.startswith(b"%PDF"):
                raise ApiError(400, "bad_format", "PDF 파일이 아니에요")
            content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                        "data": base64.b64encode(raw).decode()}},
                       {"type": "text", "text": f"길이: {length}\n위 문서를 브리핑해 주세요."}]
        elif ext in (".txt", ".md"):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp949", errors="replace")
            content = f"길이: {length}\n\n문서:\n{text}"
        else:
            raise ApiError(400, "bad_format", ".txt, .md, .pdf 파일만 받아요")
    else:
        b = await body_json(request)
        text, length = (b.get("text") or "").strip(), b.get("length") or "short"
        if not text:
            raise ApiError(400, "too_short", "요약할 내용을 넣어 주세요")
        content = f"길이: {length}\n\n문서:\n{text}"
    if length not in ("short", "medium"):
        raise ApiError(400, "bad_format", "length는 short 또는 medium이에요")
    out, usage = claude.call("briefing", content, max_tokens=2000)
    return {"summary": out.strip(), "usage": usage}


# ---------- ④ 목소리 복제(2차 범위) ----------
@app.api_route("/api/consents/sentence", methods=["GET"])
@app.api_route("/api/consents", methods=["POST"])
@app.api_route("/api/voices/clone", methods=["POST"])
def not_yet():
    raise ApiError(501, "not_implemented", "목소리 복제는 다음 단계에서 열려요(1차 범위: TTS·STT·Claude)")


@app.get("/api/consents")
def consents():
    # [{id, voice_name, voice_deleted_at, purge_at(낭독 음성), audio_purged, record_purge_at(동의서·해시, 게시 중이면 null)}]
    return retention.consents_view()


@app.delete("/api/voices/{vid}")
def delete_voice(vid: str):
    # 샘플·특징값(암호화 폴더)과 엔진 캐시를 즉시 지우고, 동의 기록에 삭제 시각을 적는다
    if not retention.delete_voice(vid):
        raise ApiError(404, "not_found", "복제 음성이 없어요(기본 음성은 지울 수 없어요)")
    return {"ok": True}


@app.put("/api/outputs/{oid}/publication")
async def publication(oid: str, request: Request):
    """외부 게시 여부(동의 기록 보관 기간 계산에 쓴다: 게시 중 + 내린 뒤 1년)."""
    b = await body_json(request)
    must(db.one("SELECT id FROM outputs WHERE id=?", oid), "결과물")
    if b.get("published") is True:
        db.run("UPDATE outputs SET published_at=COALESCE(published_at, ?), unpublished_at=NULL WHERE id=?", db.now(), oid)
    elif b.get("published") is False:
        db.run("UPDATE outputs SET unpublished_at=? WHERE id=? AND published_at IS NOT NULL", db.now(), oid)
    else:
        raise ApiError(400, "bad_format", "published는 true 또는 false예요")
    db.log("publication", output_id=oid, detail={"published": b["published"]})
    o = db.one("SELECT published_at, unpublished_at FROM outputs WHERE id=?", oid)
    return {"id": oid, **o}


# ---------- ⑤ 기록·사용량 ----------
def output_view(o):
    files = json.loads(o["files"] or "{}")
    disc = audio.disclosure(o["engine"], o["is_clone"], o["voice_name"])
    return {"id": o["id"], "kind": o["kind"], "title": o["title"], "created_at": o["created_at"],
            "duration_sec": o["duration_sec"], "voice_id": o["voice_id"], "voice_name": o["voice_name"],
            "is_clone": bool(o["is_clone"]), "ai_label": True,
            "source_expires_at": None,  # TTS 결과는 업로드 원본이 없다(전사 원본 만료는 transcripts 응답에)
            "engine": o["engine"], "caption_text": disc["caption_text"], "disclosure_text": disc["disclosure_text"],
            "disclosure_required": disc["required"], "ai_notice": o["ai_notice"],
            "published_at": o["published_at"], "unpublished_at": o["unpublished_at"],
            "text": o["text_original"], "text_normalized": o["text_normalized"], "normalizer": o["normalizer"],
            "files": {k: True for k in ("mp3", "wav") if k in files} if not o["file_deleted_at"] else {}}


@app.get("/api/outputs")
def outputs(request: Request, to: str | None = None):
    f = request.query_params.get("from")  # 'from'은 파이썬 예약어라 직접 읽는다
    sql, args = "SELECT * FROM outputs WHERE file_deleted_at IS NULL", []
    if f:
        sql += " AND created_at>=?"; args.append(f)
    if to:
        sql += " AND created_at<=?"; args.append(to + "T23:59:59" if len(to) == 10 else to)
    return [output_view(o) for o in db.q(sql + " ORDER BY created_at DESC", *args)]


def output_file(oid, fmt=None):
    o = must(db.one("SELECT * FROM outputs WHERE id=? AND file_deleted_at IS NULL", oid), "결과물")
    files = json.loads(o["files"])
    key = fmt if fmt in files else ("mp3" if "mp3" in files else "wav")
    if fmt and fmt not in files:
        raise ApiError(404, "not_found", f"{fmt} 파일이 없어요")
    p = config.OUTPUTS / files[key]
    if not p.exists():
        raise ApiError(404, "not_found", "파일이 없어요")
    return p, ("audio/mpeg" if key == "mp3" else "audio/wav")


@app.get("/api/outputs/{oid}/audio")
def output_audio(oid: str):
    p, mt = output_file(oid)
    return FileResponse(p, media_type=mt)  # Starlette 1.10 FileResponse가 Range를 처리한다


@app.get("/api/outputs/{oid}/download")
def output_download(oid: str, format: str | None = None):
    p, mt = output_file(oid, format)
    return FileResponse(p, media_type=mt, filename=p.name)


@app.delete("/api/outputs/{oid}")
def output_delete(oid: str):
    o = must(db.one("SELECT * FROM outputs WHERE id=? AND file_deleted_at IS NULL", oid), "결과물")
    for name in json.loads(o["files"]).values():
        (config.OUTPUTS / name).unlink(missing_ok=True)
    db.run("UPDATE outputs SET file_deleted_at=? WHERE id=?", db.now(), oid)
    db.log("output_deleted", output_id=oid)
    return {"ok": True}


@app.get("/api/usage")
def usage():
    return ledger.month_summary()


@app.get("/api/usage/export.csv")
def usage_csv(month: str | None = None):
    month = month or ledger.month_key()
    rows = db.q("SELECT * FROM usage_ledger WHERE substr(ts,1,7)=? ORDER BY ts", month)
    buf = io.StringIO()
    cols = [c["name"] for c in db.q("PRAGMA table_info(usage_ledger)")]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="usage-{month}.csv"'})


@app.get("/api/settings")
def get_settings():
    return {"limit_usd": db.get_setting("limit_usd"), "pseudonym_names": db.get_setting("pseudonym_names", [])}


@app.put("/api/settings")
async def put_settings(request: Request):
    b = await body_json(request)
    out = {}
    if "pseudonym_names" in b:  # 가명처리할 이름 목록(사내 인물 등). 이 PC의 DB에만 둔다
        names = b["pseudonym_names"] or []
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names) or len(names) > 500:
            raise ApiError(400, "bad_format", "pseudonym_names는 이름 문자열 목록(500개 이하)이에요")
        db.set_setting("pseudonym_names", sorted({n.strip() for n in names if n.strip()}))
        out["pseudonym_names"] = db.get_setting("pseudonym_names")
    if "limit_usd" not in b:
        return out
    v = b.get("limit_usd")
    if v in (None, "", 0):
        v = None  # 한도 없음: 경고 없이 사용량만 표시(대표 결정)
    else:
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ApiError(400, "bad_format", "한도는 숫자(USD)여야 해요")
        if v <= 0:
            raise ApiError(400, "bad_format", "한도는 0보다 커야 해요")
    db.set_setting("limit_usd", v)
    return {**out, "limit_usd": v}

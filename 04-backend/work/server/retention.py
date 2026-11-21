"""보관·삭제 규칙(대표 결정·법무 09 §3-3, 2026-11-22).
- 복제 샘플·특징값(target_se): 분리 폴더(secure_voices/{voice_id})에 DPAPI로 암호화. 목소리를 지우면 즉시 삭제(엔진 캐시·중간 파일 포함).
- 동의 낭독 음성: 목소리 삭제 후 365일 뒤 삭제.
- 서면 동의서·동의 시각·낭독 파일 해시(텍스트 기록): 그 목소리로 만든 공개 결과물이 게시되어 있는 동안 + 게시를 내린 뒤 1년.
  (목소리가 남아 있는 동안에도 보관)
- 생성 로그: 복제 음성 삭제 후 365일.
- 업로드 원본: 30일(app.cleanup_uploads)."""
from datetime import datetime, timedelta

from . import config, db, secure

KEEP = timedelta(days=365)

SCHEMA = """
CREATE TABLE IF NOT EXISTS voices(
  id TEXT PRIMARY KEY, name TEXT, subject_name TEXT, consent_id TEXT, engine TEXT, created_at TEXT, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS consents(
  id TEXT PRIMARY KEY, owner_type TEXT, subject_name TEXT, sentence TEXT, recorded_at TEXT,
  audio_path TEXT, audio_sha256 TEXT, doc_path TEXT, doc_sha256 TEXT, feature_consent INTEGER,
  voice_id TEXT, voice_deleted_at TEXT, audio_purged_at TEXT);
"""


def secure_dir(voice_id):
    return config.DATA / "secure_voices" / voice_id      # 샘플·특징값(암호화)


def cache_dir(voice_id):
    return config.DATA / "engine_cache" / voice_id       # 엔진이 만드는 복호화 임시 파일·분할 음성 등


def _ts(s):
    return datetime.fromisoformat(s) if s else None


def delete_voice(voice_id):
    v = db.one("SELECT * FROM voices WHERE id=? AND deleted_at IS NULL", voice_id)
    if not v:
        return False
    secure.wipe_dir(secure_dir(voice_id))
    secure.wipe_dir(cache_dir(voice_id))
    now = db.now()
    db.run("UPDATE voices SET deleted_at=? WHERE id=?", now, voice_id)
    db.run("UPDATE consents SET voice_deleted_at=? WHERE voice_id=?", now, voice_id)
    db.log("voice_deleted", voice_id=voice_id, consent_id=v["consent_id"],
           detail={"secure_dir_removed": not secure_dir(voice_id).exists(), "cache_removed": not cache_dir(voice_id).exists()})
    return True


def record_purge_at(consent):
    """동의 기록(동의서·시각·해시) 삭제 예정 시각. 목소리가 있거나 게시 중인 결과물이 있으면 None(계속 보관)."""
    if not consent["voice_deleted_at"]:
        return None
    outs = db.q("SELECT published_at, unpublished_at FROM outputs WHERE consent_id=?", consent["id"])
    if any(o["published_at"] and not o["unpublished_at"] for o in outs):
        return None
    last = max([_ts(consent["voice_deleted_at"])] + [_ts(o["unpublished_at"]) for o in outs if o["unpublished_at"]])
    return (last + KEEP).isoformat(timespec="seconds")


def audio_purge_at(consent):
    return (_ts(consent["voice_deleted_at"]) + KEEP).isoformat(timespec="seconds") if consent["voice_deleted_at"] else None


def purge(now=None):
    """매일 1회 + 서버 시작 때. 반환: 지운 건수."""
    now = now or datetime.now().astimezone()
    n = {"consent_audio": 0, "consent_record": 0, "generation_log": 0}
    for c in db.q("SELECT * FROM consents WHERE voice_deleted_at IS NOT NULL"):
        if not c["audio_purged_at"] and _ts(audio_purge_at(c)) <= now:
            if c["audio_path"]:
                (config.DATA / c["audio_path"]).unlink(missing_ok=True)
            db.run("UPDATE consents SET audio_path=NULL, audio_purged_at=? WHERE id=?", now.isoformat(timespec="seconds"), c["id"])
            db.log("consent_audio_purged", consent_id=c["id"])
            n["consent_audio"] += 1
        rp = record_purge_at(c)
        if rp and _ts(rp) <= now:
            if c["doc_path"]:
                (config.DATA / c["doc_path"]).unlink(missing_ok=True)
            if c["audio_path"]:
                (config.DATA / c["audio_path"]).unlink(missing_ok=True)
            db.run("DELETE FROM consents WHERE id=?", c["id"])
            db.log("consent_purged", consent_id=c["id"])  # 삭제 사실만 남긴다(설계 §6-4)
            n["consent_record"] += 1
    for v in db.q("SELECT id, deleted_at FROM voices WHERE deleted_at IS NOT NULL"):
        if _ts(v["deleted_at"]) + KEEP <= now:
            cur = db.one("SELECT COUNT(*) k FROM generation_log WHERE voice_id=? AND event<>'voice_deleted'", v["id"])["k"]
            if cur:
                db.run("DELETE FROM generation_log WHERE voice_id=? AND event<>'voice_deleted'", v["id"])
                n["generation_log"] += cur
    return n


def consents_view():
    """GET /api/consents: 목소리를 지운 동의 기록과 삭제 예정일."""
    rows = db.q("""SELECT c.*, v.name voice_name FROM consents c LEFT JOIN voices v ON v.id=c.voice_id
                   WHERE c.voice_deleted_at IS NOT NULL ORDER BY c.voice_deleted_at DESC""")
    return [{"id": c["id"], "voice_name": c["voice_name"], "voice_deleted_at": c["voice_deleted_at"],
             "purge_at": audio_purge_at(c),               # 낭독 음성 삭제 예정(365일)
             "audio_purged": bool(c["audio_purged_at"]),
             "record_purge_at": record_purge_at(c)}        # 동의서·해시 삭제 예정(게시 중이면 null)
            for c in rows]

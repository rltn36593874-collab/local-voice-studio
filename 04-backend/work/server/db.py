"""SQLite. 스레드마다 연결을 따로 쓰고, 쓰기는 짧게 끝낸다."""
import json
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, type TEXT, lane TEXT, status TEXT, progress REAL,
  cancel_requested INTEGER DEFAULT 0, payload TEXT, result TEXT, error TEXT,
  created_at TEXT, started_at TEXT, finished_at TEXT, eta_sec REAL);
CREATE TABLE IF NOT EXISTS outputs(
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, created_at TEXT, duration_sec REAL,
  voice_id TEXT, voice_name TEXT, is_clone INTEGER, consent_id TEXT, engine TEXT,
  engine_version TEXT, files TEXT, text_sha256 TEXT, job_id TEXT, file_deleted_at TEXT,
  text_original TEXT, text_normalized TEXT, normalizer TEXT, ai_notice TEXT, published_at TEXT, unpublished_at TEXT);
CREATE TABLE IF NOT EXISTS transcripts(
  id TEXT PRIMARY KEY, source_name TEXT, duration_sec REAL, language TEXT,
  segments TEXT, translations TEXT DEFAULT '{}', upload_path TEXT, created_at TEXT, job_id TEXT);
CREATE TABLE IF NOT EXISTS generation_log(
  ts TEXT, event TEXT, job_id TEXT, output_id TEXT, voice_id TEXT, consent_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS usage_ledger(
  entry_id TEXT PRIMARY KEY, ts TEXT, request_id TEXT, job_id TEXT, feature TEXT, engine TEXT,
  model_id TEXT, prompt_version TEXT, is_batch INTEGER DEFAULT 0,
  input_tokens INTEGER DEFAULT 0, cache_write_5m_tokens INTEGER DEFAULT 0,
  cache_write_1h_tokens INTEGER DEFAULT 0, cache_read_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0, stop_reason TEXT, status TEXT, latency_ms INTEGER,
  cpu_seconds REAL, audio_in_sec REAL, audio_out_sec REAL, chars_in INTEGER,
  price_version TEXT, cost_usd_est REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS price_book(
  price_version TEXT, model_id TEXT, inp REAL, w5 REAL, w1h REAL, rd REAL, out REAL,
  long_threshold INTEGER, long_inp REAL, long_w5 REAL, long_w1h REAL, long_rd REAL, long_out REAL,
  source TEXT, PRIMARY KEY(price_version, model_id));
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

# 출처: 07-data-claude-credit.md §2(공식 가격 문서, 2026-11-21 조회), 장문 단가는 07-data 대조 확인(2026-11-22)
PRICES = [
    ("2026-11-21", "claude-haiku-5-5", 0.10, 0.125, 0.20, 0.01, 0.50, 100_000, 0.50, 0.625, 1.00, 0.05, 2.50),
    ("2026-11-21", "claude-sonnet-5-5", 2.00, 2.50, 4.00, 0.10, 10.00, None, None, None, None, None, None),
]
SRC = "platform.claude.com/docs/en/about-claude/pricing (07-data §2)"


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}_{secrets.token_hex(6)}"


def conn():
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        _local.c = c
    return c


def init():
    config.DATA.mkdir(parents=True, exist_ok=True)
    c = conn()
    c.executescript(SCHEMA)
    from .retention import SCHEMA as RET_SCHEMA
    c.executescript(RET_SCHEMA)
    have = {r[1] for r in c.execute("PRAGMA table_info(outputs)")}
    for col in ("text_original", "text_normalized", "normalizer", "ai_notice", "published_at", "unpublished_at"):  # 이전 DB 이어 쓰기
        if col not in have:
            c.execute(f"ALTER TABLE outputs ADD COLUMN {col} TEXT")
    for p in PRICES:
        c.execute("INSERT OR IGNORE INTO price_book VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*p, SRC))


def q(sql, *args):
    return [dict(r) for r in conn().execute(sql, args)]


def one(sql, *args):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def run(sql, *args):
    conn().execute(sql, args)


def log(event, **kw):
    detail = kw.pop("detail", None)
    run("INSERT INTO generation_log VALUES(?,?,?,?,?,?,?)", now(), event, kw.get("job_id"), kw.get("output_id"),
        kw.get("voice_id"), kw.get("consent_id"), json.dumps(detail, ensure_ascii=False) if detail else None)


def get_setting(key, default=None):
    r = one("SELECT value FROM settings WHERE key=?", key)
    return json.loads(r["value"]) if r else default


def set_setting(key, value):
    run("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", key, json.dumps(value))

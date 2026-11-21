"""설정. 모든 값은 환경변수로 바꿀 수 있다. API 키는 여기서 읽지 않는다(claude.py가 호출 때 환경변수에서만 읽음)."""
import os
import shutil
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent            # 04-backend/work
ENV_FILE = Path(os.environ.get("VOICETOOL_ENV_FILE", Path(__file__).with_name(".env")))
_ENV_KEYS = ("ANTHROPIC_API_KEY",)  # .env에서 받는 이름(VOICETOOL_*도 허용)


def load_env_file(path=None):
    """사용자가 쓴 .env를 읽어 환경변수로 넣는다(대표 결정 2026-11-22). 이미 있는 환경변수가 우선.
    값은 어디에도 출력·기록하지 않는다. 형식 오류도 줄 내용을 내보이지 않고 건너뛴다. 반환: 넣은 이름 목록."""
    path = Path(path or ENV_FILE)
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if (name in _ENV_KEYS or name.startswith("VOICETOOL_")) and value and not os.environ.get(name):
            os.environ[name] = value
            loaded.append(name)
    return loaded


load_env_file()  # 다른 설정값보다 먼저
DATA = Path(os.environ.get("VOICETOOL_DATA_DIR", WORK / "data"))
OUTPUTS, UPLOADS, PROMPTS = DATA / "outputs", DATA / "uploads", Path(__file__).parent / "prompts"
DB_PATH = DATA / "app.db"

# 엔진 가상환경: DevOps voice-bench 재사용(읽기·실행만, 2026-11-22 DevOps 합의)
BENCH = Path(os.environ.get("VOICETOOL_BENCH_DIR", WORK.parent.parent / "06-devops" / "work" / "voice-bench"))
ENGINE_PY = {
    "faster_whisper": BENCH / ".venv" / "Scripts" / "python.exe",
    "melo": BENCH / ".venv-melo" / "Scripts" / "python.exe",
    "supertonic": BENCH / ".venv-supertonic" / "Scripts" / "python.exe",
}
# env.ps1과 같은 캐시 위치 → 이미 받은 모델을 다시 받지 않는다
ENGINE_ENV = {
    "HF_HOME": str(BENCH / "cache" / "hf"),
    "TORCH_HOME": str(BENCH / "cache" / "torch"),
    "XDG_CACHE_HOME": str(BENCH / "cache"),
    "NLTK_DATA": str(BENCH / "cache" / "nltk"),
    "SUPERTONIC_CACHE_DIR": str(BENCH / "cache" / "supertonic3"),
    "CUDA_VISIBLE_DEVICES": "",
    "PYTHONIOENCODING": "utf-8",
}

# 엔진 선택(DevOps 실측·QA 판정 후 교체): mock | melo | supertonic / mock | faster_whisper
TTS_ENGINE = os.environ.get("VOICETOOL_TTS_ENGINE", "supertonic")  # QA 청취 Supertonic 2.60 > Melo 1.80(대표 2026-11-22)
STT_ENGINE = os.environ.get("VOICETOOL_STT_ENGINE", "faster_whisper")
# QA A7-5(대표 2026-11-22): 기본 medium(CER 3.28%, 1시간 24분), 빠른 초안 small(4.99%, 9.5분). large-v3는 기준 미달로 뺀다
STT_MODELS = {"accurate": "medium", "draft": "small"}
STT_MODEL = os.environ.get("VOICETOOL_STT_MODEL", STT_MODELS["accurate"])

FFMPEG_DIR = Path(os.environ.get("VOICETOOL_FFMPEG_DIR", WORK.parent.parent / "06-devops" / "work" / "tools" / "ffmpeg-lgpl" / "bin"))


def ffmpeg():
    p = FFMPEG_DIR / "ffmpeg.exe"
    return str(p) if p.exists() else shutil.which("ffmpeg")


CLAUDE_MODEL = "claude-haiku-5-5"
TTS_MAX_CHARS = 5000            # 가안. 실측 후 확정
UPLOAD_MAX_BYTES = 2 * 1024**3  # 가안 2GB
SUMMARY_MAX_BYTES = 30 * 1024**2
UPLOAD_KEEP_DAYS = 30           # 대표 승인 2026-11-22
TARGET_RMS_DBFS = -20.0         # 출력 음량 보정: 말소리 구간 RMS −20 dBFS, 봉우리 −1 dBFS(QA A7-1·A7-7)
# Supertonic 기본 스타일·속도(QA A7-7 R2 블라인드 청취 1위 F2·0.95, 잠정·R3 판정 전) → 설정값으로 바꿀 수 있게 둔다
TTS_STYLE_FEMALE = os.environ.get("VOICETOOL_TTS_STYLE_FEMALE", "F2")
TTS_STYLE_MALE = os.environ.get("VOICETOOL_TTS_STYLE_MALE", "M2")
TTS_DEFAULT_SPEED = float(os.environ.get("VOICETOOL_TTS_SPEED", "0.95"))

PORT = int(os.environ.get("VOICETOOL_PORT", "8000"))  # 시험용 서버는 다른 포트로 띄워 운영 서버와 겹치지 않게
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", "127.0.0.1:5173", "localhost:5173"}
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

for d in (OUTPUTS, UPLOADS):
    d.mkdir(parents=True, exist_ok=True)

# 법무 09 §2-3 6번: OpenVoice wavmark 워터마크(enable_watermark 기본 True)는 끄지 않는다. 복제 엔진 어댑터가 이 값을 그대로 넘긴다.
OPENVOICE_WATERMARK = True

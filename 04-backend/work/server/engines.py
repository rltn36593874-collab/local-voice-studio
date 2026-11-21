"""엔진 어댑터(설계 §9). 서버는 tts_chunk()/transcribe()만 부른다.
실제 엔진은 voice-bench 가상환경의 하위 프로세스(engine_worker.py)로 띄워 계속 살려 둔다. mock은 프로세스 없이 서버 안에서 돈다.
엔진 교체 = 환경변수 VOICETOOL_TTS_ENGINE / VOICETOOL_STT_ENGINE."""
import json
import math
import os
import queue
import struct
import subprocess
import threading
import wave
from pathlib import Path

from . import config

WORKER = Path(__file__).with_name("engine_worker.py")


class EngineError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class Canceled(Exception):
    pass


class WorkerProc:
    def __init__(self, engine, model=None):
        self.engine, self.model = engine, model
        self.p = None
        self.events = queue.Queue()
        self.version = None

    @property
    def alive(self):
        return self.p is not None and self.p.poll() is None

    def start(self):
        py = config.ENGINE_PY[self.engine]
        if not py.exists():
            raise EngineError("engine_missing", f"엔진 가상환경이 없어요: {py}")
        env = {**os.environ, **config.ENGINE_ENV}
        env.pop("ANTHROPIC_API_KEY", None)  # 엔진 프로세스에는 키를 넘기지 않는다
        args = [str(py), "-I", str(WORKER), self.engine] + ([self.model] if self.model else [])
        logs = config.DATA / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.log = open(logs / f"engine_{self.engine}.log", "ab")  # 엔진 stderr(진단용). 키는 엔진에 넘기지 않으므로 들어가지 않는다
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                  text=True, encoding="utf-8", errors="replace", env=env, cwd=str(config.DATA),
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.events = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        ev = self._next(timeout=900)  # 첫 실행은 모델 다운로드가 낄 수 있다
        if ev.get("event") != "ready":
            self.stop()
            raise EngineError(ev.get("code", "engine_error"), ev.get("message", "엔진을 시작하지 못했어요"))
        self.version = ev.get("version")

    def _read(self):
        try:
            for line in self.p.stdout:  # errors="replace": 깨진 바이트가 와도 읽기 스레드가 죽지 않는다
                try:
                    self.events.put(json.loads(line))
                except json.JSONDecodeError:
                    pass  # 프로토콜이 아닌 줄은 버린다
        except Exception as e:  # 읽기 스레드가 죽으면 서버가 무한정 기다리므로 반드시 오류 이벤트를 남긴다
            self.events.put({"event": "error", "code": "engine_error", "message": f"엔진 출력 읽기 실패: {type(e).__name__}"})
            return
        self.events.put({"event": "error", "code": "engine_error", "message": "엔진 프로세스가 종료됐어요"})

    def _next(self, timeout=None):
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            raise EngineError("engine_error", "엔진 응답 시간이 초과됐어요")

    def send(self, req):
        self.p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def request(self, req, on_event=None, is_canceled=None):
        self.send(req)
        cancel_sent = False
        while True:
            try:
                ev = self.events.get(timeout=1)
            except queue.Empty:
                if not self.alive:
                    raise EngineError("engine_error", "엔진 프로세스가 종료됐어요")
                ev = None
            if is_canceled and is_canceled() and not cancel_sent:
                self.send({"op": "cancel"})
                cancel_sent = True
            if ev is None:
                continue
            kind = ev.get("event")
            if kind == "done":
                return ev
            if kind == "canceled":
                raise Canceled()
            if kind == "error":
                raise EngineError(ev.get("code", "engine_error"), ev.get("message", ""))
            if on_event:
                on_event(ev)

    def stop(self):
        if self.p:
            try:
                self.p.stdin.close()
                self.p.wait(10)
            except Exception:
                self.p.kill()
            self.p = None
        if getattr(self, "log", None):
            self.log.close()
            self.log = None


_procs: dict[str, WorkerProc] = {}
_lock = threading.Lock()


def _get(engine, model=None, on_preparing=None):
    """필요한 엔진(같은 모델)만 올린다. 다른 엔진·다른 모델은 내린다(한 번에 하나, 15.5GB RAM, 설계 §1)."""
    key = f"{engine}:{model or ''}"
    with _lock:
        for k in [k for k in _procs if k != key]:
            _procs.pop(k).stop()
        w = _procs.get(key)
        if w is None or not w.alive:
            if on_preparing:
                on_preparing()
            w = WorkerProc(engine, model)
            w.start()
            _procs[key] = w
        return w


def _alive(engine):
    return any(k.startswith(engine + ":") and w.alive for k, w in _procs.items())


def status():
    return {
        "tts": {"name": config.TTS_ENGINE, "loaded": config.TTS_ENGINE == "mock" or _alive(config.TTS_ENGINE)},
        "stt": {"name": config.STT_ENGINE, "loaded": config.STT_ENGINE == "mock" or _alive(config.STT_ENGINE),
                "model": config.STT_MODEL, "models": config.STT_MODELS},
        "clone": {"name": None, "loaded": False},
    }


def shutdown():
    with _lock:
        for w in _procs.values():
            w.stop()
        _procs.clear()


def tts_version():
    if config.TTS_ENGINE == "mock":
        return "mock tone"
    w = next((w for k, w in _procs.items() if k.startswith(config.TTS_ENGINE + ":")), None)
    return w.version if w else None


def tts_chunk(text, out_path, speed=1.0, voice=None, on_preparing=None):
    """한 덩어리를 WAV로 합성한다."""
    if config.TTS_ENGINE == "mock":
        return _mock_tone(out_path, seconds=max(0.6, len(text) / 7 / speed))
    w = _get(config.TTS_ENGINE, on_preparing=on_preparing)
    w.request({"op": "tts", "text": text, "out": str(out_path), "speed": speed, "voice": voice})


def transcribe(path, language, on_segment, is_canceled, on_preparing=None, model=None):
    """반환 (duration, language, version). 구간마다 on_segment(seg dict) 호출."""
    if config.STT_ENGINE == "mock":
        try:
            with wave.open(str(path)) as f:
                dur = f.getnframes() / f.getframerate()
        except (wave.Error, EOFError):
            dur = 12.0  # mock: wav가 아니면 길이를 모르니 고정값
        n = max(1, math.ceil(dur / 5))
        for i in range(n):
            if is_canceled():
                raise Canceled()
            on_segment({"start": i * 5.0, "end": min((i + 1) * 5.0, dur), "text": f"(mock 전사 {i + 1})", "progress": (i + 1) / n})
        return dur, language or "ko", "mock"
    w = _get(config.STT_ENGINE, model or config.STT_MODEL, on_preparing=on_preparing)
    ev = w.request({"op": "transcribe", "path": str(path), "language": language},
                   on_event=lambda e: on_segment(e) if e.get("event") == "segment" else None,
                   is_canceled=is_canceled)
    return ev.get("duration"), ev.get("language"), w.version


def _mock_tone(out_path, seconds, sr=22050):
    with wave.open(str(out_path), "wb") as f:
        f.setnchannels(1), f.setsampwidth(2), f.setframerate(sr)
        f.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / sr)))
                               for i in range(int(seconds * sr))))

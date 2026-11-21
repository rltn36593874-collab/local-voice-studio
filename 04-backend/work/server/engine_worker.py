"""엔진 워커: 엔진 가상환경(voice-bench)의 python.exe로 실행된다. 서버 패키지를 import하지 않는다(표준 라이브러리 + 엔진만).
프로토콜: stdin/stdout JSON 한 줄씩.
  시작 → {"event":"ready", "engine":..., "version":...}
  요청 {"op":"tts","text","out","speed","voice"} → {"event":"done","sr"}
  요청 {"op":"transcribe","path","language"} → {"event":"segment",...}* → {"event":"done","duration","language"}
  요청 {"op":"cancel"} → 진행 중인 전사를 다음 구간에서 멈춤 → {"event":"canceled"}
  실패 → {"event":"error","code","message"}
사용: python engine_worker.py <engine> [model]
"""
import io
import json
import os
import queue
import sys
import threading
import traceback

# 프로토콜 전용 출력: 원래 stdout(fd 1)을 복제해 UTF-8로 쓴다. -I 실행이라 PYTHONIOENCODING이 안 먹고 기본은 cp949다.
# 그리고 fd 1 자체를 stderr로 돌려, C 라이브러리가 직접 찍는 글(cp949 경고 등)이 프로토콜 줄에 섞이지 않게 한다(2026-11-22 통합 시험에서 발견).
_out = io.TextIOWrapper(os.fdopen(os.dup(1), "wb"), encoding="utf-8", newline="\n")
os.dup2(2, 1)
sys.stdout = sys.stderr
sys.stdin.reconfigure(encoding="utf-8")
cancel = threading.Event()
reqs = queue.Queue()


def emit(**kw):
    _out.write(json.dumps(kw, ensure_ascii=False) + "\n")
    _out.flush()


def reader():
    for line in sys.stdin:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("op") == "cancel":
            cancel.set()
        else:
            reqs.put(r)
    reqs.put(None)  # 서버가 stdin을 닫으면 종료


def hf_rev(*parts):
    """받아 둔 모델의 HF 커밋(법무 09 §1-6: 모델 버전·리비전 기록). 못 찾으면 'rev?'.
    hub 캐시는 refs/main, local_dir 방식(supertonic)은 .cache/huggingface/download/*.metadata 첫 줄이 커밋이다."""
    p = os.path.join(*parts)
    try:
        if os.path.isdir(p):  # local_dir
            meta = os.path.join(p, ".cache", "huggingface", "download", "config.json.metadata")
            with open(meta, encoding="utf-8") as f:
                return f.readline().strip()
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "rev?"


def ver(pkg):
    try:
        from importlib.metadata import version
        return version(pkg)
    except Exception:
        return "unknown"


class FasterWhisper:
    def __init__(self, model):
        from faster_whisper import WhisperModel
        # DevOps가 받아 둔 위치(HF_HOME/fw). 지정하지 않으면 hf/hub에 다시 받는다(DevOps 안내 2026-11-22)
        root = os.path.join(os.environ["HF_HOME"], "fw") if os.environ.get("HF_HOME") else None
        self.m = WhisperModel(model or "small", device="cpu", compute_type="int8", download_root=root)
        rev = hf_rev(root or "", f"models--Systran--faster-whisper-{model or 'small'}", "refs", "main")
        self.version = f"faster-whisper {ver('faster-whisper')} / Systran/faster-whisper-{model or 'small'}@{rev} int8"

    def transcribe(self, r):
        segs, info = self.m.transcribe(r["path"], language=r.get("language") or None, beam_size=5, vad_filter=True)
        dur = info.duration or 0
        for s in segs:
            if cancel.is_set():
                return emit(event="canceled")
            emit(event="segment", start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip(),
                 progress=min(s.end / dur, 1.0) if dur else None)
        emit(event="done", duration=dur, language=info.language)


class Melo:
    def __init__(self, model):
        from melo.api import TTS
        self.m = TTS(language="KR", device="cpu")
        self.spk = self.m.hps.data.spk2id["KR"]
        hub = os.path.join(os.environ.get("HF_HOME", ""), "hub")
        self.version = (f"MeloTTS {ver('melotts')} / myshell-ai/MeloTTS-Korean@{hf_rev(hub, 'models--myshell-ai--MeloTTS-Korean', 'refs', 'main')}"
                        f" + kykim/bert-kor-base@{hf_rev(hub, 'models--kykim--bert-kor-base', 'refs', 'main')}")

    def tts(self, r):
        self.m.tts_to_file(r["text"], self.spk, r["out"], speed=float(r.get("speed", 1.0)), quiet=True)
        emit(event="done", sr=self.m.hps.data.sampling_rate)


class Supertonic:
    # OpenRAIL-M 가중치: 법무 조건부 채택(공개물마다 보이는 AI 고지 필수). QA 청취 우세로 기본 TTS(대표 2026-11-22).
    # 호출 방식은 DevOps 실측 코드(voice-bench/supertonic_variants.py)와 같다.
    def __init__(self, model):
        import numpy as np
        import soundfile as sf
        from supertonic import TTS
        self.np, self.sf = np, sf
        threads = int(os.environ.get("VOICETOOL_THREADS", "8"))
        self.m = TTS(model=model or "supertonic-3", intra_op_num_threads=threads)
        self.styles = {}
        rev = hf_rev(os.environ.get("SUPERTONIC_CACHE_DIR", ""))
        self.version = f"supertonic {ver('supertonic')} / Supertone/{model or 'supertonic-3'}@{rev}"

    def tts(self, r):
        name = r.get("voice") or "F1"
        style = self.styles.get(name) or self.styles.setdefault(name, self.m.get_voice_style(name))
        wav, _ = self.m.synthesize(r["text"], style, speed=float(r.get("speed", 1.0)), lang="ko")
        wav = self.np.clip(self.np.asarray(wav, dtype=self.np.float32).squeeze(), -1, 1)
        self.sf.write(r["out"], wav, self.m.sample_rate, subtype="PCM_16")
        emit(event="done", sr=self.m.sample_rate)


ENGINES = {"faster_whisper": FasterWhisper, "melo": Melo, "supertonic": Supertonic}


def main():
    name = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        eng = ENGINES[name](model)
    except Exception as e:
        traceback.print_exc()
        emit(event="error", code="engine_load_failed", message=f"{type(e).__name__}: {e}"[:500])
        return 1
    threading.Thread(target=reader, daemon=True).start()
    emit(event="ready", engine=name, version=eng.version, pid=os.getpid())
    while (r := reqs.get()) is not None:
        cancel.clear()
        try:
            getattr(eng, r["op"])(r)
        except Exception as e:
            traceback.print_exc()
            code = "out_of_memory" if isinstance(e, MemoryError) else "engine_error"
            emit(event="error", code=code, message=f"{type(e).__name__}: {e}"[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())

# CPU 음성 엔진 후보 목록 (2단계, 사내 전용 · 이 PC 기준)

- 작성: 04 백엔드팀 · 2026-11-22
- 대상 PC: Core Ultra 5 225(10코어), RAM 15.5GB, NVIDIA GPU 없음, Windows 11
- 라이선스 원칙(대표 확정): **코드와 가중치 모두** MIT·Apache-2.0처럼 상업 이용이 명확히 허용된 것만 쓴다. 비상업(NC)·연구 전용·매출 기준 조항이 있거나 가중치 라이선스가 불명확하면 뺀다.
- 조사 방법
  - 저장소 LICENSE·README, Hugging Face 모델 카드·API 메타데이터, PyPI JSON을 열어 확인했다. 설치·실행은 하지 않았다(설치는 DevOps 담당).
  - 아래 핵심 항목은 백엔드가 원문과 직접 다시 대조했다(2026-11-22).
    - HF 라이선스 메타: `Systran/faster-whisper-small·medium·large-v3`, `deepdml/faster-whisper-large-v3-turbo-ct2`, `myshell-ai/MeloTTS-Korean`, `myshell-ai/OpenVoiceV2`, `ResembleAI/chatterbox`는 모두 `mit`이고, `Supertone/supertonic-2·3`은 `openrail`
    - PyPI 버전·Windows 휠: `faster-whisper` 1.2.1, `pywhispercpp` 1.5.1(cp310~312 win_amd64), `chatterbox-tts` 0.1.7, `deepfilternet`·`deepfilterlib` 0.5.6(Windows 휠은 **cp38~cp311만**), `noisereduce` 3.0.3
    - 원문 문장: Demucs "The license of the weights is not clear", DeepFilterNet "All code and model weights … dual-licensed", OpenVoice "V1 and V2 are MIT Licensed. Free for both commercial and research use", Supertonic LICENSE "BigScience Open RAIL-M"
- **속도는 전부 미확인**이다. 이 PC에서 잰 값은 없다. 공개 수치도 다른 CPU에서 잰 것이다. 최종 선택은 DevOps 실측과 대표 청취로 정한다.
- 예시 코드: README 원문을 그대로 옮긴 것은 "원문", 여러 조각을 조합했거나 인자 일부를 추정한 것은 "조합"으로 표시했다. "조합" 코드는 DevOps가 처음 실행할 때 고쳐야 할 수 있다.

---

## 0. 한눈에 보기

| 기능 | 1순위 | 2순위 | 3순위 | 비고 |
|---|---|---|---|---|
| STT | **faster-whisper**(CPU int8) | pywhispercpp(whisper.cpp) | — | 둘 다 MIT·Whisper 가중치 |
| 한국어 TTS | **MeloTTS-Korean** | CosyVoice2/3(Apache, CPU 속도 미검증) | (비교 측정만) Supertonic 3 | Supertonic은 OpenRAIL-M. 대표 결정으로 비교 측정만 허용하고, MeloTTS가 QA에서 미달할 때만 채택을 정한다(§2) |
| 제로샷 클로닝 | **OpenVoice V2**(+MeloTTS KR) | Fun-CosyVoice3 zero-shot | Chatterbox Multilingual(MIT, 2026-08 유지보수 종료) | |
| 보이스 체인저 | **OpenVoice V2 ToneColorConverter** | Chatterbox VC(유지보수 종료) | — | CosyVoice VC는 v1(300M)에만 확인됨 |
| 음원 분리 ① 음성 잡음 제거(보이스 아이솔레이터) | **DeepFilterNet** | noisereduce(모델 없는 신호처리) | — | |
| 음원 분리 ② 노래·배경음 분리(스템) | **후보 없음** | — | — | Demucs·Spleeter·UVR 모델은 가중치 라이선스가 불명확해 원칙상 제외(§5) |

**설치 메모(DevOps용)**: 이 PC에는 Python 3.12가 깔려 있다. 하지만 `deepfilterlib`는 Windows 휠이 3.11까지만 있다. MeloTTS·OpenVoice는 옛 버전 핀(`numpy==1.22.0`, `librosa==0.9.1`, `transformers==4.27.4` 등)이 있고, OpenVoice 공식 안내는 conda Python 3.9다. 엔진별로 **가상환경을 나누는 것**을 권한다. 예를 들면 STT는 3.11~3.12, MeloTTS·OpenVoice는 3.9~3.10, DeepFilterNet은 3.11이다. MeloTTS 설치 문서는 Windows 사용자에게 Docker를 권한다(제안이고, 실제 설치 결과는 DevOps 판단).

---

## 1. STT

| 후보 | pip | 모델 ID | 코드 라이선스 | 가중치 라이선스 | 한국어 | CPU 근거 | 판정 |
|---|---|---|---|---|---|---|---|
| **faster-whisper** | `faster-whisper` (1.2.1, Python ≥3.9) | `small`, `medium`, `large-v3` → HF `Systran/faster-whisper-{small,medium,large-v3}`. turbo는 `deepdml/faster-whisper-large-v3-turbo-ct2`(제3자 변환본) | MIT (github.com/SYSTRAN/faster-whisper) | MIT (HF 메타, 백엔드 재확인) | Whisper 다국어 모델(`ko` 언어 코드). HF 메타에 ko | README: `WhisperModel(model_size, device="cpu", compute_type="int8")`. README 벤치: small, CPU int8, beam 5에서 **1분 42초·1,477MB**(i7-12700K 8스레드, 13분 오디오 기준표) | **1순위** |
| pywhispercpp (whisper.cpp) | `pywhispercpp` (1.5.1, Windows 휠 cp310~312) | `small`, `medium`, `large-v3-turbo-q5_0` 등 ggml 파일(HF `ggerganov/whisper.cpp`) | MIT (whisper.cpp, pywhispercpp) | MIT (HF `ggerganov/whisper.cpp`) | Whisper와 같음 | whisper.cpp README "Support for CPU-only inference", 정수 양자화. 속도 수치 없음 | **2순위**(의존성이 가볍다. torch 불필요) |

- 제외: sherpa-onnx Korean zipformer(코드·카드는 Apache-2.0이지만 학습 데이터가 AI Hub이고 데이터 약관을 확인 못 함. 원칙상 보류), SenseVoice(FunASR 모델 라이선스에 상업 허용 명시 없음 + 약관 자동 개정), Moonshine Korean(Moonshine Community License, 비상업 조항), Vosk Korean(Apache-2.0이지만 WER 28.1로 정확도 탈락).

**예시 — faster-whisper** (조합: README의 CPU int8 줄 + HF 카드의 transcribe 예. 출처 https://github.com/SYSTRAN/faster-whisper)
```python
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")   # medium / large-v3 로 바꿔 실측
segments, info = model.transcribe("audio.mp3", beam_size=5, language="ko")
print("detected:", info.language, info.language_probability)
for s in segments:
    print("[%.2fs -> %.2fs] %s" % (s.start, s.end, s.text))
```

**예시 — pywhispercpp** (조합: README 예는 `Model('base.en')`. 출처 https://github.com/absadiki/pywhispercpp)
```python
from pywhispercpp.model import Model

model = Model("small")                 # 다국어 모델명. 처음 실행 때 자동 다운로드
for seg in model.transcribe("audio.wav"):   # wav가 아니면 ffmpeg 필요
    print(seg.text)
```
- 한국어 지정 인자(예: `language="ko"`)는 README에서 확인 못 했다. DevOps가 실행할 때 확인한다.

---

## 2. 한국어 TTS

| 후보 | pip | 모델 ID | 코드 라이선스 | 가중치 라이선스 | 한국어 | CPU 근거 | 판정 |
|---|---|---|---|---|---|---|---|
| **MeloTTS-Korean** | PyPI 패키지 없음 → `pip install git+https://github.com/myshell-ai/MeloTTS.git` 후 `python -m unidic download` | HF `myshell-ai/MeloTTS-Korean`, 코드에서 `TTS(language='KR')` | MIT | MIT (HF 메타, 재확인) | 한국어 전용 모델 | README "Fast enough for CPU real-time inference."(수치 없음) | **1순위**(기본 화자 1명. 클로닝은 OpenVoice와 결합) |
| CosyVoice2-0.5B / Fun-CosyVoice3-0.5B | PyPI 없음 → `git clone --recursive https://github.com/FunAudioLLM/CosyVoice` + `pip install -r requirements.txt` | `FunAudioLLM/CosyVoice2-0.5B`, `FunAudioLLM/Fun-CosyVoice3-0.5B-2512` | Apache-2.0 | Apache-2.0 | README "9 common languages (… Korean …)" | CUDA가 없으면 fp16/jit/trt를 끄는 코드 분기가 있다. 공식 CPU 문서·속도 없음. 0.5B LLM이라 CPU에서 느릴 가능성이 크다 | **2순위(조건부)** — 실측해서 MeloTTS보다 품질이 좋고 속도가 기준(기획 §4: 음성 1분에 2분 이하) 안이면 채택 |

- **보류(대표 판단 필요) — Supertonic 2/3** (`supertonic` 1.3.1, HF `Supertone/supertonic-3`): 코드는 MIT이고 가중치는 **BigScience OpenRAIL-M**이다. 비상업이나 매출 기준 조항은 없다. 대신 용도 제한(동의 없는 사칭·딥페이크 금지, 기계 생성 사실을 알리지 않은 게시 금지 등)이 있고, 이 제한을 다음 사용자에게 전달할 의무가 있다. 한국어(`ko`)를 지원하고 ONNX Runtime으로 CPU에서 빠르다(supertonic-2 카드 기준 M4 Pro RTF 0.012~0.023). 우리 사용 방식(AI 표시, 동의받은 목소리만 사용)은 제한 조항과 충돌하지 않아 보인다.
  - **[대표 결정 2026-11-22]** 비교 측정 대상으로는 허용한다. 채택은 QA 판정에서 MeloTTS가 미달할 때만 결정한다. 채택하면 OpenRAIL-M 용도 제한 조항(Attachment A)을 이 문서와 로컬 API 문서에 남긴다.
  - 예시(조합: PyPI 페이지 예는 `lang="en"`. `ko`는 지원 언어표 근거. 출처 https://pypi.org/project/supertonic/):
    ```python
    from supertonic import TTS
    tts = TTS(auto_download=True)                       # 처음 실행 때 모델 다운로드
    style = tts.get_voice_style(voice_name="M1")
    wav, duration = tts.synthesize("안녕하세요. 사내 음성 도구 시험입니다.", voice_style=style, lang="ko")
    tts.save_audio(wav, "supertonic_ko.wav")
    ```
- 제외: Piper 한국어(`ko_KR/kss` 음성이 CC BY-NC-SA 4.0, 코드 `piper1-gpl`은 GPL-3.0), Kokoro(한국어 미지원), F5-TTS·Fish·Higgs 등(1단계 §6.6, NC·매출 기준).

**예시 — MeloTTS** (조합: HF 카드 설명과 install.md의 device 값. 출처 https://huggingface.co/myshell-ai/MeloTTS-Korean , https://github.com/myshell-ai/MeloTTS/blob/main/docs/install.md)
```python
from melo.api import TTS

model = TTS(language="KR", device="cpu")
speaker_ids = model.hps.data.spk2id
model.tts_to_file("안녕하세요. 사내 음성 도구 시험입니다.", speaker_ids["KR"], "kr.wav", speed=1.0)
```

**예시 — CosyVoice3** (조합: 저장소 `example.py`의 zero-shot 흐름. 원문 문장은 중국어. 출처 https://github.com/FunAudioLLM/CosyVoice/blob/main/example.py)
```python
import sys; sys.path.append("third_party/Matcha-TTS")
from cosyvoice.cli.cosyvoice import AutoModel
from huggingface_hub import snapshot_download
import torchaudio

snapshot_download("FunAudioLLM/Fun-CosyVoice3-0.5B-2512", local_dir="pretrained_models/Fun-CosyVoice3-0.5B")
cosyvoice = AutoModel(model_dir="pretrained_models/Fun-CosyVoice3-0.5B")
for i, out in enumerate(cosyvoice.inference_zero_shot(
        "합성할 한국어 문장입니다.",
        "You are a helpful assistant.<|endofprompt|>참조 음성에서 말한 내용",
        "./ref.wav", stream=False)):
    torchaudio.save(f"cosy_{i}.wav", out["tts_speech"], cosyvoice.sample_rate)
```
- 출력 키 `tts_speech`는 요약본으로만 확인했다(실행할 때 확인).

---

## 3. 제로샷 음성 클로닝

| 후보 | pip | 모델 ID | 코드 라이선스 | 가중치 라이선스 | 한국어 | CPU 근거 | 판정 |
|---|---|---|---|---|---|---|---|
| **OpenVoice V2** (+ MeloTTS KR) | PyPI 없음 → `git clone https://github.com/myshell-ai/OpenVoice` + `pip install -e .`, MeloTTS 설치(§2), 체크포인트 `checkpoints_v2_0417.zip` | HF `myshell-ai/OpenVoiceV2` (`converter/`, `base_speakers/ses/kr.pth`) | MIT ("Free for both commercial and research use", 재확인) | MIT (HF 메타, 재확인) | README "English, Spanish, French, Chinese, Japanese and Korean are natively supported in OpenVoice V2" | 데모 노트북: `device = "cuda:0" if torch.cuda.is_available() else "cpu"`. 속도 수치 없음 | **1순위**. 변환 결과에 `wavmark` 워터마크가 기본으로 들어간다(`enable_watermark` 기본 True) → AI 표시에 도움이 된다 |
| Fun-CosyVoice3 zero-shot | §2와 같음 | `FunAudioLLM/Fun-CosyVoice3-0.5B-2512` | Apache-2.0 | Apache-2.0 | 한국어 포함 | CPU 속도 미검증 | **2순위(조건부)** |
| Chatterbox Multilingual V3 | `chatterbox-tts` (0.1.7, Python ≥3.10, `torch==2.6.0` 핀) | HF `ResembleAI/chatterbox`(`t3_model="v3"`) | MIT | MIT (HF 메타, 재확인) | 23개 언어에 Korean(ko) | README `device = "cuda"  # or "cpu"`. 다국어 모델의 CPU 속도 언급 없음 | **3순위**. 2026-08 유지보수 종료. 출력에 Perth 워터마크가 항상 들어간다 |

**예시 — OpenVoice V2 클로닝 TTS** (조합: `demo_part3.ipynb` 셀 조각. `source_se` 로드 줄은 노트북에서 확인 못 해 경로를 추정했다. 출처 https://github.com/myshell-ai/OpenVoice/blob/main/demo_part3.ipynb)
```python
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
from melo.api import TTS

device = "cpu"
conv = ToneColorConverter("checkpoints_v2/converter/config.json", device=device)
conv.load_ckpt("checkpoints_v2/converter/checkpoint.pth")

target_se, _ = se_extractor.get_se("my_voice_sample.wav", conv, vad=True)       # 복제할 목소리
source_se = torch.load("checkpoints_v2/base_speakers/ses/kr.pth", map_location=device)  # 추정 경로

tts = TTS(language="KR", device=device)
tts.tts_to_file("복제한 목소리로 읽을 문장입니다.", tts.hps.data.spk2id["KR"], "tmp.wav", speed=1.0)
conv.convert(audio_src_path="tmp.wav", src_se=source_se, tgt_se=target_se,
             output_path="cloned.wav", message="@MyShell")
```
- `se_extractor`는 import할 때 `faster_whisper`와 `whisper_timestamped`를 요구한다(조사 결과). OpenVoice가 핀으로 고정한 `faster-whisper==0.9.0`이 §1의 1.2.1과 충돌하므로 **가상환경을 나눠야 한다**.

**예시 — Chatterbox Multilingual** (조합: README·HF 카드. 클로닝용 참조 음성 인자명은 확인 못 함. 출처 https://github.com/resemble-ai/chatterbox)
```python
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
model = ChatterboxMultilingualTTS.from_pretrained(device="cpu", t3_model="v3")
wav = model.generate("안녕하세요.", language_id="ko")   # 참조 음성 인자(예: audio_prompt_path)는 실행 시 확인
```

---

## 4. 보이스 체인저 (음성 → 음성)

| 후보 | pip | 모델 ID | 코드 라이선스 | 가중치 라이선스 | 언어 | CPU 근거 | 판정 |
|---|---|---|---|---|---|---|---|
| **OpenVoice V2 ToneColorConverter** | §3과 같음 | HF `myshell-ai/OpenVoiceV2` `converter/` | MIT | MIT | README "input speech audio of OpenVoice can be in Any Language" | `device` 인자. 속도 수치 없음 | **1순위**. §3과 같은 모델을 쓰므로 추가 설치가 없다 |
| Chatterbox VC | `chatterbox-tts` 0.1.7 | HF `ResembleAI/chatterbox`(`s3gen.pt`, `ve.pt`) | MIT | MIT | VC가 언어와 무관하다는 문구는 확인 못 함 | `vc.py`가 CPU면 `map_location=cpu`로 처리. 속도 수치 없음 | **2순위**. 유지보수 종료, Perth 워터마크 |

- 제외·보류
  - CosyVoice: Apache-2.0이지만 `inference_vc` 예제는 v1(`CosyVoice-300M`)에만 있고, 2/3에서 동작하는지 확인 못 함.
  - RVC: 코드·HF 메타는 MIT지만 `hubert_base`·`rmvpe`의 개별 라이선스가 없고, 화자마다 학습이 필요하다.
  - kNN-VC: WavLM 가중치 라이선스가 불명확하고 영어로만 사전학습됐다.
  - Seed-VC: 코드 GPL-3.0, 가중치 라이선스 명시 없음.
- 기획 MVP에서 보이스 체인저는 P2다. 실측은 클로닝(§3)과 같은 모델이라 함께 하면 된다.

**예시 — OpenVoice 음성 변환** (조합: `source_se`를 원본 음성에서 뽑는 줄은 V1 데모 방식에서 유추했다. 출처 https://github.com/myshell-ai/OpenVoice/blob/main/docs/USAGE.md)
```python
from openvoice import se_extractor
from openvoice.api import ToneColorConverter

conv = ToneColorConverter("checkpoints_v2/converter/config.json", device="cpu")
conv.load_ckpt("checkpoints_v2/converter/checkpoint.pth")
src_se, _ = se_extractor.get_se("input_speech.wav", conv, vad=True)   # 바꿀 원본 음성
tgt_se, _ = se_extractor.get_se("target_voice.wav", conv, vad=True)   # 입힐 목소리
conv.convert(audio_src_path="input_speech.wav", src_se=src_se, tgt_se=tgt_se, output_path="changed.wav")
```

**예시 — Chatterbox VC** (조합: `vc.py`의 시그니처만 확인. 출처 https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/vc.py)
```python
import torchaudio as ta
from chatterbox.vc import ChatterboxVC
model = ChatterboxVC.from_pretrained("cpu")
wav = model.generate("input_speech.wav", target_voice_path="target_voice.wav")
ta.save("changed.wav", wav, model.sr)
```

---

## 5. 음원 분리 (보이스 아이솔레이터)

### 5.1 음성 잡음 제거 — 후보 있음
| 후보 | pip | 모델 ID | 코드 라이선스 | 가중치 라이선스 | CPU 근거 | 판정 |
|---|---|---|---|---|---|---|
| **DeepFilterNet** | `deepfilternet` 0.5.6(+`deepfilterlib`. Windows 휠은 **Python 3.8~3.11**) | `DeepFilterNet3`(기본값. 실행할 때 GitHub `models/*.zip`에서 받음) | MIT 또는 Apache-2.0 | 같다. README "All code and model weights in this repository are dual-licensed"(재확인) | 논문 초록: DFN3 "real-time-factor of 0.19 on a single threaded notebook CPU", DFN2 "0.04 on a notebook Core-i5". README: Windows 지원, 사전 빌드 `deep-filter` 바이너리는 48kHz WAV만 | **1순위** |
| noisereduce | `noisereduce` 3.0.3 | 없음(스펙트럼 게이팅 신호처리) | MIT | 해당 없음 | numpy/scipy만 씀. `n_jobs=-1`로 멀티코어 | **2순위**(설치 문제가 생기면 대체. 품질은 낮을 수 있음) |

- 보류: pyrnnoise 0.4.6(래퍼는 Apache-2.0, RNNoise 본체는 BSD-3이지만 번들 모델의 라이선스를 확인 못 함).

**예시 — DeepFilterNet** (원문: README. 출처 https://github.com/Rikorose/DeepFilterNet)
```python
from df.enhance import enhance, init_df, load_audio, save_audio

model, df_state, _ = init_df()                                   # 기본 모델 로드
audio, _ = load_audio("noisy.wav", sr=df_state.sr())             # 48kHz로 읽기
enhanced = enhance(model, df_state, audio)
save_audio("clean.wav", enhanced, df_state.sr())
```
- `load_audio`·`save_audio`는 README의 전체 예제에 있는 함수명을 옮긴 것이다. 실행할 때 import 경로를 확인한다.
- CLI 방식은 `deepFilter noisy.wav --output-dir out`이다.

**예시 — noisereduce** (원문: README. 출처 https://github.com/timsainb/noisereduce)
```python
from scipy.io import wavfile
import noisereduce as nr

rate, data = wavfile.read("noisy.wav")
wavfile.write("clean.wav", rate, nr.reduce_noise(y=data, sr=rate))
```

### 5.2 노래·배경음 분리(스템) — 원칙을 지키는 후보 없음
| 후보 | 제외 사유(원문 근거) |
|---|---|
| Demucs (`demucs` 4.1.0) | 유지 저장소 README: "The license of the weights is not clear: MusDB contains some data that were only usable for research purpose."(재확인). 6스템 모델은 "likely means CC-NC-BY license is applicable" |
| Spleeter (`spleeter` 2.4.2) | 코드는 MIT지만 가중치 라이선스가 명시돼 있지 않다. Python 3.12 미만, tensorflow 2.12 핀 |
| python-audio-separator (`audio-separator` 0.48.0) | 코드는 MIT. UVR 모델은 MIT라는 UVR README 문구가 있지만 모델별 라이선스 표와 학습 데이터 정보가 없다. Roformer 등 제3자 체크포인트는 확인 못 함. Demucs 가중치도 받아 온다 |

- **[대표 결정 2026-11-22]** 스템 분리는 MVP 밖이므로 보류하고, 원칙에 맞는 후보가 나올 때까지 제외한다.

---

## 6. DevOps 실측 요청 항목(제안)

| 기능 | 측정 | 비교 대상 |
|---|---|---|
| STT | 30초·5분 한국어 음성의 처리 시간, 최대 메모리, 대표가 판단한 정확도 | faster-whisper `small`/`medium`/`large-v3`(int8) vs turbo 변환본 vs pywhispercpp `small`/`large-v3-turbo-q5_0` |
| TTS | 한국어 1분 분량(약 350자) 합성 시간, 메모리, 대표 청취 | MeloTTS-Korean vs CosyVoice3 vs Supertonic 3(비교 측정만) |
| 클로닝 | 참조 음성 30초 → 한 문장 합성 시간(목소리 특징 추출 포함/제외), 대표 청취 | OpenVoice V2 vs CosyVoice3 zero-shot |
| 잡음 제거 | 1분 음성 처리 시간 | DeepFilterNet vs noisereduce |

- 기준값은 기획 `01-planning-internal-mvp.md` §4를 따른다(예: TTS는 음성 1분에 1분 이하가 목표이고, 2분 이하면 "기다리는 작업"으로 유지).

## 7. 확인 못 함
- 이 PC의 실제 속도·메모리(전 후보)
- Windows 네이티브 설치 성공 여부: 특히 MeloTTS(mecab·unidic), OpenVoice(옛 버전 핀), DeepFilterNet(Python 3.12 이상)
- 일부 예시 코드의 인자: pywhispercpp 한국어 지정, Chatterbox 참조 음성 인자, CosyVoice 출력 키, OpenVoice `source_se` 경로
- 가중치 학습 데이터의 라이선스(OpenVoice, DeepFilterNet 모두 명시 없음. 원칙은 "가중치 라이선스" 기준이라 통과로 판정함)
- (해결) Supertonic은 비교 측정만 허용, 스템 분리는 보류(대표 결정 2026-11-22)

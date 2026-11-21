# 06 DevOps — 이 PC CPU 음성 엔진 실측 (2단계)

- 작성: 인프라/DevOps팀 · 2026-11-21. 결과가 나오는 대로 단계별로 추가한다.
- 대상 PC: Intel Core Ultra 5 225(10코어 10스레드), RAM 15.5GB, NVIDIA GPU 없음(CUDA 미사용, `CUDA_VISIBLE_DEVICES=""`), Windows 11
- 근거: 지시서 `directives/06-devops.md` 2단계, 후보 `04-backend-cpu-engine-shortlist.md`, QA `05-qa-quality-baseline.md` A7, 기획 `01-planning-internal-mvp.md` §3
- 측정 도구: `06-devops/work/voice-bench/`
  - `bench_run.py`: 자식 프로세스 트리의 최대 RSS와 벽시계 시간을 잰다.
  - `tts_bench.py`, `stt_fw.py`
  - 원자료: `results/bench.jsonl`, 실행 로그 `results/log_*.txt`
  - 한 번에 하나만 실행했다. 실행마다 남은 자식 프로세스가 0개인지 확인했다.
- 용어
  - **RTF** = 처리 시간 ÷ 음성 길이(1보다 작으면 실시간보다 빠름)
  - **첫 음성** = 모델 로드 후 첫 문장 요청부터 오디오가 나올 때까지. 두 엔진 모두 비스트리밍이라 첫 문장 전체 생성 시간과 같다.
  - **최대 RAM** = 프로세스 최대 RSS(모델 로드 포함)

## 1. TTS (L1~L5 + 1분 문단, 스레드 10)

문장: QA A7 L1~L5(`voice-bench/samples/L1-L5.txt`). 5문장 합계가 30초 안팎이라, 1분 기준은 L1~L5를 이어 붙인 381자 문단(`P1min`)으로 따로 쟀다.

| 엔진 | 라이선스 | 로드 | 첫 음성(L1) | L1~L5 RTF (음성 / 처리) | 1분 문단 RTF | **음성 1분 생성 시간** | 최대 RAM | 디스크(모델 + 환경) | 기획 기준(1분 이하) |
|---|---|---|---|---|---|---|---|---|---|
| **MeloTTS-Korean** | MIT / MIT | 11.5초 | 5.2초 | 0.50 (33.0초 / 16.6초) | 0.36 (66.2초 / 24.0초) | **약 22초** | 2.5GB | 모델 198MB + BERT 454MB, 환경 3.3GB | **통과** |
| **Supertonic-3** (음성 F1) | MIT / **OpenRAIL-M(용도 제한)** | 1.6초 | 2.8초 | 0.47 (30.6초 / 14.5초) | 0.31 (59.1초 / 18.2초) | **약 19초** | 0.57GB | 모델 385MB, 환경 0.1GB | **통과** |

- 출력은 16bit PCM WAV, 44.1kHz다. 위치는 `voice-bench/results/melo/`, `voice-bench/results/supertonic/`(L1~L5.wav, P1min.wav)이고, 청취·QA 채점용이다.
- 판정(속도 기준): **두 엔진 모두 "사내 사용 가능"**이다. 품질 판정은 QA 청취와 대표 판단에 맡긴다. Supertonic 채택은 라이선스(용도 제한) 판단 뒤로 미룬다.
- 짧은 문장일수록 RTF가 나빠진다(고정 비용). 첫 음성은 MeloTTS 5.2초, Supertonic 2.8초로 둘 다 실시간 대화용으로는 길다. 스트리밍 미지원이고 문장 전체를 생성한다.
- MeloTTS Windows 설치 특이사항
  - ① librosa 0.9.1 때문에 `setuptools<70`이 필요하다.
  - ② g2pkk가 Windows에서 `eunjeon`을 요구하는데 휠이 없다. 그래서 python-mecab-ko를 `voice-bench/vendor/mecabko`에 따로 두고 연결 모듈(`.venv-melo/.../eunjeon.py`)로 붙였다. site-packages에 바로 넣으면 `mecab` 폴더가 mecab-python3의 `MeCab` 폴더와 겹친다(대소문자를 무시하는 파일시스템).
  - ③ g2pkk는 eunjeon이 없으면 `pip install eunjeon`을 스스로 실행하려 한다. 이번에는 설치되지 않은 것을 전 환경에서 확인했다. 연결 모듈이 이 경로를 막는다.

## 2. STT — 완료 (2026-11-21, 대표 재개 승인 뒤 다시 측정)
faster-whisper 1.2.1, CPU int8, 스레드 10, beam 5, `language="ko"`. FLEURS 한국어 test 앞 60문장(사람 녹음 12.9분, Google FLEURS CC BY 4.0). CER은 숫자 표기를 맞추지 않고 공백·문장부호만 지운 글자 오류율이다. 숫자 표기를 맞춘 정본 CER은 QA가 계산한다.

| 모델 | FLEURS 60 RTF (처리 / 음성) | **1시간 녹음 전사 시간(환산)** | FLEURS CER | 역전사 10개 RTF / CER | 로드 | 첫 구간 평균 | 최대 RAM | 디스크 | 기획 기준(1시간 녹음 30분 이하) |
|---|---|---|---|---|---|---|---|---|---|
| **small** | **0.158** (122초 / 775초) | **약 9.5분** | 5.0% | 0.31 / 5.5% | 1.5~7.1초 | 2.0초 | **0.61GB** | 464MB | **통과** |
| **medium** | 0.400 (310초 / 775초) | 약 24분 | 3.3% | 0.68 / 5.5% | 3.4~5.9초 | 5.2초 | 1.64GB | 1,460MB | **통과** |
| large-v3 | 0.724 (561초 / 775초, 30개씩 둘로 나눠 측정) | 약 43분 | 4.2% | 1.10 / 5.9% | 7.4~9.4초 | 9.0초 | 3.20GB | 2,948MB | **미달(느림)** |

- 판정: **small은 사내 사용 가능**(빠르고 가벼움), **medium도 사내 사용 가능**(가장 정확함, 1시간 녹음 24분). **large-v3는 느림**이다(이 PC에서는 medium보다 덜 정확하고 1.8배 느렸다. 60문장 기준이라 차이는 표본 한계일 수 있음).
- **QA 정본 판정(05 A7-5, 숫자 정규화 CER)**: small 4.99%, medium 3.28%, large-v3 3.98%. 숫자 정확도는 small·medium 19/19. 셋 다 낭독 합격이고, 속도는 1시간 환산이라 조건부다. **권장은 기본 medium, 빠른 초안 small, large-v3 비권장**이다. large-v3는 원문에 없는 문장을 덧붙인 사례가 1건 있었다(환각). 정규화 TTS(L3n·L4n)는 두 엔진 모두 숫자·약어 8/8로 합격이다.
- 짧은 파일(역전사 5~9초)은 RTF가 나쁘게 나온다. 파일마다 드는 고정 비용(언어·VAD·첫 디코딩) 때문이다. 긴 녹음일수록 FLEURS 값에 가까워진다.
- 결과 원문(가공 없음): `voice-bench/results/fw_<모델>_{backtx,fleurs60}/`(.txt, .srt). large-v3 FLEURS는 `fw_large-v3_fleurs60a`, `fw_large-v3_fleurs60b`다.
- 메모리 경위: 첫 측정은 Claude Code가 시스템 메모리 부족(남은 RAM 3.0/15.5GB)으로 강제로 멈췄다. 대표·사용자가 대기 세션 5개를 닫은 뒤(Claude 프로세스 24 → 19, 남은 RAM 4.8~5.5GB) 재개했다. large-v3는 지시대로 남은 RAM이 5GB 이상인 것을 확인하고 돌렸다. 시사점: 이 PC에서 large-v3(3.2GB)와 TTS를 함께 상주시키려면 다른 작업을 줄여야 한다. **small/medium + TTS 조합을 권장**한다(medium 1.6GB + Supertonic 0.6GB 또는 MeloTTS 2.5GB).
- Zeroth 회의 유사 세트는 지시대로 다운로드를 맨 뒤로 미뤘다(491MB 지점에서 멈춤).

### 2.1 QA 요청 — 숫자를 한글로 풀어 쓴 문장(L3n·L4n) 재생성과 역전사
- TTS 출력: `results/melo_norm/`, `results/supertonic_norm/`(16bit WAV). 역전사(small): `results/fw_small_norm/`
- 역전사 원문: 네 개 모두 "…12% 늘어난 1284명입니다.", "…SEO 점수가 72점에서 85점으로…"로 숫자·약어를 정확히 되살렸다. 제 CER 35.6%는 정답을 한글로 풀어 쓴 표기 차이 때문이라 의미가 없다. 정본은 QA 계산을 따른다.
- 속도: MeloTTS 첫 음성 4.8초, RAM 2.4GB / Supertonic 2.4초, 0.6GB

## 1.1 Supertonic-3 음성 스타일 × 말 속도 변형 (QA A7-3·A7-4 미달 뒤 대표 지시, 2026-11-21)
- 사용할 수 있는 스타일: F1~F5, M1~M5(10개, 패키지 `voice_style_names`). 1차 측정은 F1이었다.
- 생성: 스타일 F2·F3·M2 × 속도 0.95·1.05(패키지 기본값) × 7문장(L1~L5 + L3n·L4n), 16bit PCM WAV, 44.1kHz
- 위치: `voice-bench/results/supertonic_var/<스타일>_sp<속도>/`(예: `F2_sp0.95/L1.wav`). 음량 정규화는 하지 않은 원본이다(QA 지적 −25~−26 dBFS. 후처리는 백엔드 담당).
- 속도: RTF 0.456~0.503(스타일·속도에 따른 차이 작음), 로드 0.9초, 최대 RAM 0.53GB, 6조합 42개 합계 126초
- R3 추가(QA 요청, 기본 스타일 F2·0.95 확정 뒤): 정규화 1분 문단 `P1min_norm.wav`(L1·L2·L3n·L4n·L5를 되풀이, 401자)를 `F2_sp0.95/`, `F2_sp1.05/`에 추가했다. 0.95는 음성 60.9초를 18.2초에 생성(RTF 0.30), 1.05는 55.2초를 17.8초에(0.32), 최대 RAM 0.65GB. **음성 1분 생성 약 18초로 기획 기준(1분 이하) 통과**

## 1.2 CosyVoice3(Fun-CosyVoice3-0.5B, Apache-2.0) — 준비 완료, RAM 부족으로 실측 대기
- 설치: `.venv-cosy`(Python 3.10, torch 2.3.1 CPU). requirements.txt에서 학습·웹 UI·GPU용 패키지(deepspeed, tensorrt, gradio, tensorboard 등)는 뺐다. import 확인 완료. 모델 5.05GB(CPU에서 안 쓰는 파일 3개 제외).
- 측정 계획(`cosy_bench.py`): 참조 음성은 **TTS 합성음**(Supertonic F1 L5)만 쓴다. 측정 항목은 로드, 참조 등록(목소리 특징 추출) 시간, 스트리밍 첫 청크, L1~L5 생성 RTF, 최대 RAM이다.
- 대기 사유: 남은 RAM 3.9GB(Claude 프로세스 20개). 모델 파일만 약 4.2GB라 실행에 5GB 이상 필요할 것으로 추정한다. 스왑이 일어나면 속도 수치를 믿을 수 없어 RAM 6GB 이상 남을 때 단독으로 돌린다.

## 3. 클로닝(OpenVoice V2) · 잡음 제거(DeepFilterNet) — 대기

## 부록: 설치 구성 (전역 설치 없음)
| 가상환경 | Python | 용도 |
|---|---|---|
| `.venv` | 3.12.10(시스템) | faster-whisper 1.2.1, 측정 도구. **PyAV는 `av==15.1.0`으로 고정**(최신 19.0.2에서는 `decode_audio`가 `metadata_errors` 인자 오류로 실패함) |
| `.venv-melo` | 3.10.22(uv 휴대용, `voice-bench/pythons`, `--no-bin --no-registry`) | MeloTTS(+OpenVoice 예정), torch 2.2.2 CPU |
| `.venv-supertonic` | 3.12.10 | supertonic 1.3.1(ONNX Runtime) |
| `.venv-df` | 3.11.18(uv 휴대용) | deepfilternet 0.5.6, noisereduce 3.0.3, torch 2.2.2 CPU |

모든 캐시(HF, torch, pip, uv, supertonic)는 `voice-bench/cache/`에 두었다(`env.ps1`). PATH와 레지스트리는 바꾸지 않았다.

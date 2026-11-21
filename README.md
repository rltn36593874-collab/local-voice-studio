# local-voice-studio

한 대의 Windows PC(CPU만 사용)에서 돌아가는 **개인용 로컬 음성 도구**와, 이것을 만든 "AI 에이전트 회사"의 작업 기록 전체입니다.
Claude Code 세션 9개(대표 + 8개 팀 + 법무)가 각자 폴더에서 일하고, `shared/`의 지시서·보고서·현황판으로 소통했습니다.

- 기능: 텍스트 → 음성(TTS), 음성 → 텍스트(STT, 자막 SRT), Claude API로 문장 정규화·요약
- 판매하지 않는 사내(개인) 전용 도구입니다. 음성 모델은 무료 공개 모델을 로컬 CPU로 돌립니다.
- 진행 중인 작업은 [ROADMAP.md](ROADMAP.md)에 있습니다.

## 폴더 구조
| 폴더 | 내용 |
|---|---|
| `00-ceo` ~ `09-legal` | 팀별 세션 폴더. `CLAUDE.md`는 각 세션의 역할 지시, `work/`는 산출물 |
| `03-frontend/work/app` | 웹 화면(Vite) |
| `04-backend/work/server` | 로컬 API 서버(FastAPI), 엔진 워커, 시험(`04-backend/work/tests`) |
| `05-qa/work` | 품질 판정 도구, 블라인드 청취 세트(TTS 음성만 포함) |
| `06-devops/work/voice-bench` | CPU 실측 스크립트와 결과(RTF·RAM·전사 결과), 모델 대장 `MODELS.md` |
| `shared/` | `directives/`(대표 지시서), `reports/`(팀 보고서), `board.md`(현황판), `research/`(조사·설계 문서) |

## 실측 요약 (이 PC: CPU 전용, RAM 16GB)
- TTS: Supertonic-3(F2, 속도 0.95) 음성 1분 생성에 약 18초, RAM 0.6GB / MeloTTS 약 22초, 2.5GB
- STT(faster-whisper int8): 1시간 녹음 전사 small 약 9.5분, medium 약 24분, large-v3 약 43분
- 자세한 표: `shared/research/elevenlabs/06-devops-cpu-bench.md`

## 실행 방법
모델·가상환경·데이터셋은 저장소에 없습니다. 아래 순서로 다시 만듭니다.

1. **벤치 환경**(`06-devops/work/voice-bench`): `. .\env.ps1`로 캐시 경로를 폴더 안으로 지정한 뒤 엔진별 가상환경을 만듭니다(`install_engines.ps1`, 구성은 cpu-bench 문서 부록). 모델은 첫 실행 때 내려받습니다.
2. **백엔드**(`04-backend/work`): `.venv`를 만들고 `pip install -r requirements.txt`를 실행합니다. `server\.env`에 `ANTHROPIC_API_KEY=...`를 직접 쓴 뒤 `.\run.ps1`로 실행합니다(127.0.0.1:8000).
3. **프론트**(`03-frontend/work/app`): `npm install`, `npm run dev`(mock) 또는 `npm run dev:real`(백엔드 연결)

## 공개 범위와 주의
- 이 저장소에는 ElevenLabs의 공개 기능을 분석한 조사 문서(`shared/research/elevenlabs/`)가 들어 있습니다. 2026-11-22부터 ElevenLabs 계정 사용은 중단했습니다(법무 권고). 이 프로젝트는 ElevenLabs와 관계가 없습니다.
- 올리지 않은 것: 비밀값(`.env`), 가상환경, 모델 캐시, 데이터셋 원본(FLEURS·Zeroth), 개인 음성·업로드, 제3자 사진, 사람 녹음 클립. 목록은 `.gitignore`에 있습니다.
- 생성된 음성 wav는 모두 AI 합성음입니다(AI 기본법 표시).

## 라이선스
- 이 저장소의 코드와 문서: [MIT](LICENSE)
- **Third-party** (저장소에 포함하지 않음, 사용자가 따로 받음):

| 구성 요소 | 용도 | 라이선스 | 비고 |
|---|---|---|---|
| faster-whisper / Systran CT2 모델 (small·medium·large-v3) | STT | MIT / MIT | |
| MeloTTS, MeloTTS-Korean | TTS | MIT / MIT | |
| kykim/bert-kor-base | MeloTTS 의존 | 조건부(법무 판정) | 리비전 `1779cc09…` 고정 |
| Supertonic-3 | TTS | 코드 MIT / 가중치 OpenRAIL-M | 용도 제한, 공개물마다 AI 고지 필요. 리비전 `724fb5ab…` |
| Fun-CosyVoice3-0.5B | TTS(비교) | Apache-2.0 | 실측 예정 |
| OpenVoice V2 | 클로닝(예정) | MIT | 의존성 whisper-timestamped는 AGPL(외부 배포 시 재검토) |
| DeepFilterNet | 잡음 제거(예정) | MIT / Apache-2.0 | |
| python-mecab-ko, mecab-ko-dic | 한국어 형태소 | BSD / Apache-2.0 | |
| Google FLEURS (ko) | STT 정확도 측정 | CC BY 4.0 | 전사 결과 텍스트에 문장이 포함됨. 출처: "Google FLEURS (CC BY 4.0)" |
| Zeroth-Korean | STT 측정(예정) | CC BY 4.0 | 출처: "Zeroth-Korean, Zeroth Project / Atlas Labs (CC BY 4.0)" |

법무 판정 원문: `shared/research/elevenlabs/09-legal-review.md`

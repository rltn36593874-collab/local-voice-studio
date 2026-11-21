# 백엔드 개발팀 보고서

## [2026-11-22] 사용자 요청 Claude 시험 4회 · QA 기본 스타일 반영
- **사용자 요청 Claude 시험 4회**(대본·브리핑·요약·번역): 모두 성공. 합계 추정 $0.0010, Haiku 5.5, 1.5~1.9초. 키는 결과에 없다. 결과는 `04-backend/work/tests/live_claude_result_4.json`이다. 오늘 앞서 한 대표 승인 5회($0.0012)와 합치면 9회, 약 $0.0022.
- **QA A7-7 반영**
  - 기본 TTS: Supertonic-3 F2, 속도 0.95(잠정). 스타일·속도는 설정값이다.
  - 음량: QA `prepare()`와 같은 말소리 구간 RMS −20 dBFS, 봉우리 −1 dBFS.
  - 버전 기록: `engine_version`에 스타일·속도까지 남긴다.
  - HF 커밋 리비전도 남긴다(법무 §1-6, QA가 "공개 전 필수 미완"으로 추적하던 항목). 캐시의 `refs/main`과 내려받기 메타데이터에서 읽는다. 예: `Supertone/supertonic-3@724fb5ab…`
  - 실측 확인(같은 날): 실제 Supertonic F2로 결과물을 만들어 outputs·`.ai.json`·생성 로그 세 곳에 `Supertone/supertonic-3@724fb5abbf5502583fb520898d45929e62f02c0b / style F2 / speed 0.95`가 찍히는 것을 확인했다. 첫 확인에서 생성 로그 누락을 발견해 고쳤고, 시험(21건)에 로그 확인을 추가했다. QA에 전달했다. QA가 대조용 결과물(`04-backend/work/samples/rev-check-data/`, out_861c593cbd0e)로 세 곳을 직접 대조했고, 리비전 기록을 **완료로 닫았다**. 같은 wav는 피크 −2.8 dBFS, 클리핑 0이다. 이 폴더는 릴리스 판정 근거라 보존한다. 내 PID 트리만 종료했고, 8001이 비었는지 확인했다.
  - 시험 21건 통과.

## [2026-11-22] 실제 엔진 통합 시험 · TTS 기본 Supertonic · STT 기본 medium — 완료
- **반영**
  - TTS 기본값을 Supertonic-3로 바꿨다(F1 기본, M1 선택). 출력 음량을 −20 dBFS로 맞춘다(QA 요청).
  - STT 기본은 medium이고, `quality=draft`면 small이다. large-v3는 뺐다.
- **통합 시험**: DevOps와 순서를 합의했다. 포트 8001과 별도 데이터 폴더를 썼고, Claude 호출은 없었다.
  - STT medium: L1을 정상 전사했다(한 글자 오인식).
  - Supertonic TTS: 12초 음성을 6.8초에 만들었다. 정규화, 음성 안내, 고지 문구, `_AI` 파일명, Range 재생이 모두 정상이다.
  - small로 다시 받아쓴 내용도 맞다.
  - 끝난 뒤 내 PID 트리만 종료했고, 8001이 비었는지 확인했다.
- **버그 수정**: 워커 stdout이 cp949로 나와 서버 읽기 스레드가 죽던 문제를 고쳤다. 엔진 stderr는 로그 파일로 남긴다.
- **시험**: 21건 통과. 청취용 결과는 `04-backend/work/samples/`. 설계 문서는 §13.

## [2026-11-22] Claude 실제 시험 + 법무 최종 판정 반영 — 완료
- **Claude 실제 시험**(대표 승인): 5회 모두 성공, 합계 추정 $0.0012, Haiku 5.5. 키는 결과·로그에 없다(확인).
  - 문제: 정규화에서 어순이 바뀐 사례가 1건 있었다.
  - 조치: 어순·분량이 바뀌면 Claude 결과를 버리고 로컬 규칙을 쓰는 검사를 넣었다.
  - 결과 파일: `04-backend/work/tests/live_claude_result.json`
- **AI 표시**: 음성 안내 1회(기본 켬, 앞/뒤 선택, 복제는 끌 수 없음). 응답에 `caption_text`(화면 자막)와 `disclosure_text`(설명란)를 넣었고, OpenVoice 워터마크 유지 값을 고정했다.
- **가명처리**: 전사 요약·번역 전에 이름·전화·이메일·주민·계좌번호를 표시로 바꾸고 결과에서 되돌린다(기본 켬). 이름 목록은 `pseudonym_names` 설정으로 등록한다.
- **보관**
  - 샘플·특징값은 분리 폴더에 DPAPI로 암호화하고, 목소리를 지우면 캐시까지 즉시 삭제한다.
  - 낭독 음성은 365일, 동의서·시각·해시는 게시 중 + 내린 뒤 1년, 생성 로그는 365일.
  - 게시 여부를 기록하는 API를 추가했다.
- **시험**: 19건 통과. 설계 문서는 §12.
- **한계·남은 일**
  - 가명처리는 규칙 기반이라 직함 없는 이름은 놓칠 수 있다.
  - 복제 생성 API·OpenVoice 어댑터는 2차 범위다(DevOps 설치와 메모리 여유가 필요).
  - 엔진 통합 시험은 메모리 문제로 보류 중이다.
  - 프론트 세션이 닫혀 있어 새 필드(`caption_text`, `ai_notice`, `pseudonymize`, publication API)는 계약 문서에만 적었다.

## [2026-11-22] TTS 정규화(QA 필수)·AI 고지 문구 — 완료
- **정규화**: TTS 작업 앞단에 Claude 정규화(`prompts/tts_normalize.v1.md`)를 넣고, 그 뒤에 로컬 규칙 안전망(`server/normalize.py`)을 둔다. 규칙은 숫자→한글(쉼표 제거), %→퍼센트, 약어→한글 읽기, 단위 수사다. Claude를 못 쓰면 로컬 규칙만으로 처리한다.
- **기록**: 정규화 전후 문장은 `outputs`(`text`, `text_normalized`, `normalizer`)에 남기고, 비용은 원장 `tts_normalize`에 기록한다.
- **AI 고지**: 결과 응답과 `.ai.json`에 `disclosure_text`를 넣었다. Supertonic·복제 음성이면 `disclosure_required: true`다(법무 판정).
- **시험**: 15건 통과(QA 예시: 1,284명→천이백팔십사 명, 12.5%→십이 점 오 퍼센트, SEO→에스이오, 72점→칠십이 점).
- **로컬 규칙의 한계**: 6월→유월, 10월→시월 같은 굳은 읽기, 날짜 "십일 월" 띄어쓰기, 대소문자가 섞인 상호(YouTube)는 처리하지 못한다. Claude 정규화가 처리하도록 프롬프트에 넣었다.
- **Claude 시험 준비**: 스크립트는 `04-backend/work/tests/live_claude_check.py`다(서버·포트 없이 인프로세스로 돌고, 시험 중 월 한도 $0.01). 대표 승인은 5회에 번역 재시도를 더해 최대 6회. 키가 들어왔다는 대표 연락을 기다린다(`server/.env` 아직 없음).
- **전사 공지 확인**: ElevenLabs 계정 사용과 API 호출을 중단한다. 백엔드는 이번 단계에서 ElevenLabs를 호출한 적이 없다. 로컬 API는 자체 계약으로 설계했다.

## [2026-11-22] 로컬 API 서버 1차 구현 — 코드 완료, 실제 엔진 통합 시험 대기 (마감 11-23 18:00)

모델·effort 검토: 현재 opus/high → 구현·설계에 적정. 서브에이전트는 쓰지 않았다.

**산출물**
- 코드 `04-backend/work/server/`: app(라우트), jobs(대기열 두 줄), engines(어댑터), engine_worker(엔진 프로세스), claude(호출 래퍼), ledger(원장·비용), audio(AI 메타데이터), db
- 프롬프트 `server/prompts/*.v1.md`, 시험 `work/tests/test_server.py`, 실행 `work/run.ps1`, `requirements.txt`
- 설계 문서 갱신: `04-backend-local-api.md` §3(헤더 실측, 보관 필드, `GET /api/consents`, settings), §7.2(is_batch, 단가표 2행, 미등록 모델 차단), §11(구현 현황)

**구현 내용**
- 엔진: DevOps `voice-bench` 가상환경을 하위 프로세스로 재사용한다(DevOps 합의, 읽기·실행만, 캐시는 `env.ps1`과 같음).
  - 1순위: faster-whisper(small, `download_root=HF_HOME/fw`), MeloTTS. Supertonic은 비교용이다.
  - 엔진은 환경변수로 바꾼다. mock 엔진도 둔다.
- Claude: Haiku 5.5, thinking 끔, 고정 시스템 프롬프트에만 캐시를 건다. 키는 `ANTHROPIC_API_KEY` 환경변수에서만 읽고, 엔진 프로세스에는 넘기지 않는다.
- 원장·한도: 응답 usage를 원장에 기록하고, 미등록 모델은 호출 전에 막는다. 한도는 기본 null이고, 입력하면 80% 경고·100% 정지다(대표 결정).
- AI 표시: WAV INFO 청크, 파일명 `_AI`, `.ai.json` 세 곳. ffmpeg가 생기면 MP3도 만든다.
- 보관: 업로드 원본은 30일 뒤 매일 정리한다. 동의 기록·복제 샘플 규칙(대표 정정)은 2차 복제 구현 때 넣는다.
- 보안: 127.0.0.1에만 바인딩, Host·Origin 허용 목록. 프론트 실측값을 반영했다.

**시험**
- mock 엔진 + 가짜 Claude 클라이언트로 10건 모두 통과했다.
- 검증 범위: TTS→기록→Range 재생→다운로드→삭제, 전사→SRT·요약·번역(llm 줄), 키 없음 503, 한도 80/100%, Host/Origin 차단, 비용 assert(07 이식 + Haiku 10만 토큰 경계·배치).
- 실제 uvicorn 부팅도 확인했다.

**사고 보고**
- 22:10쯤 포트 8000의 uvicorn(PID 10808/21388)을 제 시험 서버로 오인해 종료했다. 정황상 다른 세션(프론트로 추정)이 mock으로 띄운 서버였다.
- 03-frontend에 사과하고 확인을 요청했다. 지금 떠 있는 서버(21784/19284, 다른 세션이 실행)는 건드리지 않았다.
- 그 서버의 `work/data`에 제 mock 결과 2건이 남아 있다.
- 03-frontend 확인 결과, 그 서버는 프론트가 run.ps1로 띄운 것이었다(프론트가 다시 띄워 시험을 마쳤고, 지금은 꺼져 있다).
- 같은 때 `work/data` 정리를 시도하다 프론트 서버가 쓰던 `uploads` 폴더까지 지웠다. 그래서 프론트 시험 전사 1건의 원본이 사라졌다(→ `source_expires_at` null). 폴더가 없으면 업로드 때 다시 만들도록 고쳤다.
- 재발 방지: 시험 서버는 `VOICETOOL_PORT=8001`과 별도 데이터 폴더로 띄운다. 끄거나 지우기 전에 부모 프로세스·시작 명령·포트 사용 여부로 내 것인지 확인한다.
- 프론트 통합(mock) 결과: health·voices·usage·jobs·TTS 재생(Range 206)·다운로드·전사·SRT·오류 표시가 정상이다. 지적 3건(작업 `title`, 파일명 `YYYYMMDD-HHMM_종류_제목_AI`, 원본 만료일)을 반영했고, 시험 11건 통과. 시험 데이터 `work/data`는 서버가 꺼진 것을 확인한 뒤 지웠다.

**남은 일 / 막힌 점**
- 실제 엔진 통합 시험: DevOps STT 실측이 끝난 뒤(연락 대기). 참고로 DevOps 첫 TTS 측정은 MeloTTS 로드 11.5초, 1분 음성 약 22초(RTF 0.36), 최대 RAM 2.5GB다.
- 실제 Claude 호출 시험: **대표·사용자 승인이 필요하다**. 키 설정 방법(환경변수)도 정해야 한다.
- 1차에서 뺀 것: 목소리 복제·동의(501), `eta_sec`(null), 업로드 단계 형식 판별.
- ffmpeg LGPL 빌드: DevOps가 준비한다(`06-devops/work/tools/ffmpeg-lgpl/bin/`).

**후속(같은 날)**
- 대표 승인: Claude 시험 호출은 Haiku 5.5로 4회, $0.01 미만. 키가 들어온 뒤에 한다.
- 키 방식: `04-backend/work/server/.env`에 `ANTHROPIC_API_KEY=...`(사용자가 직접 씀). 서버 시작 때 읽고, 셸 환경변수가 우선이다.
- 키 노출 방지: `.gitignore`에 넣었다. 엔진 프로세스에는 넘기지 않는다. SDK 디버그 로그(`ANTHROPIC_LOG`)를 끈다. 출력 지점을 점검했고, 시험 12건 통과.
- 대표에게 파일 경로와 키 이름을 보고했다. 키가 들어오면 mock 엔진 서버(포트 8001)로 4회 실행한다.
- 엔진 통합 시험: DevOps STT 실측이 메모리 부족(남은 RAM 3.0/15.5GB)으로 중단됐다. 대표 확인 전까지 보류한다(DevOps 요청).

## [2026-11-22] 2단계 CPU 엔진 후보 + 3단계 로컬 API 설계 — 완료

모델·effort 검토: 현재 opus/high → 판정·설계에 적정. 라이선스·패키지 수집은 sonnet 서브에이전트 2개(동시 2개)에 맡겼고, HF 라이선스 메타, PyPI 버전·휠, 핵심 라이선스 문장은 백엔드가 원문과 직접 대조했다.

**산출물**
- `shared/research/elevenlabs/04-backend-cpu-engine-shortlist.md` — 5개 기능, pip·모델 ID·예시 코드(DevOps 통보 완료)
- `shared/research/elevenlabs/04-backend-local-api.md` — 로컬 API 설계. 프론트 계약 **합의 완료**

**요약**
1. CPU 1순위: STT faster-whisper(int8), TTS MeloTTS-Korean, 클로닝·보이스 체인저 OpenVoice V2, 잡음 제거 DeepFilterNet. 모두 코드·가중치가 MIT/Apache다.
2. 대표 결정: 스템 분리는 보류(Demucs 가중치 라이선스 불명확), Supertonic(OpenRAIL-M)은 비교 측정만 허용.
3. 로컬 API
   - 127.0.0.1:8000에서 FastAPI와 SQLite로 돈다.
   - 대기열은 두 줄이다: CPU 1개, Claude 번역 1개.
   - 진행 확인은 폴링이고, 작업 상태는 queued → preparing → running → done·failed·canceled다.
   - TTS 결과는 완료 후 파일로 받는다.
4. Claude: Haiku 5.5, thinking 끔, 고정 프롬프트 파일에 캐시, API 키는 환경변수 `ANTHROPIC_API_KEY`에서만 읽는다. usage_ledger·price_book은 데이터팀 §5를 1인용으로 줄였다.
5. AI 표시는 파일명(_AI), ffmpeg 메타데이터, `.ai.json` 세 곳에 넣는다. 동의 기록은 목소리를 지운 뒤 365일이 지나면 자동 삭제한다.

**대표 결정 필요**
- 월 Claude 한도 기본값. 경고 기준을 '잔액'에서 '월 한도'로 바꾼 것(잔액은 관리자 키 없이 읽을 수 없음).
- 업로드 원본 보관 기간(제안 30일).

**확인 대기·위험**
- 이 PC의 실제 속도는 0건 측정이다(DevOps 실측 대기).
- Windows 설치 위험: MeloTTS·OpenVoice 옛 버전 핀, deepfilterlib는 Python 3.11까지. 엔진별 가상환경 분리를 권했다.
- 예시 코드 일부는 "조합" 표시(인자 미확인).
- Host·Origin 실측값(프론트 측정 중).

## [2026-11-21] 방향 전환 통보 수신 — 대기 중
- 대표 통보: 판매하지 않는 사내 전용 도구로 만든다. 음성은 로컬에서 돌리는 자체 모델, LLM은 Claude API를 쓴다. 다중 고객·과금 설계는 보류한다. ElevenLabs API 테스트 호출은 하지 않는다.
- 산출물에서 보류 대상: 4절(크레딧 계량), 7절의 2번(원장), 8.1의 원장·크레딧 예약 단계, 8.3의 과금 쟁점. 8.3 결정 사항(클론 음성은 서버 중계)은 사내 도구에서도 권한 통제용으로 유효하다고 보지만, 다음 지시 때 다시 확인한다.
- 사내 도구에서도 그대로 쓸 수 있는 것: 6절 엔진 후보와 라이선스(F5·Fish 등은 사내 비상업 용도라도 조항을 다시 봐야 함), 6.5 GPU 표, 8.2 업로드 검증·변환, 3절 스트리밍 구조.
- 새 지시가 올 때까지 대기한다.
- 대표 회신(잠정 원칙): 사내 도구라도 NC(비상업)·매출 기준 조항이 있는 모델은 빼고, MIT·Apache 2.0처럼 상업 이용이 명확한 모델만 쓴다. 사용자가 방향을 확정하면 이 원칙으로 엔진 후보를 다시 고르라는 지시가 내려온다. 그때까지 대기한다.

## [2026-11-21] DevOps 문의 회신
- CosyVoice VRAM: 공식 수치가 없다(확인 못 함). 참고값으로 모델 파일 크기(CV2 4.86GB, CV3 9.75GB, 대체 파일 포함)만 `04-backend-api-engine.md` 6.5에 추가했다. 2단계에서 실측이 필요하다.
- 미세조정(PVC급) 소요 시간: CosyVoice 공식 레시피에 시간이 없다(확인 못 함). ElevenLabs 문서는 3~6시간과 6~24시간으로 서로 다르다. 미세조정을 MVP에 넣을지 대표 결정이 필요하다.

## [2026-11-21] 대표 회신 반영
- 보안 제안 채택을 결정 사항으로 문서에 표기했다(`04-backend-api-engine.md` 8.3): 브라우저 직결 스트리밍은 공용 음성만 허용하고, 클론 음성은 반드시 서버 중계로 쓴다. 토큰 발급 API에서 `voice_id`를 확인해 클론 음성이면 403을 돌려준다.
- 테스트 TTS 호출은 대표가 사용자 승인을 받아 지시할 때까지 보류한다(9절에 표기). 추가 작업 없음.

## [2026-11-21] ElevenLabs API·데이터 모델·음성 엔진 분석 (1단계) — 완료

모델·effort 검토: 현재 opus/high → 설계·판정·최종 검수에 적정. 엔진 라이선스·GPU 수치 수집은 sonnet 서브에이전트 1개에 맡겼고, 핵심 수치는 원문과 직접 대조했다.

**산출물**
- 본문: `shared/research/elevenlabs/04-backend-api-engine.md`
- 부록(REST 엔드포인트 206개 전체 표): `shared/research/elevenlabs/04-backend-api-endpoints.md`

**요약**
1. 리소스·엔드포인트 표: OpenAPI 실제 명세는 `openapi/api-reference-2.json`이다(`openapi.json`은 명세를 고르는 안내 페이지). voices·IVC·PVC·TTS·STT·보이스 체인저·더빙·효과음·뮤직·history·models·워크스페이스·API 키·웹훅을 정리했다(1절).
2. 비동기: 동기 바이너리 / 작업 ID + 폴링 / 웹훅 세 가지 패턴과 기능별 상태 enum, 웹훅 서명·재시도(최대 5회, 30초~30분)·자동 비활성화 규칙, 플랜별 동시 처리 한도(2절).
3. 스트리밍: HTTP 스트림 7종, WebSocket 8채널의 메시지 구조(3절). **`/stream` 응답 형식(대표 확인 요청)**: openapi.json의 선언은 `text/event-stream`(SSE)이지만 본문 스키마는 binary이고, 공식 SDK는 원시 바이트(타임스탬프판은 줄마다 JSON)로 읽는다. 그래서 실제로는 원시 바이트일 가능성이 높다. 응답 헤더 실측은 아직이다(3.1).
4. 크레딧: TTS는 글자 × 모델·음성 배율, STT는 오디오 시간(무음 포함), 더빙은 분 × 언어(선결제·환불 규칙 있음). 한 번에 쓸 수 있는 양은 월 할당량의 2배까지(4절).
5. 안전장치 14종: PVC 본인 확인(보이스 캡차), IVC 보호 음성 대조, No-Go Voices, 워터마크·판별 API, 공유 음성 실시간 검열 등(5절).
6. 엔진 후보: TTS·클로닝은 CosyVoice3(Apache-2.0, 한국어, 스트리밍), STT는 Whisper turbo + faster-whisper, 음원 분리는 Demucs. Fish(호스팅 서비스 금지)·Higgs v3·F5 가중치는 상업 서비스에 못 쓰거나 별도 계약이 필요하다(6절). **GPU·처리량 표**(6.5): CosyVoice3는 L20 1장에서 RTF 0.05~0.11, CosyVoice2 첫 청크는 동시 1에서 197ms, 동시 10에서 1,215ms 등. 벤더가 잰 값이라 한국어 자체 벤치가 필요하다.
7. 프론트팀 요청 3건 반영(8절): 스트림 중계(POST로 작업 생성 → 1회용 GET 스트림, `audio/mpeg`로 통일), 업로드 검증(매직 넘버, 실제 디코딩한 길이, 5초·10초~3분, ffmpeg로 MP3 192k 변환, 격리된 워커에서 실행), 일회용 토큰 발급 경로(사용자 인증, 횟수 제한, 잔액 확인).

**막힌 점 / 실행 확인 필요 (대표 판단 요청)**
- 테스트 키로 짧은 TTS 스트림 1회를 호출하면 세 가지가 한 번에 풀린다: `/stream`의 실제 `Content-Type`, 비용 응답 헤더 유무, 중간에 끊었을 때 크레딧 차감 여부. 크레딧이 조금 차감되므로 승인이 필요하다.
- 보안 쟁점: ElevenLabs 일회용 토큰이 특정 음성에 묶이는지 문서에 없다. 묶이지 않으면 브라우저 직결 WebSocket으로 다른 사용자의 클론 음성을 쓸 수 있다. 제안: 직결은 공용 음성만 허용하고 클론 음성은 서버 중계로 쓴다(8.3).
- 문서끼리 다른 점: API 키 만료 상한(문서 30일, 명세 90일).
- 확인 못 함: 기능별 정확한 크레딧 요율(가격 페이지), 웹훅 서명 헤더 형식, CosyVoice VRAM, XTTS-v2 라이선스 전문.

**다른 팀에 필요한 것(요청 사항)**
- 데브옵스(06): 6.5 GPU 표로 비용을 산정해 달라(경로는 별도 메시지로 전달). ffmpeg 빌드 라이선스(LGPL/GPL)와 미디어 처리 격리 워커 검토도 필요하다.
- 데이터(07): 4절 계량 기준을 가격 페이지 요율과 대조해 달라.
- 마케팅(08)·법무: 6.6 라이선스 함정, 음성 샘플 보관(생체 정보) 정책.
- 프론트(03): 8절 계약(`/api/tts`, `/api/tts/{id}/stream`, `/api/realtime/token`, 업로드 `202 + upload_id`) 검토를 부탁한다.

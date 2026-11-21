# 사내 음성 도구 — 웹 화면 구현 계획과 뼈대 (3단계) · 프론트엔드팀

- 작성: 03-frontend · 2026-11-22 · 지시서 `shared/directives/03-frontend.md` 3단계
- 근거:
  - 기획 `01-planning-internal-mvp.md` §3·§5
  - 디자인 `02-design-internal-screens.md`(§2·§5)와 시안 `02-design/work/mockup/`
  - 백엔드 `04-backend-local-api.md` §3
  - 1단계 `03-frontend-client-logic.md` §1
- 산출물: 이 문서 + 뼈대 `03-frontend/work/app/`(실행 확인 완료, §7)
- 상태 요약:
  - API 계약: **합의 완료**(백엔드 문서 §3)
  - 디자인 토큰·시안 CSS: **적용 완료**
  - 백엔드 미구현 구간: mock으로 동작

---

## 1. 스택 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 빌드 | **Vite 8** | 설정 파일 하나에 dev 서버와 프록시를 내장. 로컬 1인 도구라 SSR·서버 라우팅이 필요 없다 |
| UI | **React 19, JavaScript(JSX)** | 녹음·작업 상태 같은 상태 화면이 많아 컴포넌트가 낫다. TS는 빌드 단계만 늘려서 넣지 않았다. 계약 점검은 §4-3으로 대신한다 |
| 라우팅 | **해시 라우팅 직접 구현(약 10줄)** | 화면이 5개라 라우터 라이브러리가 필요 없다 |
| 상태 | React 상태 + Context 1개(사용량·작업 목록 갱신) | 서버 상태가 작고 폴링 주기가 1초로 단순하다 |
| 스타일 | 디자인 시안 CSS를 그대로 복사(`npm run sync-design`) + 작은 보조 CSS | 시안과 같은 클래스 이름을 쓰므로 시안이 바뀌면 다시 복사만 하면 된다 |
| 오디오 | 브라우저 표준 API(`MediaRecorder`, Web Audio `AnalyserNode`·`decodeAudioData`, `<audio>`) | 외부 라이브러리 없음 |
| 테스트 | `node --test`(Node 내장) | 테스트 도구 의존성 없음 |
| 패키지 | npm. 의존성은 `react`, `react-dom`, 개발용 `vite`, `@vitejs/plugin-react` 4개뿐 | 지시: 가장 가벼운 구성 |

- 보안: dev 서버는 `127.0.0.1:5173`에만 바인딩한다. 이 PC 밖에서는 접속할 수 없다.
- 백엔드 프록시: `/api`를 `127.0.0.1:8000`으로 넘긴다.

## 2. 화면과 라우팅 (기획 §5)

| 해시 | 화면 | 들어간 것 | 처리 |
|---|---|---|---|
| `#/tts` | ① 음성 만들기 | 대본(5,000자 표시), ✳ Claude로 다듬기, 음성 선택(기본 + 내 목소리), 속도 0.7~1.3, MP3/WAV, 작업 카드, 결과 카드 | Claude + 로컬 |
| `#/transcribe` | ② 받아쓰기 | 파일 선택, 원본 30일 보관 안내, 작업 카드(진행률 모르면 줄무늬), 타임스탬프 전사문, SRT·TXT, ✳ 요약·회의록, ✳ 번역(언어 선택) → 언어별 SRT | 로컬 + Claude |
| `#/briefing` | ③ 보고서 브리핑 | 붙여넣기 또는 .txt/.md/.pdf, 짧게·보통, ✳ 요약, 요약문 수정, 음성 만들기(①과 같은 컴포넌트, `kind:'briefing'`) | Claude + 로컬 |
| `#/clone` | ④ 목소리 복제 | 4단계 표시(주인 확인 → 동의 낭독 → 샘플 → 이름·저장) 아래 내용 참고, 내 목소리 목록·삭제(삭제 예정일 표시), 보관 안내 | 로컬 |
| `#/history` | ⑤ 기록 | 사용량 카드(금액·토큰·80% 눈금·월 상한(선택)·원장 CSV), 날짜별 결과 카드(재생·AI 배지·설명란 문구 복사·내려받기·삭제) | 없음 |

④ 목소리 복제의 단계 내용:
1. 주인 확인: "다른 사람"을 고르면 이름과 동의서를 받는다.
2. 동의 낭독: 서버가 만든 문장(10분 유효)을 녹음한다.
3. 샘플: 드롭존과 녹음.
4. 이름·저장: 작업 카드로 진행을 보여 준다.

- **공통 셸**(시안 §1):
  - 왼쪽 메뉴: 진행 중 작업 점(●), 하단에 로컬 모델 상태(`/api/health`, 10초 주기)
  - 상단 바: 화면 제목, mock 배지, "작업 n · 대기 m", Claude 미터
  - 작업 서랍: 진행·대기·취소, 최근 끝난 작업과 [보기]
  - 완료 토스트(6초), 사용량 배너
- **화면 전환 시 상태 보존**: 5화면을 모두 띄워 두고 `hidden`으로만 감춘다. 화면을 옮겨도 녹음 중인 내용, 진행 중인 작업, 입력한 글이 사라지지 않는다.

## 3. 컴포넌트와 상태 이름 (디자인 02 §5와 같게)

| 컴포넌트 | 파일 | 상태·규칙 |
|---|---|---|
| 녹음 패널 `rec-panel` | `components/Recorder.jsx` | **S0 대기 → S1 권한 요청**(사전 안내 카드 → 브라우저 팝업) **→ S2 녹음 중 → 정지/자동 정지 → S0**. 실패 시 **S1x**(거부·장치 없음·https 아님, 원인별 문구 + 다시 시도). 아래 S2 세부 참고 |
| 샘플 목록·드롭존 `dropzone` | `components/SampleList.jsx` | 드래그·클릭·녹음으로 추가. 아래 검사 규칙 참고 |
| 작업 카드 `job-card` | `components/JobCard.jsx` | 1초 폴링. 아래 상태별 표시 참고 |
| 결과 카드 `result-card` | `components/ResultCard.jsx` | `<audio>` 재생. 배지 `badge-ai`, `badge-clone`, 누락 시 `badge-warn`. 설명란 문구 복사(1.6초 "복사됨"), 내려받기 |
| 작업 서랍 `drawer`, 토스트 `toast`, 미터 `usage-meter`, 단계 `stepper`, 세그먼트 `seg` | `App.jsx`, 각 화면 | 시안 클래스 그대로 사용 |

S2 녹음 중:
- 타이머는 `aria-live`로 알린다.
- 레벨미터(`<meter>`)와 함께 경고 문구를 띄운다: 너무 큼(피크 > 0.98), 5초 무음, 15초 전 자동 정지 예고.
- 탭을 닫거나 새로고침하면 경고한다(녹음본 손실 방지).
- 형식은 `webm/opus`를 쓰고, 사파리에서는 `mp4`를 쓴다(`pickMimeType`).

샘플 목록·드롭존:
- 파일마다 **실제로 디코딩한 길이**로 검사한다(10MB 이하, 5초 이상). 통과 못 한 파일은 **S5** 오류 행으로 표시한다.
- 합계는 진행 막대로 보여 준다(0:10~3:00). 길이가 모자라거나 넘치면 **S3** 배너를 띄운다.

작업 카드 상태별 표시:
- 상태 순서: `queued` → `preparing` → `running` → `done`/`failed`/`canceled`
- queued: "앞에 n개 작업이 있어요"
- preparing: "모델 불러오는 중"
- running: %와 남은 시간
- `progress:null`이면 줄무늬 바와 경과 시간만 보여 준다.
- `cancel_requested`이면 "취소 중"
- failed이면 원인과 [다시 시도]

- **Claude 사용량 단계**(대표 결정 11-22, 디자인 §2-3): `none`(상한 없음) / `ok` / `warn`(80% 이상) / `over`(100% 이상)
  - 미터: none이면 금액만, 그 밖에는 %와 막대
  - warn: 배너를 하루 1회 띄운다(`localStorage`, 실패해도 동작).
  - over: ✳ 버튼(`.needs-claude`)만 잠기고, 로컬 기능은 그대로 쓸 수 있다.
  - 상한을 비우면 none으로 돌아간다.
- **접근성**:
  - 상태 변화는 `aria-live`, 오류는 `role="alert"`로 알린다.
  - 세그먼트는 `aria-pressed`를 쓴다.
  - 서랍은 닫혀 있을 때 `inert`이고 Esc로 닫는다.
  - 색과 함께 항상 문구를 보여 준다.

## 4. 백엔드 API 계약 (합의 완료 — 원문 `04-backend-local-api.md` §3)

### 4-1. 합의 과정
1. 프론트 초안 발송(11-22)
2. 백엔드 변경·추가 제안: lane, cancel_requested, health, 동의 nonce 10분·1회용, consent_used, kind, download·DELETE, usage CSV·settings, 오류 코드
3. 프론트 조건 3건 → 백엔드 반영 → **합의 완료**
   - ① `preparing` 상태, `progress:null`, `created_at`
   - ② `GET /api/jobs?active=1&recent=5` → `{active, recent}`
   - ③ Host/Origin 허용 목록
4. 프록시 헤더 실측(§7)으로 허용 목록 확정 근거를 보냈다.

### 4-2. 프론트가 쓰는 엔드포인트 (`src/lib/api.js`의 `real`)
| 화면 | 호출 |
|---|---|
| 공통 | `GET /api/health`(10초), `GET /api/jobs?active=1&recent=5`(1초), `GET/DELETE /api/jobs/{id}`(작업 카드 1초), `GET /api/usage` |
| ① | `GET /api/voices`, `POST /api/script/refine`, `POST /api/tts {text, voice_id, speed, format, title?, kind}`, `GET /api/outputs`(결과 찾기) |
| ② | `POST /api/transcribe`(multipart file, language), `GET /api/transcripts/{id}`, `POST .../summary`, `GET .../srt?lang=`, `GET .../txt?lang=`, `POST .../translate {lang}` |
| ③ | `POST /api/summarize`(JSON `{text,length}` 또는 multipart `{file,length}`) → ①의 `/api/tts`(`kind:'briefing'`) |
| ④ | `GET /api/consents/sentence`, `POST /api/consents`(multipart owner·nonce·audio·consent_doc·subject_name), `POST /api/voices/clone`(multipart name·consent_id·files[]), `DELETE /api/voices/{id}` |
| ⑤ | `GET /api/outputs`, `GET /api/outputs/{id}/audio`, `.../download?format=`, `DELETE /api/outputs/{id}`, `GET /api/usage/export.csv`, `PUT /api/settings {limit_usd}` |

- 오류는 `{error:{code,message}}`의 `message`를 그대로 보여 준다.
- 서버에 연결할 수 없으면 "로컬 서버에 연결할 수 없어요…"를 띄운다.

### 4-3. mock 전략
- `src/lib/mock.js`는 계약과 **같은 함수 이름, 같은 응답 모양**이다.
- 기본 실행(`npm run dev`)은 mock이다. `npm run dev:real`에서만 실서버로 바꾼다.
- 개발 중 콘솔 점검: `real`에 있는 함수가 mock에 없으면 경고를 띄운다. 실행 확인 때 경고 0건이었다.
- mock이 흉내 내는 서버 동작:
  - 줄 두 개(cpu, llm)마다 순차 처리
  - preparing 1.2초, 받아쓰기는 progress null
  - 취소 요청은 다음 단계 경계에서 처리
  - nonce 10분 유효·1회용, consent_used, 월 상한 none·80·100
- 텍스트에 '실패'를 넣으면 작업이 실패해 오류 화면을 볼 수 있다.

### 4-4. 백엔드에 추가 요청한 것 (반영 완료 — 백엔드 §3·§11)
1. 월 상한이 없으면 `limit_usd: null`로 응답해 주고, `PUT /api/settings {limit_usd:null}`을 허용해 달라. 50% 단계는 쓰지 않는다.
2. 보관 표시용 필드
   - 결과 원본 삭제일(예: `source_expires_at`)
   - 지운 목소리의 동의 기록 목록(예: `GET /api/consents` → `voice_deleted_at`, `purge_at`)
   - 지금은 화면에 규칙 문구만 보여 준다.

## 5. 디자인 적용
- 토큰 v1과 시안 CSS를 `src/design.css`로 복사해 쓴다. 시안이 바뀌면 `npm run sync-design`을 돌린다.
- 시안과 다르게 만든 부분(shortcut, 코드에 주석 있음):
  1. 결과 플레이어: 원형 재생 버튼 + 파형(`.player .wave`) 대신 기본 `<audio>`를 쓴다. 파형 데이터를 주는 API가 생기면 바꾼다.
  2. 복제 샘플 합계: 진행 링(`.ring`) 대신 막대를 쓴다.
  3. 녹음 레벨: 막대 묶음(`.level i`) 대신 `<meter>`를 쓴다.
  4. ✳ 버튼 옆 예상 비용 칩(`.cost`): 넣지 않았다. 요청 전 비용 추정치를 백엔드에서 받아야 한다.
  5. 기록 화면: 시안의 표(`.hist`)·필터 대신 날짜별 결과 카드를 쓴다.
- 1~3은 시안 컴포넌트를 그대로 옮기면 되는 작업이다. 4~5는 데이터(비용 추정, 필터 조건)가 먼저 필요하다.
- **디자인팀 회신(11-22)**: 1~5 모두 1차는 그대로 진행해도 된다고 했다. 회신에 붙은 조건은 모두 반영하고 mock으로 확인했다.
  - over일 때 ✳ 버튼 앞에 사유 `.why`("이번 달 상한 도달")를 두고 `aria-describedby`로 잇는다.
  - 샘플 합계 막대에 10초 눈금을 두고, 10초 미만이면 경고색을 쓴다.
  - 녹음 경고는 색만이 아니라 글 배지로 보여 준다.
  - 기록 카드에 종류, 시각, 복제 배지, AI 표시 상태, 원본 삭제일을 넣는다.
  - 기록 화면에 '종류' 필터와 '지운 목소리의 동의 기록(삭제 예정일)'을 넣는다.
- 아직 하지 않은 것: AI 표시 누락 시 [다시 기록] 버튼. 이 기능을 할 API가 없어서 백엔드에 요청해야 한다.

## 6. 남은 일 (다음 단계)
1. 백엔드 실서버가 뜨면 `npm run dev:real`로 화면 5개를 실제 데이터로 다시 확인한다. 특히 multipart 필드명과 Range 재생을 본다.
2. §5의 shortcut 1~3을 시안 컴포넌트로 바꾼다.
3. 녹음 실기 확인: 아래 §7 미확인 항목
4. 사파리 녹음 포맷(mp4)은 이 PC에 사파리가 없어서 확인하지 못했다. 대표가 크롬만 쓰면 생략한다.

## 7. 실행 확인 결과 (2026-11-22)
| 항목 | 결과 |
|---|---|
| `npm install` | 의존성 4개, 취약점 0건 |
| `npm test` | 5/5 통과: 파일 검사, 합계 10초~3분 경계, 사용량 단계(none·80·100, 서버 값 우선), 보관 날짜 계산, 시간 표기·녹음 MIME 선택 |
| `npm run build` | 성공(JS 263KB, gzip 83KB / CSS 21KB) |
| dev 서버 + 크롬(mock) | 5화면 모두 렌더링 확인. 아래 흐름 참고 |
| 콘솔 | 오류·경고 0건(계약 점검 경고 없음) |
| 프록시 헤더 실측(echo 서버 :8000, 크롬 fetch) | Host는 항상 `127.0.0.1:8000`(Vite 단축 프록시가 changeOrigin 적용). 같은 출처 GET은 Origin 없음. DELETE는 `Origin: http://127.0.0.1:5173`. 결과를 백엔드에 전달함 |
| 종료 | dev 서버와 echo 서버를 껐고, 5173·8000 리스닝이 없는 것을 확인했다. npx가 띄운 node 하위 프로세스 1개가 남아 PID로 직접 종료했다. 크롬 탭도 닫았다 |

크롬에서 확인한 흐름:
- ① 대본 입력 → ✳ 다듬기 → 음성 만들기 → 작업 카드(처리 중 %·남은 시간) → 메뉴 점·상단 "작업 1 · 대기 0" → 결과 카드(AI 배지) → 완료 토스트
- ④ 단계 표시와 보관 안내
- ⑤ 사용량 카드, 결과 행, 삭제 버튼
- 월 상한 $0.001 → over 배너, ✳ 버튼 잠김, 로컬 음성 만들기는 유지
- 작업 서랍(최근 끝난 작업 + 보기)

### 7-1. 백엔드 1차 서버와 연동 확인 (같은 날, `npm run dev:real` + 백엔드 mock 엔진)

| 항목 | 결과 |
|---|---|
| 읽기 API | health, voices, usage, `jobs?active=1&recent=5` → `{active, recent}`, consents, outputs. 모양이 계약과 일치 |
| ① 브라우저 연동 | TTS 작업 → 결과 카드 → `<audio>` 재생(0:02) → 완료 토스트까지 확인. 상세는 아래 |
| ② 받아쓰기(curl multipart) | `file`·`language` → 작업 → 전사문 → SRT·TXT 정상 |
| 오류 표시 | Claude 키 없음(503 `claude_key_missing`), 복제 미구현(501)이 서버 문구 그대로 화면에 나온다 |
| 콘솔 | 오류 0건 |
| 종료 | 백엔드(uvicorn)와 Vite를 껐다. npx가 남긴 node 하위 프로세스는 PID로 종료. 5173·8000 리스닝 없음, 크롬 탭 닫음 |

① 브라우저 연동 세부:
- `audio` Range 요청에 206 응답
- 내려받기 파일명은 Content-Disposition 값을 쓴다.
- ffmpeg가 아직 없어 결과는 wav만 나온다.

연동에서 찾은 어긋남(백엔드에 전달 → **3건 모두 반영 완료**, 백엔드 시험 11건 통과):
- 1번은 코드 버그가 아니었다. 시험 중 백엔드가 uploads 폴더를 지운 탓이었고, 폴더가 없으면 다시 만들도록 고쳤다.
- 2번: job `title`을 추가했다.
- 3번: 파일명을 `YYYYMMDD-HHMM_종류_제목_AI`(복제는 `_AI-clone`)로 맞췄다.
1. 업로드 직후에도 전사의 `source_expires_at`이 `null`이다(계약은 30일 뒤 날짜).
2. job에 `title`이 없어 작업 서랍과 완료 알림이 "음성 생성 ·"까지만 보인다.
3. 내려받기 파일명이 `YYYYMMDD-HHMMSS_제목_AI`다. 디자인 규칙 `YYYYMMDD-HHMM_종류_제목_AI`와 다르다(종류 빠짐).

테스트 데이터 정리:
- 내가 만든 TTS 결과 1건은 DELETE API로 지웠다.
- 전사 1건은 삭제 API가 없어 백엔드에 정리를 요청했다.

§4-4 요청 2건(limit_usd null, 보관 필드)은 백엔드가 반영했다. `GET /api/consents`도 화면에 연결했다.

**확인 못 함(실기 필요)**:
- 마이크 녹음(S1 권한 팝업 → S2 → 정지): 사용자 브라우저에 마이크 권한 팝업이 떠서 하지 않았다.
- 파일 업로드 흐름(② 받아쓰기, ④ 샘플 드롭): 자동화 도구로 파일을 넣지 않았다.
- 폰 폭(320·390·430) 스크린샷: 이 PC 브라우저 전용 도구라 생략했다. 데스크톱 1568px 폭에서만 확인했다.
- 대표나 QA팀이 직접 녹음과 업로드를 한 번 해 보기를 요청한다.

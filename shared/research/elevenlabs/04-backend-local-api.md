# 사내 음성 도구 — 로컬 API 서버 설계 (3단계, 백엔드팀)

- 작성: 04 백엔드팀 · 2026-11-22 · 마감 2026-11-22 18:00
- 상태: **설계 문서**. 코드는 아직 만들지 않았다. 프론트팀 계약 합의 상태는 §3 머리에 적는다.
- 근거 문서
  - 지시서: `directives/04-backend.md` 3단계
  - 기획 MVP: `01-planning-internal-mvp.md` §1~§5
  - 프론트 계약 초안: 03-frontend-29의 2026-11-22 메시지(`03-frontend-internal-plan.md` §4에 둘 예정)
  - 데이터팀 Claude 원칙·원장: `07-data-claude-credit.md` §4·§5, 계산 스크립트 `07-data/work/claude_credit.py`
  - 엔진 후보: `04-backend-cpu-engine-shortlist.md`
  - ffmpeg 격리: `06-devops-infra.md` §5.5
- Claude API 사실(모델 ID, 캐싱, 사용량 필드, thinking 규칙)은 공식 Python SDK 문서(claude-api 스킬 번들, 2026-11 기준)로 확인했다.

---

## 0. 결정 요약

| 항목 | 결정 |
|---|---|
| 실행 형태 | Python 3.11 + FastAPI + uvicorn 프로세스 하나. **`127.0.0.1:8000`에만 바인딩**한다(외부 네트워크에서는 접근 불가) |
| 저장 | SQLite 파일 하나(`data/app.db`)와 결과 파일 폴더(`data/outputs/YYYY-MM-DD/`). 데이터 폴더 위치는 환경변수 `VOICETOOL_DATA_DIR`로 바꿀 수 있다 |
| 작업 처리 | 대기열 두 줄. **CPU 줄(TTS·전사·복제)은 한 번에 하나**만 돈다. **Claude 줄(번역 등 긴 Claude 작업)도 한 번에 하나**지만 CPU 줄과 따로 돈다. 짧은 Claude 호출(대본 다듬기·요약)은 작업을 만들지 않고 바로 응답한다 |
| 진행 확인 | 1초 간격 폴링(`GET /api/jobs/{id}`). SSE는 나중에 필요하면 붙인다 |
| TTS 결과 | 생성이 끝난 뒤 파일로 받는다. 스트리밍은 하지 않는다(CPU라 실시간보다 느릴 수 있고, 1단계 §8.1 스트리밍 중계는 ElevenLabs 전제였다) |
| Claude | 기본 `claude-haiku-5-5`, thinking 끔, 기능별 고정 시스템 프롬프트에 캐시를 건다. API 키는 **환경변수 `ANTHROPIC_API_KEY`에서만** 읽는다 |
| AI 표시 | 서버가 파일 메타데이터, 파일명, 옆에 두는 JSON 파일 세 곳에 넣는다 |
| 동의 기록 | 목소리가 있는 동안 보관한다. 목소리를 지우면 **삭제일로부터 365일 뒤** 자동 삭제한다(대표 결정) |
| 사용량 | Claude 호출 래퍼 한 곳에서 응답 `usage`를 원장(`usage_ledger`)에 한 줄씩 기록한다. 월 한도의 50·80·100%에서 경고한다 |

---

## 1. 실행 구조

```
브라우저(Vite :5173) ──/api 프록시──▶ 로컬 API 서버 127.0.0.1:8000 (FastAPI)
                                       ├─ 라우터: 요청 검증 → 작업 등록 또는 바로 응답
                                       ├─ CPU 작업자(스레드 1개): TTS / 전사 / 복제 ── 엔진 어댑터(§9)
                                       ├─ Claude 작업자(스레드 1개): 번역 등 긴 Claude 작업
                                       ├─ Claude 호출 래퍼(§4): 모든 Claude 호출이 지나는 한 곳 → usage_ledger 기록
                                       ├─ ffmpeg(별도 프로세스): 형식 변환·길이 측정·메타데이터 기록(§5)
                                       └─ SQLite data/app.db + data/outputs/, data/voices/, data/consents/
```

- **모델 메모리**: 15.5GB RAM에서 TTS·STT·클로닝 모델을 한꺼번에 올리지 않는다. CPU 작업자가 작업 종류에 맞는 모델만 올리고, 다른 종류로 바뀌면 이전 모델을 내린다(같은 종류가 이어지면 그대로 재사용한다). 모델을 올리는 시간이 실측에서 길면, 마지막으로 쓴 모델 하나는 계속 올려 두는 방식으로 바꾼다.
- **재시작**: 서버를 다시 켜면 `preparing`·`running` 상태로 남은 작업을 `failed`(`code: interrupted`)로 바꾸고, `queued` 작업은 그대로 이어서 처리한다(대기열이 DB에 있으므로 유지된다).
- **폴더**
  - `data/outputs/YYYY-MM-DD/` 생성 결과
  - `data/uploads/` 업로드 원본(전사용 녹음, 브리핑용 문서). **30일 뒤 삭제**(대표 승인 2026-11-22). 동의 낭독 녹음과 복제용 샘플은 여기에 두지 않는다. **[대표 정정 2026-11-22]** 동의 낭독 녹음과 동의 기록은 목소리가 있는 동안 보관하고, 목소리를 지우면 365일 뒤 삭제한다(§6). 복제용 샘플은 목소리를 지울 때 **즉시** 함께 삭제한다
  - `data/voices/{voice_id}/` 복제 음성(참조 음성·임베딩)과 샘플
  - `data/consents/{consent_id}/` 동의 낭독 녹음과 동의서
  - `data/prompts/` Claude 기능별 고정 시스템 프롬프트(버전이 붙은 파일, §4)

---

## 2. 작업 대기열

| 필드 | 값 |
|---|---|
| `id` | `job_` + 짧은 무작위 ID |
| `type` | `tts`, `transcribe`, `clone`, `translate` |
| `lane` | `cpu`(tts·transcribe·clone), `llm`(translate) |
| `status` | `queued` → `preparing`(모델 불러오는 중) → `running` → `done` / `failed` / `canceled`. 이미 올라가 있는 모델이면 `preparing`을 건너뛴다 |
| `progress` | 0~1 또는 `null`. 엔진이 진행률을 알려 주거나(전사 구간, 문장 단위 합성) 단계로 셀 수 있으면 그 값을 보내고, 알 수 없으면 `null`을 보낸다(프론트는 줄무늬 바와 경과 시간을 표시) |
| `created_at`, `started_at`, `finished_at` | 경과 시간 표시용 |
| `queue_position` | 같은 줄에서 내 앞에 있는 작업 수(실행 중이면 `null`) |
| `eta_sec` | 같은 엔진의 최근 10건 처리 속도(입력 1초 또는 1글자당 처리 시간)로 추정한다. 기록이 없으면 `null` |
| `cancel_requested` | 실행 중인 작업에 취소를 요청하면 `true` |

- **취소**
  - `queued` 작업은 바로 `canceled`가 된다.
  - `running` 작업은 `cancel_requested=true`로 표시한다. 작업자가 다음 단계 경계(문장 단위 합성, 30초 단위 전사 등)에서 이를 확인하면 멈추고 `canceled`로 바꾼다. 엔진 한 번의 추론 호출은 중간에 끊을 수 없으므로, 화면은 "취소 중"을 보여 줘야 한다.
- **긴 입력 나누기**: TTS는 문장 단위로 나눠 합성한 뒤 이어 붙인다(진행률과 취소 지점이 생긴다). 전사는 엔진이 주는 구간(segment) 단위로 진행률을 갱신한다.
- **실패 코드**: `engine_error`, `out_of_memory`, `interrupted`, `bad_format`, `credit_limit`, `claude_error`, `claude_refusal`.

---

## 3. API 계약

> **합의 상태: 합의 완료(2026-11-22, 03-frontend-29)**. 프론트 초안을 기본으로 하고, 백엔드가 제안한 **[변경]·[추가]** 항목을 프론트가 모두 받았다. 프론트의 추가 요청 3건(status `preparing`, `progress: null`, `created_at` / `recent` 옵션 / Host 허용 목록에 `127.0.0.1:5173`)도 반영했다. 남은 것은 Host·Origin 실측값 확인 한 가지다.

### 3.1 공통
- 기본 주소는 `/api`(프론트 Vite가 `127.0.0.1:8000`으로 프록시). 포트는 8000이다. 인증은 없다(사용자 1명, localhost 전용).
- 오류 형식은 `{error:{code, message}}`다. HTTP 상태와 코드의 대응은 다음과 같다.

  | HTTP | 코드 |
  |---|---|
  | 400 | `bad_format`, `too_short`, `too_long`, `consent_required` |
  | 404 | `not_found` |
  | 413 | `file_too_large` |
  | 402 | `credit_limit` |
  | 409 | `consent_used`, `nonce_expired` |
  | 502 | `claude_error` |
  | 503 | `claude_key_missing` |

- 시각은 ISO 8601이고 서버 로컬 시간대(+09:00)로 쓴다.
- 보안(DNS 리바인딩 방지, §8)
  - **실측(03-frontend, 2026-11-22, Vite 8.3.8)**: 문자열 단축형 프록시는 `changeOrigin`을 자동 적용해 Host가 항상 `127.0.0.1:8000`으로 온다. Origin은 같은 출처 GET에는 없고, DELETE 등에는 `http://127.0.0.1:5173`이 그대로 온다.
  - `Host` 허용: `127.0.0.1:8000`, `localhost:8000`(프록시 경유·직접 접속). `127.0.0.1:5173`, `localhost:5173`도 목록에 남겨 둔다(프록시 설정이 바뀌어도 동작).
  - `Origin`은 있을 때만 검사한다(`http://127.0.0.1:5173`, `http://localhost:5173`, 같은 서버 `:8000`). **Origin이 없는 요청은 허용**한다.

### 3.2 상태
| 메서드·경로 | 응답 |
|---|---|
| **[추가]** `GET /api/health` | `{ok, engines:{tts:{name,loaded}, stt:{...}, clone:{...}}, claude_key_present:bool, ffmpeg:bool}`. 키는 있는지 여부만 알려 주고 값은 절대 내보내지 않는다 |

### 3.3 작업
| 메서드·경로 | 응답 |
|---|---|
| `GET /api/jobs/{id}` | `{id, type, lane, status, progress(0~1 또는 null), queue_position, eta_sec, cancel_requested, created_at, started_at, finished_at, result:{output_id?, voice_id?, transcript_id?, lang?}, error}` |
| `GET /api/jobs?active=1&recent=5` | `{active:[...], recent:[...]}`. `active`는 `queued`·`preparing`·`running` 작업이고, `recent`는 최근 끝난(`done`·`failed`·`canceled`) 작업을 `finished_at` 역순으로 N개(최대 20) 준다. `recent`를 빼면 `active`만 채워 보낸다. 작업 서랍과 "작업이 끝났어요" 알림에 쓴다 |
| `DELETE /api/jobs/{id}` | 202. 대기 중이면 즉시 취소, 실행 중이면 `cancel_requested`(§2) |

### 3.4 ① 음성 만들기
| 메서드·경로 | 요청 → 응답 |
|---|---|
| `GET /api/voices` | `[{id, name, kind:'builtin'|'clone', created_at, engine[추가]}]` |
| `POST /api/script/refine` | `{text, tone?, target_sec?}` → `{text, usage:{input_tokens, output_tokens, cache_read_tokens[추가], est_usd[추가]}}`. Claude 동기 호출 |
| `POST /api/tts` | `{text, voice_id, speed(0.7~1.3), format:'mp3'|'wav', title?}` → 202 `{job_id}`. **합성 전 정규화 필수**(§4.4) |
| (TTS 진행) | 작업 처리 순서: 정규화(Claude) → 문장 단위 합성 → 저장. 완료되면 `result.output_id`. 텍스트 길이 상한은 엔진 실측 후 정한다(가안 5,000자, 넘으면 `too_long`) |

### 3.5 ② 받아쓰기
| 메서드·경로 | 요청 → 응답 |
|---|---|
| `POST /api/transcribe` | multipart `file`, `language?`(기본 `ko`)[추가] → 202 `{job_id}`. 완료되면 `result.transcript_id`. 검증: 형식은 ffprobe로 판별, 파일 크기 상한은 2GB(가안), 길이 1초 이상 |
| `GET /api/transcripts/{id}` | `{id, source_name, duration_sec, language, segments:[{start, end, text}], translations:[언어 코드], source_expires_at}`. `source_expires_at`은 업로드 원본 삭제 예정 시각(30일), 이미 지웠으면 `null` |
| `POST /api/transcripts/{id}/summary` | → `{summary, decisions:[], todos:[], usage[추가]}`. 동기. 전사가 길어 한 번에 넣기 어려우면 서버가 나눠 요약한 뒤 합친다(이때는 응답이 오래 걸릴 수 있다. 실측 후 작업 방식으로 바꿀 수 있음) |
| `GET /api/transcripts/{id}/srt?lang=ko` | `text/plain; charset=utf-8` SRT. **[추가]** `GET /api/transcripts/{id}/txt?lang=` |
| `POST /api/transcripts/{id}/translate` | `{lang}` → 202 `{job_id}`(**llm 줄**). 완료되면 `result.lang`. 이후 `srt?lang=en` 등으로 받는다 |

### 3.6 ③ 보고서 브리핑
| 메서드·경로 | 요청 → 응답 |
|---|---|
| `POST /api/summarize` | JSON `{text, length:'short'|'medium'}` 또는 multipart `{file, length}` → `{summary, usage[추가]}`. 동기. 파일은 `.txt`, `.md`, `.pdf`를 받는다[변경: 형식 명시]. PDF는 Claude의 PDF 입력(document 블록)으로 바로 넘긴다. `.docx`는 1차 범위에서 받지 않는다(붙여넣기로 대신) |
| (음성) | ①의 `POST /api/tts`를 그대로 쓴다. 결과 `kind`는 `briefing`으로 하자고 제안한다 → TTS 요청에 `kind?:'tts'|'briefing'` 추가[추가] |

### 3.7 ④ 목소리 복제
| 메서드·경로 | 요청 → 응답 |
|---|---|
| `GET /api/consents/sentence` | `{sentence, nonce, expires_at[추가]}`. 문장에 날짜·목적·무작위 숫자 4자리가 들어간다. nonce는 **10분 유효, 한 번만** 쓸 수 있다[추가] |
| `POST /api/consents` | multipart `{owner:'self'|'other', nonce, audio, consent_doc?, subject_name?[추가: other일 때 이름]}` → `{consent_id}`. 검증: nonce가 유효한지, 낭독 녹음이 2초 이상인지, `other`면 동의서(pdf·jpg·png, 10MB 이하)가 있는지 |
| `POST /api/voices/clone` | multipart `{name, consent_id, files[]}` → 202 `{job_id}`. 완료되면 `result.voice_id`. 서버 검증은 1단계 §8.2 그대로다: 매직 넘버로 형식 판별, **실제로 디코딩한 길이**로 파일당 10MB 이하·5초 이상, 합계 10초~3분, `consent_id` 필수. 동의 하나로는 목소리 하나만 만들 수 있다(이미 쓴 동의면 `consent_used`)[추가] |
| `GET /api/consents` | `[{id, voice_name, voice_deleted_at, purge_at}]` — 목소리를 지운 동의 기록과 삭제 예정일(프론트 요청 2026-11-22). 1차 구현은 복제 전이라 `[]` |
| `DELETE /api/voices/{id}` | 음성 모델과 샘플 파일을 삭제한다. 동의 기록에 `voice_deleted_at`을 적고, 365일 뒤 자동 삭제한다(§6). 이 음성으로 만든 결과물과 생성 로그는 남는다 |

### 3.8 ⑤ 기록·사용량
| 메서드·경로 | 요청 → 응답 |
|---|---|
| `GET /api/outputs?from=&to=` | `[{id, kind:'tts'|'briefing'|'transcript', title, created_at, duration_sec, voice_id, voice_name[추가], is_clone, ai_label:true, files:{mp3?, wav?}, source_expires_at(TTS는 원본이 없어 null), engine, disclosure_text, disclosure_required, text, text_normalized, normalizer}]`. `disclosure_text`는 설명란에 붙일 AI 고지 문구다. `disclosure_required`가 true면(Supertonic 엔진 또는 복제 음성) 외부에 공개할 때 반드시 붙인다(법무 판정 2026-11-22) |
| `GET /api/outputs/{id}/audio` | `audio/mpeg` 또는 `audio/wav`. Range 요청을 지원한다(`<audio>` 탐색용). Starlette `FileResponse`의 Range 지원 여부를 구현할 때 확인하고, 없으면 직접 처리한다 |
| **[추가]** `GET /api/outputs/{id}/download?format=mp3|wav` | 첨부 파일로 내려받기. 파일명은 §5 규칙을 따른다 |
| **[추가]** `DELETE /api/outputs/{id}` | 결과 파일을 삭제한다. 생성 로그 행은 남기고 `file_deleted_at`을 적는다 |
| `GET /api/usage` | `{month, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, est_usd, limit_usd(없으면 null), warn_level:0|80|100}`. 프론트 표시는 none(한도 없음)/ok/warn(80)/over(100) |
| **[추가]** `GET /api/usage/export.csv?month=` | 월 원장 CSV. 콘솔 사용량과 월 1회 대조하는 데 쓴다(데이터팀 §5-4) |
| `GET /api/settings`, `PUT /api/settings` | `{limit_usd}`(월 한도, USD). 기본값 `null`(대표 결정). `PUT {limit_usd:null}`이면 한도를 지운다 |

### 3.9 프론트 질문에 대한 답
1. 포트 8000, 폴링, 순차 처리 모두 동의한다. 다만 CPU 작업과 Claude 번역은 **줄을 나눠서** 번역이 긴 TTS 뒤에서 기다리지 않게 한다(`lane`).
2. TTS는 **완료 후 파일**로 받는다(프론트 1안 채택).
3. AI 생성 표시는 서버가 파일 메타데이터와 파일명 **둘 다**에 넣는다. 옆에 JSON 파일도 하나 더 둔다(§5).

---

## 4. Claude 호출 (데이터팀 확정 원칙 반영)

### 4.1 원칙
- 모델은 `claude-haiku-5-5`가 기본이다. **thinking은 끈다**(`thinking={"type":"disabled"}` — Haiku 5.5는 effort `high` 이하에서 끌 수 있고 기본 effort가 `medium`이라 그대로 허용된다). 품질 때문에 기능 하나를 Sonnet 5.5(`claude-sonnet-5-5`)로 올리는 것은 대표 결정 사항이다. Sonnet 5.5는 `{type:"disabled"}`를 받지 않으므로(400), 올릴 때는 thinking 설정을 다시 정해야 한다.
- **캐시**: 기능별 고정 시스템 프롬프트(규칙·용어집·예시)를 `data/prompts/{feature}.v{N}.md` 파일로 고정하고, 시스템 블록에 `cache_control`을 건다. 날짜, 요청 ID, 사용자 입력처럼 바뀌는 값은 모두 `messages` 쪽으로 보낸다. 접두가 512토큰보다 짧으면 캐시가 안 되므로, 각 고정 프롬프트는 512토큰 이상으로 만든다. 사내 사용은 띄엄띄엄 일어나서 5분 캐시가 자주 만료된다. 적중률은 원장의 `cache_read_tokens`로 확인한다.
  - 자동 캐시(요청 최상위 `cache_control`)는 쓰지 않는다. 자동 캐시는 마지막 블록, 즉 매번 바뀌는 사용자 입력에 캐시를 써서 쓰기 비용만 늘린다.
- **배치**: Message Batches는 녹음 여러 건을 몰아서 요약·번역할 때만 쓴다(결과가 최대 24시간 뒤에 나옴). 1차 범위에서는 쓰지 않는다.
- **구조화 출력**: 요약의 `{summary, decisions, todos}`와 번역의 구간 배열은 `output_config.format`(JSON 스키마)으로 받는다. `tool_choice` 강제는 쓰지 않는다. Haiku 5.5에서 구조화 출력이 동작하는지는 구현할 때 확인하고, 안 되면 JSON 지시와 파싱 검증으로 대신한다.
- **키 파일 [대표 결정 2026-11-22]**: 사용자가 `04-backend/work/server/.env`에 `ANTHROPIC_API_KEY=...` 한 줄을 직접 쓴다. 서버는 시작할 때 이 파일을 읽어 환경변수로 넣는다(이미 설정된 환경변수가 우선, `ANTHROPIC_API_KEY`와 `VOICETOOL_*`만 받음). 백엔드는 이 파일 내용을 읽거나 출력하지 않는다. `.gitignore`에 넣었다.
- **API 키**: `os.environ["ANTHROPIC_API_KEY"]`로만 읽어 클라이언트에 넘긴다. SDK 기본 생성자는 `ant auth` 프로필도 찾아 쓰기 때문에, "환경변수로만"을 지키려고 키를 명시적으로 넘긴다. 코드·설정 파일·DB·로그·원장 어디에도 키 값을 쓰지 않는다. 키가 없으면 Claude 기능만 `503 claude_key_missing`으로 막고, 음성 기능은 그대로 동작한다.

### 4.2 기능별 설정

| 기능(feature) | API | 입력 | 출력 | max_tokens | 비고 |
|---|---|---|---|---|---|
| `script` | `/api/script/refine` | 원문, 말투, 목표 길이 | 낭독용 대본(숫자·영문·상호를 한글 읽기로 변환) | 4,000 | |
| `stt_summary` | `/api/transcripts/{id}/summary` | 전사 텍스트 | JSON `{summary, decisions[], todos[]}` | 4,000 | 긴 전사는 나눠 요약한 뒤 합친다 |
| `srt_translate` | `/api/transcripts/{id}/translate` | 구간 번호와 텍스트, 목표 언어 | JSON `[{i, text}]` | 16,000 | 한 번에 약 150구간씩. 구간 수가 맞지 않으면 그 묶음만 1회 재시도한다. 타이밍은 서버가 원본에서 그대로 복사한다 |
| `briefing` | `/api/summarize` | 보고서 텍스트 또는 PDF | 사장님께 말하듯 쉬운 요약(소리 내 읽을 문장) | 2,000 | |

### 4.4 TTS 앞단 정규화 (QA 필수, 대표 지시 2026-11-22)
- 규칙: ① 숫자는 한글로 쓰고 천 단위 쉼표는 없앤다(1,284명 → 천이백팔십사 명) ② % → 퍼센트 ③ 영문 대문자 약어는 한글로 읽는다(SEO → 에스이오) ④ 단위에 맞는 수사를 고르고 띄어 쓴다(72점 → 칠십이 점, 3개 → 세 개).
- 처리
  1. Claude 정규화(`tts_normalize.v1`, Haiku)를 먼저 한다.
  2. 결과에 숫자·%·대문자가 남아 있으면 로컬 규칙(`server/normalize.py`)으로 마저 바꾼다.
  3. Claude를 못 쓰면(키 없음·한도·오류·거절) 로컬 규칙만 쓴다. 이 경우 TTS는 막지 않는다.
- 기록: `outputs.text_original`(정규화 전), `text_normalized`(정규화 후), `normalizer`(예: `claude:tts_normalize.v1+local`, `local(claude claude_key_missing)`). 생성 로그에는 원문을 넣지 않고 미리보기와 해시만 남긴다. 비용은 원장에 `feature=tts_normalize`로 기록한다.

### 4.3 호출 래퍼(모든 Claude 호출이 지나는 한 곳)

```python
import os, time, anthropic

# 키는 환경변수에서만 읽는다. 값은 어디에도 쓰지 않는다.
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=2)

def call_claude(feature: str, user_content, job_id: str | None = None, max_tokens: int = 4000):
    guard_monthly_limit()                     # 월 한도 100% 이상이면 CreditLimit 예외 → 402
    system_text, prompt_version = load_prompt(feature)   # data/prompts/{feature}.v{N}.md
    t0 = time.monotonic()
    resp = _client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        system=[{"type": "text", "text": system_text,
                 "cache_control": {"type": "ephemeral"}}],   # 고정 접두만 캐시
        messages=[{"role": "user", "content": user_content}],
    )
    record_usage(feature, job_id, resp, prompt_version,
                 latency_ms=int((time.monotonic() - t0) * 1000))   # 성공·실패 모두 기록
    if resp.stop_reason == "refusal":         # Haiku 5.5는 서버 측 대체 모델이 없다
        raise ClaudeRefusal(resp.stop_details.category if resp.stop_details else None)
    if resp.stop_reason == "max_tokens":
        raise ClaudeTruncated()               # 묶음을 줄여 다시 시도한다
    return "".join(b.text for b in resp.content if b.type == "text")
```

- 오류는 SDK의 구체적인 예외부터 잡는다: `RateLimitError` → 재시도 후 `502 claude_error`, `AuthenticationError` → `503 claude_key_missing` 성격의 안내, `APIConnectionError` → "인터넷 연결 확인". 메시지에는 `e.message`만 남기고, 요청 헤더는 로그에 남기지 않는다.
- SDK 디버그 로그(`ANTHROPIC_LOG`)는 켜지 않는다.

---

## 5. AI 생성 표시 메타데이터

| 위치 | 내용 | 방법 |
|---|---|---|
| 파일명 | `YYYYMMDD-HHMMSS_{제목 슬러그}_AI.mp3`(복제 음성이면 `_AI-clone`) | 서버가 정한다 |
| 파일 메타데이터 | `comment="AI 생성 음성 (사내 도구, 모델: {engine}, 음성: {voice_name}{, 복제})"`, `title`, `artist="AI voice"`, `date` | 저장할 때 ffmpeg 한 번에 처리한다: `-metadata comment=... -metadata artist="AI voice"`. MP3는 ID3, WAV는 INFO 청크로 들어간다. 이미 쓰는 ffmpeg를 쓰므로 태그 라이브러리를 추가하지 않는다 |
| 옆 JSON 파일 | `{파일명}.ai.json`: `{ai_generated:true, generator:"사내 음성 도구", engine, engine_version, voice_id, voice_name, is_clone, consent_id?, created_at, job_id, text_sha256}` | 서버가 기록한다 |
| 설명란 고지 문구 | `disclosure_text`(API 응답과 `.ai.json`). Supertonic·복제 음성은 `disclosure_required: true` → 외부에 공개할 때 반드시 붙인다(법무 판정: 메타데이터만으로는 부족) | 서버가 만들고, 프론트가 [설명란 문구 복사]로 보여 준다 |
| 화면 | 기록 목록의 'AI 생성' 배지, 영상 설명란 안내 문구 복사 버튼 | 프론트 |

- 들리지 않는 워터마크는 P1이다(기획 §2).
- 메타데이터는 편집 프로그램에서 쉽게 지워질 수 있다. 외부 공개 시 표시 의무는 사람이 설명란 문구로 지켜야 한다(화면 안내 문구로 알린다).

---

## 6. 동의 기록과 보관·삭제

**`consents` 테이블**

| 필드 | 설명 |
|---|---|
| `id` | `con_...` |
| `owner_type` | `self` / `other` |
| `subject_name` | 목소리 주인 이름(`other`일 때) |
| `sentence`, `nonce` | 화면에 띄운 문장과 일회용 값. nonce는 10분 안에 한 번만 쓸 수 있다 |
| `audio_path`, `doc_path` | 낭독 녹음과 동의서 파일 |
| `audio_sha256`, `doc_sha256` | 나중에 파일이 바뀌지 않았는지 확인하는 용도 |
| `recorded_at` | 녹음 시각 |
| `voice_id` | 이 동의로 만든 목소리(하나뿐) |
| `voice_deleted_at` | 목소리를 지운 시각 |
| `purge_after` | `voice_deleted_at + 365일` |

**규칙**
1. 복제 작업은 `consent_id`가 없거나, 이미 쓴 동의이거나, `other`인데 동의서가 없으면 시작하지 않는다.
2. 목소리가 있는 동안 동의 기록을 지우는 API는 두지 않는다.
3. `DELETE /api/voices/{id}`를 하면 음성 파일은 바로 지우고, 동의 기록에는 `voice_deleted_at`과 `purge_after`를 적는다.
4. 서버를 켤 때와 그 뒤 24시간마다, `purge_after`가 지난 동의 기록의 파일과 행을 삭제한다. 삭제 사실(동의 ID, 삭제 시각)은 생성 로그에 한 줄 남긴다.
5. 복제 음성으로 만든 결과물의 생성 로그에는 `consent_id`를 남긴다. 동의 기록이 삭제된 뒤에도 "어떤 동의로 만들었는지"를 ID로 추적할 수 있다.

- 동의 낭독과 샘플이 같은 사람인지 자동 대조(성문 비교)는 하지 않는다(기획 §3 결정).

---

## 7. 생성 로그·사용량 원장

### 7.1 `outputs`(결과물)와 `generation_log`(생성 로그)
- `outputs`: `id, kind, title, created_at, duration_sec, voice_id, voice_name, is_clone, consent_id, engine, engine_version, files(json), text_sha256, job_id, file_deleted_at`
- `generation_log`: 행을 추가만 하고 고치지 않는다. 필드는 `ts, event(job_started|job_done|job_failed|voice_created|voice_deleted|consent_purged|output_deleted), job_id, output_id, voice_id, consent_id, detail(json)`.
- 생성 로그에는 텍스트 원문을 넣지 않는다(`text_sha256`과 앞 50자 미리보기만). 원문은 결과물과 함께 `outputs` 쪽에 둔다.

### 7.2 `usage_ledger`(데이터팀 §5-2를 사내 1인용으로 줄임)
| 필드 | 출처 |
|---|---|
| `entry_id`, `ts`(UTC), `request_id`(응답 `id`), `job_id`, `feature`, `engine`(`claude_api`/`local_cpu`), `model_id`, `prompt_version` | 서버 |
| `input_tokens` | `usage.input_tokens` |
| `cache_write_5m_tokens` | `usage.cache_creation.ephemeral_5m_input_tokens` |
| `cache_write_1h_tokens` | `usage.cache_creation.ephemeral_1h_input_tokens` |
| `cache_read_tokens` | `usage.cache_read_input_tokens` |
| `output_tokens` | `usage.output_tokens` |
| `stop_reason`, `status`(`ok`/`failed`/`canceled`), `latency_ms` | 응답·서버 |
| `cpu_seconds`, `audio_in_sec`, `audio_out_sec`, `chars_in` | 로컬 작업 기록(CPU 작업도 한 줄씩 남겨 처리 시간을 쌓는다 → `eta_sec` 추정에도 쓴다) |
| `price_version`, `cost_usd_est` | 아래 단가표로 계산 |

- `is_batch`(bool, 기본 `false`): §4.1이 몰아서 처리할 때 배치를 허용하므로 지금 넣는다. 배치 요청이면 비용에 0.5를 곱한다(데이터팀 요청, 2026-11-22).
- 데이터팀 원장의 `staff_id`, `team`, `project_id`, `claude_key_label`, `inference_geo`, `speed`, `gpu_seconds`, `device_id`는 사용자 1명·GPU 없음·기본 지역·기본 속도라 뺐다.
- `price_book`은 코드 상수가 아니라 DB 테이블로 둔다. 단가가 바뀌면 행을 추가한다. 출처는 데이터팀 §2(공식 가격 문서, 2026-11-21 조회)다.

  | price_version | model_id | 입력 | 캐시 쓰기 5분 | 캐시 쓰기 1시간 | 캐시 읽기 | 출력 | 장문 기준 |
  |---|---|---|---|---|---|---|---|
  | 2026-11-21 | `claude-haiku-5-5` | 0.10 | 0.125 | 0.20 | 0.01 | 0.50 | 100,000토큰 초과 시 장문 단가(입력 0.50, 캐시 쓰기 0.625/1.00, 읽기 0.05, 출력 2.50) |
  | 2026-11-21 | `claude-sonnet-5-5` | 2.00 | 2.50 | 4.00 | 0.10 | 10.00 | 없음 |

  (단위: USD/MTok)
- **price_book에 없는 모델**: 호출 래퍼가 호출 **전에** 막는다(`500 config_error`, "단가표에 없는 모델"). 비용을 계산할 수 없는 호출이 원장과 월 한도를 비켜 가지 않게 하려는 것이다. 모델을 올릴 때는 단가표 행부터 추가한다.
- 비용 식은 데이터팀 §5-2와 같다. Haiku 5.5는 `input + cache_write + cache_read`가 10만 토큰을 넘으면 그 요청 전체에 장문 단가를 쓴다.
- **검산(단위 테스트)**
  1. `07-data/work/claude_credit.py`의 `cost()` assert를 그대로 옮긴다.
  2. Haiku 5.5 일반 케이스를 추가한다.
  3. Haiku 5.5 **10만 토큰 경계** 케이스 두 개를 추가한다: 입력 합계가 정확히 100,000(일반 단가)인 경우와 100,001(장문 단가)인 경우. 데이터팀 `cost()`에는 이 분기가 없으므로 백엔드 테스트가 이 분기를 검증한다.
  4. 배치 케이스(×0.5)를 추가한다.
- **경고 [대표 결정 2026-11-22]**
  - `limit_usd` 기본값은 **비워 둔다**(`null`). 한도가 없으면 경고 없이 사용량만 표시한다(`warn_level: 0`, `limit_usd: null`).
  - 한도를 입력하면 이번 달 `cost_usd_est` 합이 80%를 넘을 때 `warn_level: 80`으로 경고한다. 100%에 닿으면 `warn_level: 100`이 되고, 새 Claude 호출을 `402 credit_limit`으로 막는다(음성 기능은 계속 쓸 수 있다).
  - 50% 단계는 쓰지 않는다. 프론트의 `half` 단계는 쓰이지 않는다.
  - 잔액 대신 사용자가 입력한 월 한도를 기준으로 삼는다. 잔액은 관리자 키 없이 읽을 수 없다(데이터팀 동의).
- **월 1회 대조**: `GET /api/usage/export.csv`로 내려받아 Claude 콘솔 사용량과 비교한다. 5% 넘게 차이 나면 원인을 찾는다.

---

## 8. 보안

- `127.0.0.1`에만 바인딩한다. 방화벽 예외를 만들지 않는다.
- `Host`·`Origin` 헤더 허용 목록을 둔다(§3.1). 다른 사이트가 브라우저를 통해 로컬 서버를 부르는 공격(DNS 리바인딩, CSRF)을 막는다. CORS는 열지 않는다(Vite 프록시가 같은 출처로 만들어 준다).
- 업로드는 1단계 §8.2 검증을 따른다. ffmpeg·ffprobe는 별도 프로세스로 돌리고 시간 제한 30초를 둔다(전사용 긴 파일은 길이 측정만 하고 변환은 길이에 비례해 제한한다). DevOps §5.5의 LGPL 빌드를 쓴다.
- API 키: §4.1. 응답·로그·원장·CSV 어디에도 나가지 않게, 원장 CSV 내보내기는 원장 필드만 내보낸다.
- 파일 경로는 ID로만 찾는다. 요청에 경로를 받지 않으므로 경로 조작(`..`)이 불가능하다.

---

## 9. 엔진 어댑터

엔진은 `04-backend-cpu-engine-shortlist.md`의 1순위로 시작하고, DevOps 실측 결과에 따라 바꾼다. 서버 코드는 아래 세 함수만 부른다.

```python
class TTSEngine:   def synthesize(self, text: str, voice: VoiceRef, speed: float, on_progress) -> Path  # wav
class STTEngine:   def transcribe(self, audio: Path, language: str, on_progress) -> list[Segment]       # start, end, text
class CloneEngine: def create_voice(self, samples: list[Path]) -> VoiceRef                              # 참조 음성/임베딩 저장
```

- 복제 음성으로 합성할 때는 `TTSEngine.synthesize`가 `VoiceRef.kind == 'clone'`이면 클로닝 엔진의 합성 경로를 탄다(OpenVoice라면 MeloTTS 합성 → 음색 변환).
- `engine`과 `engine_version`은 결과물·원장·AI 메타데이터에 함께 남긴다.

---

## 10. 확인 필요 / 대표 결정

| 항목 | 상태 |
|---|---|
| 프론트팀 계약 합의 | 합의 완료. Host·Origin 실측값만 확인 대기 |
| 월 Claude 한도 기본값 | 결정: 비워 둔다. 입력하면 80% 경고, 100% 정지 |
| 업로드 원본 보관 기간 | 결정: 30일. 동의 녹음·복제 샘플은 §6 규칙 |
| TTS 텍스트 상한, 전사 파일 크기 상한, 모델 상주 방식 | DevOps CPU 실측 후 확정 |
| Haiku 5.5 구조화 출력 동작, Starlette Range 지원 | 구현할 때 확인 |
| Claude API 실제 호출 | 구현 단계에서 대표·사용자 승인 후. 이번 설계 단계에서는 호출하지 않았다 |

---

## 11. 구현 현황 (2026-11-22, 1차: TTS·STT·Claude)

- 코드: `04-backend/work/server/`(app·jobs·engines·engine_worker·claude·ledger·audio·db·config, 프롬프트 `server/prompts/*.v1.md`), 시험 `04-backend/work/tests/test_server.py`, 실행 `04-backend/work/run.ps1`.
- 서버 가상환경: `04-backend/work/.venv`(Python 3.12, `requirements.txt` 고정). 엔진은 DevOps `voice-bench` 가상환경을 하위 프로세스로 재사용한다(읽기·실행만, DevOps 합의). 캐시 경로는 `env.ps1`과 같다. 엔진 프로세스에는 API 키를 넘기지 않는다.
- 엔진 교체: `VOICETOOL_TTS_ENGINE=melo|supertonic|mock`, `VOICETOOL_STT_ENGINE=faster_whisper|mock`, `VOICETOOL_STT_MODEL=small|medium|large-v3`. Supertonic은 대표 결정대로 비교용으로만 둔다.
- ffmpeg가 없으면 WAV만 만든다. AI 표시는 WAV INFO 청크와 파일명, `.ai.json`으로 한다. DevOps가 `06-devops/work/tools/ffmpeg-lgpl/bin/`에 두면 MP3도 자동으로 만든다.
- 1차에서 빠진 것: 목소리 복제·동의(`501 not_implemented`), `eta_sec`(항상 null), 업로드 단계의 형식 판별(디코딩 실패는 작업 실패로 돌아온다).
- 시험: mock 엔진과 가짜 Claude 클라이언트로 10건 통과. 비용 assert는 데이터팀 것을 옮기고 장문 경계·배치 케이스를 더했다. 실제 엔진 통합 시험은 DevOps 실측이 끝난 뒤, 실제 Claude 호출은 승인 뒤에 한다.

---

## 12. 법무 최종 판정 반영 (09-legal-review.md, 2026-11-22)

### 12.1 AI 표시 (§2-3)
- **음성 안내**: TTS 요청 `ai_notice`(기본 `true`)와 `ai_notice_position: 'start'|'end'`(기본 `start`).
  - 결과 음성의 앞이나 뒤에 "이 음성은 AI로 생성했습니다."를 1회 넣고, 본문과는 0.5초 쉰다.
  - 복제 음성이면 "이 음성은 AI로 복제한 ○○○의 목소리입니다."를 넣는다. 이때는 끌 수 없다.
- **응답 필드**(outputs·`.ai.json`)
  - `caption_text`: 영상 화면 자막. 예: "이 영상의 음성은 AI로 생성했습니다", 복제면 "AI로 복제한 ○○○의 음성입니다".
  - `disclosure_text`: 설명란 문구.
  - `disclosure_required`: 외부 공개물은 모두 `true`.
  - `ai_notice`: 넣은 위치. 안 넣었으면 `null`.
- OpenVoice wavmark 워터마크는 끄지 않는다(`config.OPENVOICE_WATERMARK = True`). 비가시 워터마크는 보조 수단일 뿐이다.

### 12.2 가명처리 (§5 L4)
- 대상: `POST /api/transcripts/{id}/summary`, `POST /api/transcripts/{id}/translate`. 요청에 `pseudonymize`(기본 `true`)를 받는다.
- Claude로 보내기 전에 아래를 `[이름1]`, `[전화번호1]` 같은 표시로 바꾸고, 결과에서 원래 값으로 되돌린다(`server/pseudonym.py`).
  - 이름: 설정 `pseudonym_names`에 등록한 목록과 "성+이름+직함" 패턴
  - 전화번호, 이메일, 주민등록번호, 계좌번호(숫자 10자리 이상)
- 대응표는 그 요청의 메모리에만 두고 저장하지 않는다. 생성 로그에는 종류별 건수만 남긴다.
- 프롬프트 v2(`stt_summary.v2`, `srt_translate.v2`)에 "표시를 그대로 옮긴다" 규칙을 넣었다.
- 응답 `pseudonymized: {이름: n, ...}`. 설정 API: `GET/PUT /api/settings {pseudonym_names: [...]}`.
- 한계: 직함 없이 이름만 나오면 놓칠 수 있다. 자주 나오는 사람은 이름 목록에 등록한다. 번역 자막에서는 복원된 이름이 한글로 들어간다.

### 12.3 보관·삭제 (§3-3, 대표 결정)
| 대상 | 저장 | 보관 기간 |
|---|---|---|
| 복제 샘플·특징값(`target_se`) | `data/secure_voices/{voice_id}/*.enc`. Windows DPAPI 암호화(이 PC는 Home판이라 EFS를 못 씀. 현재 Windows 계정에 묶여 다른 계정·PC에서는 풀리지 않음) | 목소리를 지우면 즉시 삭제. 엔진 캐시 `data/engine_cache/{voice_id}`와 중간 파일도 함께 지운다 |
| 동의 낭독 음성 | `data/consents/{id}/` | 목소리 삭제 후 365일 |
| 서면 동의서·동의 시각·낭독 해시(텍스트) | `consents` 테이블 + 동의서 파일 | 목소리가 있는 동안, 그리고 그 목소리로 만든 공개 결과물이 게시되어 있는 동안 + 게시를 내린 뒤 1년 |
| 생성 로그(복제 음성 관련) | `generation_log` | 복제 음성 삭제 후 365일(`voice_deleted` 기록은 남김) |
| 업로드 원본 | `data/uploads/` | 30일 |

- 게시 여부는 `PUT /api/outputs/{id}/publication {published: true|false}`로 적는다(`published_at`, `unpublished_at`). 사용자가 회사 채널에 올리거나 내릴 때 표시한다.
- `GET /api/consents` → `[{id, voice_name, voice_deleted_at, purge_at(낭독 음성), audio_purged, record_purge_at(게시 중이면 null)}]`.
- 정리 작업은 서버를 켤 때와 그 뒤 24시간마다 돈다(`retention.purge`).
- 복제 생성 API는 아직 2차 범위(501)다. 보관·삭제 장치와 시험(가상 데이터)은 먼저 넣었다.

### 12.4 Claude 실제 시험 (2026-11-22, 대표 승인)
- 5회 모두 성공(번역 재시도 없음), 합계 추정 $0.0012. 고정 프롬프트 5종이 모두 캐시에 써졌다(512토큰 최소치 충족).
- 정규화에서 어순이 바뀐 사례가 1건 있었다("SEO 점수 72점" → "칠십이 점 에스이오 점수"). 그래서 검사 단계를 넣었다: Claude 결과를 로컬 규칙 결과와 단어 단위로 비교해, 같은 단어가 자리를 옮겼거나 분량이 0.6~1.6배를 벗어나면 버리고 로컬 규칙 결과를 쓴다(`normalize.suspicious`, 생성 로그 `normalize_rejected`).

---

## 13. 엔진 확정·통합 시험 (2026-11-22)
- **TTS 기본값: Supertonic-3**(대표 결정, QA 청취 2.60 > MeloTTS 1.80). 음성은 `supertonic_f1`(기본 여성, QA 최선)과 `supertonic_m1`(기본 남성)이다. 법무 조건부 채택이라 모든 결과물에 `disclosure_required: true`를 붙인다. MeloTTS는 `VOICETOOL_TTS_ENGINE=melo`로 계속 쓸 수 있다.
- **음량 보정**: 결과 WAV의 RMS를 −20 dBFS에 맞추고, 봉우리는 −1 dBFS를 넘지 않게 한다(QA A7-1, Supertonic 출력이 약 8.5dB 작음).
- **STT**: `POST /api/transcribe`에 `quality: 'accurate'|'draft'`를 받는다. 기본 `accurate`는 medium(CER 3.28%, 1시간 녹음에 약 24분), `draft`는 small(4.99%, 9.5분)이다. large-v3는 뺐다(QA A7-5). `GET /api/health`의 `engines.stt.models`로 확인한다. 엔진은 계속 한 번에 하나(모델이 바뀌면 이전 모델을 내림).
- **통합 시험**(8001, 별도 데이터, Claude 호출 없음)
  - ① STT medium: L1 6초 정상(한 글자 오인식).
  - ② Supertonic F1 TTS: 12초 음성을 6.8초에 생성, +6.1dB 보정.
  - ③ small로 다시 받아쓰기: 안내 문장과 본문이 맞다.
  - 엔진 교체 시 이전 엔진 종료, Range 206 확인.
- **고친 버그**: 워커를 `-I`로 실행하면 stdout이 cp949로 나와 서버 읽기 스레드가 죽고 "준비 중"에서 멈췄다. 워커는 fd 1을 복제해 UTF-8로 쓰고 fd 1은 stderr로 돌린다. stdin도 UTF-8로 바꿨다. 서버는 깨진 바이트를 대체 문자로 읽고, 읽기 스레드가 죽으면 오류 이벤트를 남긴다. 엔진 stderr는 `data/logs/engine_*.log`에 남긴다.

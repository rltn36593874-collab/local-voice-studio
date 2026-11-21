# ElevenLabs API·데이터 모델·음성 엔진 분석 (1단계, 백엔드팀)

- 작성: 04 백엔드팀 · 2026-11-21 · 마감 2026-11-22 18:00
- 근거: 공식 명세와 문서만 사용. 2026-11-21에 직접 내려받아 읽은 것만 적었다. 확인 못 한 것은 "확인 못 함"으로 적었다.
  - OpenAPI 3.1: `https://elevenlabs.io/docs/openapi/api-reference-2.json` (377 경로. `openapi.json`은 두 명세를 고르는 안내 페이지이고, `api-reference.json`(172 경로)은 이 명세의 부분집합)
  - AsyncAPI 2.6.0: `https://elevenlabs.io/docs/asyncapi/api-reference-2.json`, `.../asyncapi/api-reference.json`, `.../asyncapi/elevenagents.json`
  - 문서 페이지: 각 절 끝에 URL을 단다(모두 `https://elevenlabs.io/docs/...` 아래 `.md` 판)
  - 공식 Python SDK 소스(스트림 응답 형식 대조용): `github.com/elevenlabs/elevenlabs-python` main
  - 음성 엔진(6절): 각 저장소 LICENSE·README, Hugging Face 모델 카드, 벤더 문서, arXiv. 6절 행마다 URL을 단다
- **2026-11-21 방향 전환**: 사내 전용 도구(판매 안 함), 음성은 로컬 자체 모델, LLM은 Claude API. 다중 고객·과금 관련 내용(4절 계량, 7절 2번, 8.1 원장 단계, 8.3 과금 쟁점)은 보류 상태다. 분석 기록으로만 남긴다.
- 2026-11-21 대표 추가 지시 반영: 프론트팀 요청 3건(8절), `/stream` 응답 형식 판정(3.1), 엔진별 GPU·처리량(6.5)
- 앱 화면: 이번에는 보지 않았다. 앱 관찰은 대표실 메모(`00-ceo-app-notes.md`)를 참고만 했다.
- 금지 사항 준수: API 키를 쓰지 않았고 아무 요청도 실행하지 않았다(생성·클로닝·업로드·설정 변경 0건). 실제 응답으로 확인해야 하는 항목은 "실행 확인 필요"로 표시했다.
- 부록: REST 엔드포인트 전체 표(206개) → `04-backend-api-endpoints.md`

---

## 0. 한눈에 보기

| 항목 | 핵심 |
|---|---|
| 인증 | `xi-api-key` 헤더. 키마다 권한 범위·월 크레딧 한도·IP 허용 목록·만료 시각을 건다. 브라우저용으로는 15분짜리 1회용 토큰을 쓴다(`realtime_scribe`, `batch_scribe`, `tts_websocket`) |
| 리전 | `api.elevenlabs.io`, `api.us.`, `api.eu.residency.`, `api.in.residency.`, `api.sg.residency.` (REST·WebSocket 동일) |
| 처리 방식 4가지 | ① 동기 바이너리 응답(TTS, 효과음, 뮤직, 보이스 체인저, 음원 분리) ② HTTP 스트리밍 ③ WebSocket 양방향 스트리밍(TTS, 대화, 실시간 STT, 실시간 번역) ④ 작업 ID를 받고 폴링하거나 웹훅을 받는 비동기 처리(더빙, 배치 STT, PVC 학습, Studio 변환, Flows 생성, 뮤직 파인튠) |
| 계량 | 단위는 "크레딧"(예전 이름은 characters). TTS는 글자 수 × 모델 배율 × 음성 배율, STT는 오디오 시간(무음 포함), 더빙은 원본 분 × 언어 수, 효과음·뮤직은 길이·변형 개수 기준. 한 번에 쓸 수 있는 양은 월 할당량의 2배까지 |
| 엔진 후보(6절) | TTS·클로닝은 CosyVoice3(Apache-2.0, 한국어, 스트리밍), STT는 Whisper large-v3-turbo + faster-whisper(MIT), 실시간 STT는 상용(Return Zero 등), 음원 분리는 Demucs(가중치 라이선스 확인 필요). Fish·Higgs v3·F5 가중치는 상업 서비스 불가 또는 별도 계약. GPU 수치는 6.5 |
| 안전장치 | PVC는 본인 목소리만 허용하고 보이스 캡차로 확인. IVC는 보호 음성과 겹치면 확인을 요구. 공인 음성 차단(No-Go Voices), 모든 생성물에 워터마크와 판별 API, 생성자 추적, 공유 음성 실시간 검열, 무료 등급 다중 계정 탐지 |

---

## 1. 리소스 모델과 엔드포인트 표

경로는 모두 `https://api.elevenlabs.io` 기준이다. "응답" 열은 명세의 200 응답 형식이다. 전체 목록은 부록에 있다.

### 1.1 음성(voices)·클로닝

| 리소스 | 주요 엔드포인트 | 응답·메모 |
|---|---|---|
| Voice | `GET /v2/voices`(검색·페이지), `GET /v1/voices`, `GET/DELETE /v1/voices/{voice_id}`, `POST /v1/voices/{voice_id}/edit` | `category` enum: `generated`, `cloned`, `premade`, `professional`, `famous`, `high_quality`. 주요 필드: `samples`, `fine_tuning`, `settings`, `sharing`, `verified_languages`, `safety_control`, `voice_verification`, `is_owner`, `permission_on_resource` |
| Voice 설정 | `GET /v1/voices/settings/default`, `GET /v1/voices/{id}/settings`, `POST /v1/voices/{id}/settings/edit` | 안정성·유사성 등 설정값을 음성 단위로 저장하고, 요청마다 덮어쓸 수 있다 |
| 즉시 클로닝(IVC) | `POST /v1/voices/add` (multipart: `name`, `files[]`, `remove_background_noise`, `labels`) | 응답 `voice_id`, `requires_verification`, `library_voice_match`. 학습 없이 바로 쓸 수 있다 |
| 프로페셔널 클로닝(PVC) | `POST /v1/voices/pvc` → `POST .../pvc/{id}/samples` → `POST .../samples/{sid}/separate-speakers` → `GET .../speakers`(상태) → `GET .../pvc/{id}/captcha` → `POST .../captcha`(녹음 제출) → `POST .../pvc/{id}/train` | 단계형 비동기(2절). 수동 확인 요청은 `POST .../verification` |
| 샘플 | `GET /v1/voices/{id}/samples/{sid}/audio`, `DELETE ...`, PVC는 `.../waveform`(파형) | |
| 보이스 디자인 | `POST /v1/text-to-voice/design`(프롬프트 → 미리듣기 여러 개) → `POST /v1/text-to-voice`(골라서 저장), `POST /v1/text-to-voice/{voice_id}/remix`, `GET /v1/text-to-voice/{generated_voice_id}/stream` | 미리듣기 문장은 100~1000자. `eleven_ttv_v3`은 참고 오디오(`reference_audio_base64`)도 받는다 |
| 공유 음성 라이브러리 | `GET /v1/shared-voices`, `POST /v1/voices/add/{public_user_id}/{voice_id}`, `POST /v1/similar-voices` | 공유 상태 enum: `enabled`, `disabled`, `copied`, `copied_disabled`. 심사 상태 enum: `not_requested`, `pending`, `declined`, `declined_resubmittable`, `allowed`, `allowed_with_changes` |
| 컬렉션 | `/v1/voices/collections` CRUD, 음성 추가·제거 | |
| 발음 사전 | `/v1/pronunciation-dictionaries` (파일·규칙으로 생성, 규칙 add/remove/set, 버전별 다운로드) | TTS 요청 하나에 사전을 최대 3개까지 적용(명세) |

### 1.2 생성·변환

| 기능 | 엔드포인트 | 입력 → 출력 |
|---|---|---|
| TTS | `POST /v1/text-to-speech/{voice_id}`, `.../stream`, `.../with-timestamps`, `.../stream/with-timestamps` | JSON(`text`, `model_id`, `voice_settings`, `seed`, `previous_text`/`next_text`, `previous_request_ids`/`next_request_ids`, `pronunciation_dictionary_locators`, `apply_text_normalization`, `audio_effects`) → 오디오 바이너리. 쿼리 `output_format`(`codec_샘플레이트_비트레이트`), `optimize_streaming_latency`, `enable_logging` |
| 대화(여러 화자) | `POST /v1/text-to-dialogue`, `/stream`, `/with-timestamps`, `/stream/with-timestamps` | 화자별 음성·텍스트 배열 → 오디오 |
| 보이스 체인저(STS) | `POST /v1/voice-changer/{voice_id}`, `/stream` | multipart `audio`, `model_id`, `remove_background_noise` → 오디오 |
| STT 배치 | `POST /v1/speech-to-text`, `GET/DELETE /v1/speech-to-text/transcripts/{transcription_id}` | multipart `file` 또는 `source_url`(YouTube·TikTok 등 URL 가능), `diarize`, `num_speakers`(최대 32), `timestamps_granularity`, `keyterms`(최대 1000), `entity_detection`/`entity_redaction`, `webhook`, `webhook_metadata`. 파일은 최대 5GB·15시간 |
| 강제 정렬 | `POST /v1/forced-alignment` | 오디오(1GB 미만)와 텍스트 → 글자·단어 타이밍 |
| 오디오 분리(보이스 아이솔레이터) | `POST /v1/audio-isolation`, `/stream`, 기록 `GET/DELETE /v1/audio-isolation/history` | multipart `audio` → 배경을 지운 음성 |
| 효과음 | `POST /v1/sound-generation` | `text`, `duration_seconds`(0.5~30), `loop`, `prompt_influence` → 오디오 |
| 뮤직 | `POST /v1/music`, `/stream`, `/detailed`, `/detailed/stream`, `POST /v1/music/plan`(구성안 생성), `/video-to-music`, `/upload` | `prompt` 또는 `composition_plan`, `music_length_ms`(3,000~600,000), `force_instrumental`, `finetune_id`, `sign_with_c2pa` |
| 음원 분리(stem) | `POST /v1/music/stem-separation` | `stem_variation_id`: `two_stems_v1`, `six_stems_v1` → 스템별 파일이 든 ZIP |
| 뮤직 파인튠 | `/v1/music/finetunes` CRUD | 상태 enum: `pending`, `in_progress`, `completed`, `failed`, `blocked`. 실패 사유 enum: `audio_processing_failed`, `copyright_violation`, `training_failed` |
| 더빙 | `POST /v1/dubbing`(파일 또는 `source_url`, `target_lang`, `num_speakers`, `watermark`, `disable_voice_cloning`, `use_profanity_filter`), `GET /v1/dubbing/{id}`, `GET .../audio/{lang}`, `GET .../transcripts/{lang}/format/{srt|webvtt|json}` | 응답 `dubbing_id`, `expected_duration_sec`(비동기) |
| 더빙 프로젝트(편집형) | `/v1/dubbing/project` CRUD, 언어 타깃 CRUD, 원문·번역 세그먼트 PATCH, `.../transcript/regenerate` | 프로젝트 상태 `queued`, `preparing`, `processing`, `ready`, `failed`. 언어 상태 `queued`, `processing`, `completed`, `stale`, `failed` |
| Studio(오디오북·팟캐스트) | `/v1/studio/projects` CRUD, `.../convert`, 챕터 CRUD·convert, 스냅샷 목록·스트림·ZIP, `POST /v1/studio/podcasts` | 프로젝트 상태 `creating`, `default`, `converting`, `in_queue`. 챕터 상태 `default`, `converting` |
| Audio Native(웹 임베드 플레이어) | `POST /v1/audio-native`, `.../content`, `.../settings` | 상태 `processing`, `ready` |
| Flows(이미지·비디오·TTS 비동기) | `POST/GET /v1/flows/{image|video|text-to-speech}`, `GET .../{generation_id}`, 템플릿 실행 `/v1/flows/templates/{id}/runs` | 응답 `id`, `status`(`pending`, `generating`, `completed`, `failed`). 실패 사유 enum에 `moderated`, `charging_failed` 등이 있다 |
| 오디오 효과 카탈로그 | `GET /v1/audio-effects/catalog` | TTS의 `audio_effects`에 넣을 ID 목록 |
| 워터마크 판별 | `POST /v1/content-provenance/watermark` | 5절 참고 |

### 1.3 공통 리소스(history·models·사용량)

| 리소스 | 엔드포인트 | 메모 |
|---|---|---|
| History(생성 기록) | `GET /v1/history`, `GET/DELETE /v1/history/{id}`, `GET .../audio`, `POST /v1/history/download`(여러 건 묶음) | 필드: `request_id`, `voice_id`, `model_id`, `text`, `character_count_change_from`/`_to`(이 생성 전후 사용량 = 차감량 근거), `source`(TTS, STS, AN, Projects, Dubbing 등), `settings`, `alignments`, `dialogue`, `output_format`. `enable_logging=false`로 요청하면 기록이 남지 않는다 |
| Models | `GET /v1/models` | `can_do_text_to_speech`, `can_do_voice_conversion`, `can_be_finetuned`, `token_cost_factor`, `model_rates.character_cost_multiplier`, `cost_discount_multiplier`, `maximum_text_length_per_request`, `languages`, `concurrency_group` |
| 사용량 | `POST /v1/workspace/analytics/query/usage-by-product-over-time`, `POST /v1/workspace/analytics/usage`(비용), `POST /v1/workspace/analytics/requests`(API 요청 로그), `GET /v1/usage/character-stats`(폐기 예정) | 지표 enum: `credits`, `tts_characters`, `minutes_used`, `request_count`, `ttfb_avg`, `ttfb_p95`, `fiat_units_spent`, `concurrency`, `concurrency_average`. 분류 기준: voice, user, api_keys, product_type, model, region 등 |
| User·구독 | `GET /v1/user`, `GET /v1/user/subscription` | `character_count`/`character_limit`, `next_character_count_reset_unix`, `max_credit_limit_extension`, `voice_slots_used`/`voice_limit`, `professional_voice_limit`, `can_use_instant_voice_cloning`, `can_use_professional_voice_cloning`, `status`(`trialing`, `active`, `incomplete`, `past_due`, `free`, `free_disabled`) |
| 자산(Assets) | `/v1/assets` CRUD | 업로드 파일 보관 |

### 1.4 워크스페이스·API 키·웹훅

| 리소스 | 엔드포인트 | 메모 |
|---|---|---|
| 멤버 | `GET/POST /v1/workspace/members`, `PUT .../{user_id}/usage-limit` | 좌석 유형 enum: `workspace_admin`, `workspace_member`, `workspace_lite_member`. 멤버별 사용 한도 |
| 초대·그룹 | `/v1/workspace/invites/add`, `/add-bulk`, `DELETE /v1/workspace/invites`, `/v1/workspace/groups`(검색, 멤버 추가·제거) | |
| 리소스 공유 | `GET /v1/workspace/resources/{id}`, `POST .../share`, `.../unshare` | 음성·프로젝트를 사용자·그룹·서비스 계정 단위로 공유 |
| 서비스 계정·API 키 | `POST/GET /v1/service-accounts`, `.../{sa}/api-keys` CRUD, `.../disable`, `POST /v1/workspaces/api-keys/disable`, `.../third-party-disabling` | 키 필드: `permissions`, `character_limit`(월 한도, 넘으면 과금 요청 실패), `allowed_ips`(CIDR), `expires_at_unix`, `third_party_disable_allowed`, 엔터프라이즈 전용 `tts/dubbing/music_concurrency_limit` |
| 1회용 토큰 | `POST /v1/single-use-token/{realtime_scribe|batch_scribe|tts_websocket}` | 15분 뒤 만료, 한 번 쓰면 소멸. 실시간 STT는 `max_session_duration_seconds` 지정 가능 |
| 웹훅 | `/v1/workspace/webhooks` CRUD, `POST .../{id}/test`, `POST .../{id}/deliveries/{did}/redeliver` | 생성 바디 `settings`: `auth_type`(`hmac`만), `name`, `webhook_url`(HTTPS), `request_headers`, `log_redacted_fields` |
| 외부 인증 연결·감사 로그 | `/v1/workspace/auth-connections` CRUD, `GET /v1/workspace/audit-logs` | |

출처: OpenAPI 명세. 인증 `api-reference/authentication.md`, 토큰 `api-reference/tokens/create.md`.

---

## 2. 비동기 작업 처리

### 2.1 패턴별 정리

| 패턴 | 해당 기능 | 시작 응답 | 진행 확인 | 끝 상태 |
|---|---|---|---|---|
| A. 동기(요청 하나에 결과 하나) | TTS, 대화, 효과음, 뮤직, 보이스 체인저, 오디오 분리, 음원 분리, 강제 정렬 | 오디오 바이너리(음원 분리는 ZIP) | 없음 | HTTP 상태 코드 |
| B. 작업 ID + 폴링 | 더빙 | `dubbing_id`, `expected_duration_sec` | `GET /v1/dubbing/{id}`의 `status`, `error` | 목록 필터 enum `queued`, `preparing`, `dubbing`, `dubbed`, `failed` |
| B | 더빙 프로젝트·언어 | 프로젝트 ID | 프로젝트·언어 GET | 위 1.2 enum. 언어의 `stale` = 원문이 바뀌어 다시 생성해야 함(enum 이름으로 본 해석, 문서 설명은 확인 못 함) |
| B | PVC 화자 분리 | — | `GET .../speakers`의 `status`. 공식 예제는 5초 간격 폴링 | `not_started`, `pending`, `completed`, `failed` |
| B | PVC 학습 | `{status}` | `GET /v1/voices/{id}`의 `fine_tuning.state[모델ID]`, `progress[모델ID]`. 공식 예제는 5초 간격 | `not_started`, `queued`, `fine_tuning`, `fine_tuned`, `failed`, `delayed` |
| B | Studio 변환 | — | 프로젝트·챕터 `state` | `converting` → `default` |
| B+C | Flows 이미지·비디오·TTS·템플릿 | `id`, `status` | GET 폴링 또는 `flows_generation`·`flows_template_run` 웹훅 | `completed`, `failed` |
| C. 웹훅 | 배치 STT(`webhook=true`) | 결과 없이 바로 `message`, `request_id`, `transcription_id` 반환 | 웹훅 `speech_to_text_transcription` / 실패 시 `webhook_error`. 전송이 끝내 실패하면 `GET /v1/speech-to-text/transcripts/{transcription_id}`로 직접 받는다 | — |
| C | 공유 음성 제거 알림 | — | 웹훅 `voice_removal_notice`, `voice_removal_notice_withdrawn`, `voice_removed` | — |

### 2.2 웹훅 전달 규칙(문서 기준)

- 봉투: `{type, event_timestamp, data}`. Flows 웹훅의 `data`는 해당 GET 엔드포인트의 최종 응답과 같은 모양이라, 폴링 처리 코드를 그대로 쓸 수 있다.
- 서명: `ElevenLabs-Signature` 헤더에 HMAC 서명. SDK의 `constructEvent`(JS) / `construct_event`(Python)가 서명 검증, 타임스탬프 검증, JSON 파싱을 한 번에 한다. 헤더 안의 정확한 형식(타임스탬프 필드 이름, 해시 알고리즘, 허용 시간 차)은 문서에 없어 확인 못 함.
- 재시도: 웹훅마다 켜고 끈다(기본은 꺼짐). 최대 5회, 간격은 즉시 → 30초 → 2분 → 8분 → 30분, 간격의 최대 10%를 무작위로 더한다. 재시도 대상은 `5xx`, `429`, `408`, 연결 오류·시간 초과뿐이고, 나머지 `4xx`는 재시도하지 않는다.
- 한도: 웹훅 하나에 대기 중인 재시도는 100건까지, 넘치면 버린다. 오디오 페이로드가 50MiB를 넘으면 한 번만 보내고, 웹훅당 오디오 재시도 합계는 400MiB까지. 이벤트 하나에 웹훅은 최대 10개(`too_many_webhooks`).
- 자동 비활성화: 연속 10회 이상 실패하고, 마지막 성공이 7일보다 오래됐거나 성공한 적이 없으면 꺼지고 관리자에게 메일이 간다. 다시 켜는 것은 수동이다.
- 재시도 페이로드가 원본과 똑같으므로, 받는 쪽은 같은 이벤트를 여러 번 받아도 결과가 같게(멱등) 처리해야 한다.
- STT 웹훅은 기본 1회 전송. `enable_logging=false`(무보관) 요청은 재시도를 켜도 5초·30초 두 번만 재시도하고, 전사 결과는 저장하지 않는다.
- 받을 웹훅이 하나도 없는데 Flows 생성을 웹훅 전달로 요청하면 요청 자체를 거절한다(결과를 받을 곳 없이 생성되는 일을 막음).

출처: `eleven-api/resources/webhooks.md`, `eleven-api/guides/how-to/speech-to-text/batch/webhooks.md`, `eleven-api/guides/how-to/image-and-video/webhooks.md`, `eleven-api/guides/how-to/voices/professional-voice-cloning.md`, OpenAPI enum.

### 2.3 동시 처리 한도(큐잉)

- 플랜별 동시 요청 한도(`overview/models.md` 표). 예: Free는 Multilingual v2 2개 / Flash 4개 / STT 8개 / 실시간 STT 6개 / 뮤직 0개 / 효과음 4개, Pro는 10/20/40/30/2/6, Scale·Business는 15/30/60/45/5/8. 엔터프라이즈는 "Elevated". 우선순위 등급은 3~6.
- 한도를 넘은 요청은 큐에 들어가 우선순위가 낮은 요청과 함께 처리된다. 응답 헤더 `current-concurrent-requests`, `maximum-concurrent-requests`로 현재 상태를 보여 준다.
- HTTP는 요청 하나가 한 칸을 쓴다. TTS WebSocket은 실제로 오디오를 생성하는 시간만 한도에 잡힌다. 대화(TTD) WebSocket은 연결해 있는 동안 별도 풀에서 세션 하나를 계속 차지한다.
- STT는 8분이 넘는 파일을 내부에서 최대 4조각으로 나눠 병렬 처리한다: 동시 처리 수 = min(4, 올림(오디오 초 / 480)).
- 출처: `overview/models.md` "Concurrency and priority", `overview/capabilities/speech-to-text.md`.

---

## 3. 스트리밍 프로토콜

### 3.1 HTTP 스트리밍

- 대상: `/v1/text-to-speech/{id}/stream`, `/stream/with-timestamps`, `/v1/voice-changer/{id}/stream`, `/v1/audio-isolation/stream`, `/v1/text-to-dialogue/stream`, `/v1/music/stream`, `/v1/music/detailed/stream`.
- **응답 형식 판정(대표 확인 요청 건)** — 근거 4가지를 대조했다.

  | 근거 | `/stream` | `/stream/with-timestamps` |
  |---|---|---|
  | OpenAPI(`openapi/api-reference-2.json`) | 미디어 타입 `text/event-stream`, 스키마 `{type: string, format: binary}` | 미디어 타입 `text/event-stream`, 스키마 `StreamingAudioChunkWithTimestampsResponseModel{audio_base64, alignment, normalized_alignment}` |
  | 문서 `api-reference/streaming.md` | "raw audio bytes (e.g., MP3 data) … chunked transfer encoding" | — |
  | 문서 `concepts/audio-streaming.md`, `best-practices/latency-optimization.md` | "server-sent events" | — |
  | 공식 Python SDK 소스(`elevenlabs-python` main, 커밋 `2268b13c9ed9`, `src/elevenlabs/text_to_speech/raw_client.py`) | `_response.iter_bytes()`로 받은 바이트를 그대로 넘긴다. SSE 파싱 없음 | `_response.iter_lines()`의 각 줄에 바로 `json.loads()`. `data:` 접두어를 떼는 코드가 없다(파싱에 실패한 줄은 조용히 버림) |

  - **openapi.json 기준 결론**: 명세가 선언한 미디어 타입은 **`text/event-stream`(SSE)** 이다. 다만 `/stream` 본문 스키마는 SSE 이벤트가 아니라 **오디오 바이너리**이고, SSE 이벤트 구조(`event:`/`data:` 필드)는 명세 어디에도 정의돼 있지 않다. 그러니 openapi.json만으로는 "실제 바이트가 SSE 프레임이다"라고 확정할 수 없다. 명세에는 "바이너리 오디오를 스트리밍한다"는 것만 정의돼 있다.
  - **SDK로 본 실제 동작(추론)**: 공식 SDK는 `/stream`을 원시 오디오 바이트로, `with-timestamps`를 줄마다 JSON 하나가 오는 형식(NDJSON)으로 읽는다. 실제 응답이 SSE 프레임이라면 SDK의 `json.loads`가 모든 줄에서 실패해 타임스탬프 스트림이 비어 버린다. 그래서 실제 본문은 **SSE 프레임이 아니라 chunked 원시 바이트(타임스탬프판은 NDJSON)일 가능성이 높다**. 응답 `Content-Type` 헤더 값은 아직 실측하지 않았다 → **실행 확인 필요**(짧은 TTS 1회).
  - **설계 영향 없음**: 8.1의 중계 서버가 어느 쪽이든 흡수해서 브라우저에는 항상 `audio/mpeg` 원시 바이트만 준다.
- 문서가 말하는 지연 구성: 네트워크 왕복(공용 인터넷에서 20~200ms) + 서버 처리(한 자릿수 ms) + 모델 추론 + 플레이어 버퍼(500ms가 흔함). 공개된 모델 지연 수치는 네트워크를 뺀 서버 쪽 중앙값이다. 예: Eleven v4 Turbo·Flash v2.5 약 100ms, v3 Conversational 약 165ms, Flash v2 약 135ms.
- 글 전체가 미리 있으면 HTTP 스트리밍이 낫고, LLM처럼 글이 조금씩 생기면 WebSocket이 낫다고 문서가 권한다.

### 3.2 WebSocket 채널(AsyncAPI)

| 채널 | 방향·인증 | 클라이언트 → 서버 | 서버 → 클라이언트 |
|---|---|---|---|
| `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input` | 쿼리: `model_id`, `language_code`, `output_format`, `inactivity_timeout`(기본 20초), `auto_mode`(기본 false), `sync_alignment`, `apply_text_normalization`, `seed`, `enable_ssml_parsing`, `enable_logging`, 인증 `authorization` 또는 `single_use_token` | ① 초기화 `{text:" ", voice_settings, generation_config, pronunciation_dictionary_locators, xi-api-key}`(공백 한 칸 필수, 설정은 첫 메시지에서만) ② 텍스트 `{text:"... ", try_trigger_generation, flush}`(텍스트는 공백으로 끝나야 함) ③ 종료 `{text:""}` | `{audio(base64, 기본 MP3), alignment, normalizedAlignment}` 반복, 끝에 `{isFinal:true}` |
| `.../multi-stream-input` | 위와 같음 | 모든 메시지에 `context_id`. 컨텍스트 초기화, `SendTextMulti`, `flush`, `close_context`, `close_socket`, keep-alive(`text:""`) | `{audio, alignment, contextId}`, `{isFinal, contextId}` |
| `.../v1/text-to-dialogue/stream-input` | `model_id`는 `eleven_v3*` 또는 `eleven_v4*`(기본 `eleven_v3_conversational`) | 첫 메시지에 `voices`(v3는 최대 10개, v3_conversational·v4는 1개) → `inputs:[{text, voice_id, new_turn}]`, `flush`, `close_socket`, `keep_alive` | 오디오 청크와 정렬, `is_final_audio_for_turn`, `is_final`, 오류 `{message, error, code, param}` |
| `.../v1/text-to-dialogue/multi-stream-input` | 위와 같음 | `context_id` 필수, 동시 컨텍스트 최대 5개 | 위와 같음 + `context_id` |
| `.../v1/speech-to-text/realtime` | 쿼리: `model_id`, `token`, `audio_format`, `language_code`, `secondary_languages`, `commit_strategy`(기본 `manual`, 그 밖에 VAD·턴 예측), `vad_*`, `include_timestamps`, `diarize`, `keyterms`, `entity_detection`/`entity_redaction`, `keepalive_interval_ms`, `enable_logging` | `{message_type:"input_audio_chunk", audio_base_64, commit, sample_rate, previous_text}` | `session_started`, `partial_transcript`(중간 결과), `committed_transcript`(구간 확정), `committed_transcript_with_timestamps`, `diarized_transcript`, `speakers_merged`, `committed_transcript_entities`, `redacted_transcript`, 경고 `warning`, 오류 `auth_error`, `quota_exceeded`, `rate_limited`, `commit_throttled`, `queue_overflow`, `resource_exhausted`, `session_time_limit_exceeded`, `chunk_size_exceeded`, `insufficient_audio_activity`, `unaccepted_terms`, `input_error`, `invalid_request`, `transcriber_error` |
| `.../v1/translation/realtime` (엔터프라이즈 전용) | 쿼리: `target_language`, `source_language`, `voice_id`, `input_format`, `output_format`, `tts_model_id`, `eagerness` | `input_audio_chunk`, `end_of_stream` | `session_started`, `status`, `partial_transcript`, `final_transcript`, `translation`, `audio{data, sample_rate}`, 오류 여러 종(`payment_issue`, `quota_exceeded` 포함) |
| `/speech-engine/upstream` (방향이 반대) | ElevenLabs가 클라이언트가 되어 **우리 서버**(`wsUrl`)에 접속한다 | (ElevenLabs → 우리) `init{conversation_id}`, `user_transcript`, `ping`, `close`, `error` | (우리 → ElevenLabs) `agent_response{content, is_final}`, `pong` |
| `.../v1/convai/conversation?agent_id=` (에이전트, 범위 밖이라 요약만) | | `user_audio_chunk`, `user_message`, `contextual_update`, `client_tool_result`, `pong` 등 | `audio`, `user_transcript`, `agent_response`, `interruption`, `vad_score`, `client_tool_call`, `guardrail_triggered`, `ping` 등 |

- AsyncAPI 파일에서는 `subscribe`가 클라이언트 → 서버 메시지이고 `publish`가 서버 → 클라이언트 메시지다(파일 설명문 기준, 보통 쓰는 뜻과 반대).
- 대화 WebSocket은 텍스트가 대략 40자·8단어 이상 쌓여야 오디오를 내보내고, 20초 동안 아무것도 받지 못하면 연결을 닫는다(`keep_alive`로 시간을 되돌린다).
- 출처: AsyncAPI 3종, `concepts/audio-streaming.md`, `concepts/latency.md`, `overview/models.md`.

---

## 4. 크레딧 계량

| 대상 | 차감 기준(문서) | 근거 |
|---|---|---|
| 공통 | "크레딧"(예전 이름 characters, 값은 같음). 플랜, 웹/API 구분, 제품, 모델에 따라 소모량이 다르다. 매달 초기화되고, 최대 2개월분까지 이월된다. PAYG 크레딧은 달러 값으로 저장했다가 현재 플랜 요율로 환산하며 12개월간 유효하다 | `help-center/account/general/what-are-credits.md`, `.../what-happens-when-i-run-out-of-credits.md` |
| TTS | 글자 수 기준. 웹에서 v3는 글자당 1크레딧, API는 할인(정확한 요율은 가격 페이지, 확인 못 함). 모델별 배율 필드 `token_cost_factor`, `model_rates.character_cost_multiplier`, `cost_discount_multiplier`가 있다. 공유 음성에 "사용자 지정 요율"이 걸려 있으면 음성별 크레딧 배율이 추가된다(예전 기능, 새로 공유하는 음성에는 없음) | `.../how-much-does-it-cost-to-generate-using-eleven-v3-alpha.md`, `.../what-are-custom-rates-and-credit-multipliers.md`, `GET /v1/models` 스키마 |
| 보이스 디자인 | 생성 한 번에 후보 3개, 미리듣기 문장의 글자 수만큼 과금 | `.../how-much-does-voice-design-cost.md` |
| Studio | 같은 텍스트·음성·설정이면 다시 생성하기 2회까지 무료 | `.../does-it-cost-credits-to-regenerate-in-studio.md` |
| STT | 오디오 시간(시간 단위 요율). 무음도 포함하고 무음 할인은 없다. 배치와 실시간 모두 보낸 오디오를 초 단위로 계량 | `overview/capabilities/speech-to-text.md` |
| 더빙 | 원본 길이(분) × 더빙 언어 수, 요율은 더빙 모델마다 다르다. API 프로젝트는 만들 때 1개 언어분을 먼저 받는다. 준비에 실패하면 환불, 추가 언어가 실패하면 그 언어분 환불, 첫 언어가 실패하면 환불 대신 같은 프로젝트에서 무료로 재시도. 이미 돌고 있는 작업을 지워도 환불하지 않는다 | `help-center/product/dubbing/how-much-does-dubbing-cost.md` |
| 효과음 | 설정(생성 개수, 길이) 기준. 입력 텍스트는 비용과 무관 | `.../how-much-does-it-cost-to-generate-sound-effects.md` |
| 뮤직 | 곡 길이 × 변형 개수. 앱은 생성 전에 비용을 보여 준다 | `.../how-much-does-eleven-music-cost.md` |
| 보이스 체인저·보이스 아이솔레이터 | 웹과 API 요율이 다르다는 것만 확인. 단위(분/초)는 가격 페이지에 있어 확인 못 함 | `.../how-much-does-voice-changer-cost.md`, `.../how-much-does-voice-isolator-cost.md` |
| Flows 이미지·비디오 | 시간 초과로 실패하면 "과금하지 않음" 메시지. 실패 사유 enum에 `charging_failed`가 있다(과금 실패를 별도 실패로 다룸) | `image-and-video/webhooks.md`, OpenAPI |
| 에이전트 통화 | 웹훅 `metadata.cost`, `charging` 필드 | `resources/webhooks.md` 예시 |

**계량과 한도를 거는 지점(서버 로직 관점)**
- 한 번에 쓸 수 있는 크레딧은 월 할당량의 2배까지(악용 방지 목적이라고 명시).
- API 키 단위 월 한도 `character_limit`(넘으면 과금 요청 실패), 멤버 단위 `usage-limit`, 그룹 단위 billing group 한도, 워크스페이스 초과 한도 `max_credit_limit_extension`(`"unlimited"` 또는 0이면 사용량 기반).
- 사용량 기반 청구가 월 구독료의 2배를 넘으면 그 자리에서 결제한다.
- 생성 기록 하나하나에 `character_count_change_from`/`_to`가 남는다. 요청 단위 원장(ledger)이 있다는 뜻이다.
- 응답 헤더로 생성 비용을 알려 주는지(예: 글자 수 헤더)는 명세에 응답 헤더 정의가 없어 확인 못 함. **실행 확인 필요**.

---

## 5. 본인 확인·악용 방지 안전장치(문서 기준)

| # | 장치 | 동작 | 출처 |
|---|---|---|---|
| 1 | PVC는 본인 목소리만 | 동의가 있어도 남의 목소리로는 PVC를 만들 수 없다. 공유하려면 목소리 주인이 자기 계정에서 PVC를 만들고 링크로 공유한다 | `help-center/.../can-i-create-a-professional-voice-clone-of-someone-elses-voice.md` |
| 2 | 보이스 캡차 | `GET .../captcha`가 여러 줄 문장이 담긴 이미지(base64)를 준다. 목소리 주인이 그 자리에서 읽어 녹음하고 `POST .../captcha`로 제출하면, 학습용 샘플과 같은 목소리인지 확인한다. 시도 횟수(`verification_attempts_count`, `max_verification_attempts`)를 넘기면 24시간 뒤 다시 할 수 있고, 지원팀이 횟수를 초기화해 줄 수 있다. 시각장애처럼 캡차를 못 하는 경우를 위한 수동 확인 요청(`POST .../verification`)이 있다. 한계도 문서에 적혀 있다: "녹음이 정말 요청자 것인지는 보장 못 하고, 요청자가 그 자리에 있었다는 것만 확인한다" | `eleven-api/concepts/voice-cloning.md`, `.../professional-voice-cloning.md`, `.../what-can-i-do-if-i-failed-to-verify...md`, 스키마 `FineTuningResponseModel` |
| 3 | IVC 보호 음성 대조 | IVC 응답의 `requires_verification`, `library_voice_match`: 샘플이 라이브러리의 보호 음성과 일치하면 확인을 거쳐야 쓸 수 있고, 대신 그 라이브러리 음성을 추가하라고 안내한다. 개념 문서는 "IVC와 PVC 모두 확인 단계가 있다"고 적었지만, IVC를 항상 확인하는지 조건부인지는 문서로 확인 못 함 | OpenAPI `AddVoiceIVCResponseModel`, `concepts/voice-cloning.md` |
| 4 | No-Go Voices | 유명 공인의 목소리와 비슷한 클론을 만들지 못하게 막는다. 걸린 음성은 차단된다. 위반 시 경고, 음성 삭제, 계정 정지, 필요하면 수사기관 협조 | `help-center/legal/what-are-no-go-voices.md` |
| 5 | 생성자 추적 | "모델이 생성한 모든 오디오는 생성한 사용자까지 즉시 추적할 수 있다" | `.../are-there-any-restrictions-on-what-voices-i-can-upload...md` |
| 6 | 워터마크·판별 API | 생성 오디오에 들리지 않는 워터마크를 넣는다. `POST /v1/content-provenance/watermark`는 `is_detected`와 `details{product, model, generated_at, unique_id}`만 돌려주고, 프롬프트·계정은 노출하지 않는다. 파일은 50MB 이하, 0.5초~5분. 키당 24시간에 25회까지. 워터마크 권한이 있는 키만 쓸 수 있고 OAuth 토큰은 안 된다. 뮤직·음원 분리는 `sign_with_c2pa`(MP3에 C2PA 서명) 옵션이 있다 | `eleven-api/concepts/content-provenance.md`, `help-center/legal/audio-detector/...`, OpenAPI |
| 7 | 공유 음성 실시간 검열 | 공유 PVC에 Live Moderation을 켜면, 그 음성으로 들어온 요청 텍스트가 금지 범주에 해당하는지 검사한다(지연이 늘 수 있음). 공유 심사 상태, `ban_reason`, `moderation_check`, `safety_control` 필드가 있다 | `.../what-is-live-moderation.md`, 스키마 `VoiceSharingResponseModel` |
| 8 | 무료 등급 악용 탐지 | 같은 IP나 VPN 등으로 여러 계정이 의심되면 무료 사용을 막는다(`status: free_disabled`). 유료 플랜은 해당 없음 | `help-center/account/general/what-does-unusual-activity-detected...md` |
| 9 | 사용량 폭주 방지 | 한 번에 쓰는 크레딧을 월 할당량의 2배로 제한, 키·멤버·그룹 한도(4절) | 4절 출처 |
| 10 | 키 보안 | 권한 범위, IP 허용 목록(어기면 403), 만료(문서는 15분~30일, 명세 `expires_at_unix` 설명은 15분~90일로 **서로 다름**), 키를 가진 쪽이 스스로 끌 수 있는 설정, 서비스 계정으로 환경 분리, 브라우저에는 1회용 토큰 | `api-reference/authentication.md`, `best-practices/security.md`, OpenAPI |
| 11 | 리소스 권한 | 클론 음성을 우리 서비스 사용자에게 쓰게 할 때, 백엔드에서 `user_id | voice_id | permission_level(viewer/editor/admin)`로 접근을 통제하라고 권장 | `best-practices/security.md` |
| 12 | 데이터 보호 | `enable_logging=false` = 무보관 모드(엔터프라이즈 전용, 기록·전사 저장 안 함). STT 개인정보(PII·PHI·PCI) 탐지·가림 | `resources/zero-retention-mode.md`, OpenAPI |
| 13 | 콘텐츠 제한 | 더빙 욕설 필터(베타), 더빙 결과물 워터마크 옵션, 뮤직 파인튠 저작권 위반 차단(`copyright_violation`, 상태 `blocked`), Flows 검열 실패(`moderated`) | OpenAPI enum |
| 14 | 약관 | 이용약관과 금지 사용 정책(Prohibited Use Policy)에 따라 조치 | 위 4·5번 출처 |

캡차 문장을 어떻게 고르는지, 화자 일치 판정 기준, No-Go 목록과 판정 방식, 워터마크 알고리즘은 문서에 없어 확인 못 함.

---

## 6. 음성 엔진 후보 비교

- 조사 방법: 저장소 LICENSE·README, HF 모델 카드, 벤더 공식 문서를 열어 읽은 내용만 적었다. 설치·실행·가입은 하지 않았다. 품질과 지연은 모두 **벤더가 적은 값**이고 우리 실측이 아니다.
- 핵심 수치는 원문과 다시 대조했다: CosyVoice README(한국어·150ms)·LICENSE(Apache-2.0)·HF 카드(`license: apache-2.0`), Fish LICENSE(연매출 USD 500,000 기준, Hosted Service 조항), F5-TTS README(가중치 CC-BY-NC), CosyVoice3 TRT-LLM 벤치 표(L20), faster-whisper 벤치 표(RTX 3070 Ti), Whisper VRAM 표.
- 라이선스는 법률 자문이 아니다. 도입 전에 법무 검토가 필요하다(특히 Fish, Boson/Higgs, bilibili, Llama 기반 모델).
- 2026년에 라이선스가 바뀐 프로젝트가 많다(Fish Speech 2026-10-13, Higgs v3 2026-07-08, Chatterbox 2026-08 은퇴). 예전에 알려진 정보와 다를 수 있다.

### 6.1 TTS

| 후보 | 형태 | 코드 / 가중치 라이선스 | 상업 이용 | 한국어 | 지연·스트리밍(벤더 표기) | 출처 |
|---|---|---|---|---|---|---|
| **Fun-CosyVoice3-0.5B / CosyVoice2-0.5B** | 오픈소스 | Apache-2.0 / Apache-2.0 | 가능 | 예(README "9 common languages (… Korean …)") | 텍스트 입력·오디오 출력 양방향 스트리밍 "as low as 150ms"(하드웨어 미표기) | github.com/FunAudioLLM/CosyVoice (README, LICENSE), huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 |
| MeloTTS-Korean | 오픈소스 | MIT / MIT | 가능 | 예(한국어 전용 카드) | "CPU 실시간 추론 가능"(수치 없음). 제로샷 클로닝 없음 | github.com/myshell-ai/MeloTTS, huggingface.co/myshell-ai/MeloTTS-Korean |
| Orpheus 3B | 오픈소스 | Apache-2.0 / Apache-2.0(한국어 모델은 "research release") | 라이선스상 가능. 한국어 모델은 연구용 프리뷰 | 연구용 한국어 모델 있음 | 스트리밍 약 200ms, 입력 스트리밍 시 약 100ms(README) | github.com/canopyai/Orpheus-TTS, huggingface.co/canopylabs/3b-ko-ft-research_release |
| Chatterbox Multilingual V3 | 오픈소스(**2026-08 은퇴**) | MIT / MIT | 가능하지만 유지보수 중단 | 예(23개 언어에 ko) | 확인 못 함 | github.com/resemble-ai/chatterbox |
| Google Cloud TTS Chirp 3 HD | 상용 API | — | 상용(가격 확인 못 함) | 예(ko-KR) | 스트리밍 합성 지원, 지연 수치 없음 | docs.cloud.google.com/text-to-speech/docs/chirp3-hd |
| Azure Speech(HD 음성) | 상용 API | — | 상용(가격 확인 못 함) | 예(ko-KR 음성 여러 개) | 수치 없음 | learn.microsoft.com/…/speech-service/language-support |
| Typecast API | 상용 API | — | 상용(웹 요금제와 API 구독이 따로) | 예 | 청크 스트리밍 지원 | typecast.ai/docs/overview |
| Naver CLOVA Voice | 상용 API | — | 상용(가격 확인 못 함) | 예 | REST 요청-응답, 한 번에 200자 제한 | api.ncloud-docs.com/docs/ai-naver-clovavoice |

탈락: Spark-TTS(가중치 CC-BY-NC-SA, 한국어 없음), IndexTTS(bilibili 라이선스, 한국어 없음), Kokoro·Zonos·Dia(한국어 확인 안 됨 또는 미지원), MaskGCT(가중치 CC-BY-NC), Higgs v3(연구·비상업), Fish Speech(6.6 참고), OpenAI TTS 3종(공식 문서상 2027-01-06 종료 예정).

### 6.2 보이스 클로닝(제로샷·퓨샷)

| 후보 | 코드 / 가중치 라이선스 | 상업 이용 | 한국어 | 메모 | 출처 |
|---|---|---|---|---|---|
| **CosyVoice 2/3** | Apache-2.0 / Apache-2.0 | 가능 | 예 | README "multi-lingual/cross-lingual zero-shot voice cloning". 오픈소스 중 **한국어 + 제로샷 클로닝 + 상업 허용 + 스트리밍**을 모두 문서로 확인한 유일한 후보 | 위 6.1 |
| Chatterbox Multilingual | MIT / MIT | 가능(은퇴) | 예 | 모든 출력에 Perth 워터마크 내장 | 위 6.1 |
| F5-TTS | MIT / **CC-BY-NC-4.0** | **불가**(가중치) | 확인 못 함 | 학습 데이터(Emilia) 때문에 가중치가 비상업 | github.com/SWivid/F5-TTS |
| XTTS-v2 | 확인 못 함 / Coqui Public Model License | **판정 보류**(라이선스 전문 페이지가 열리지 않음) | 예(17개 언어) | 6초 샘플로 클로닝. 회사(Coqui)가 서비스를 접어 계약 상대가 없을 위험 | huggingface.co/coqui/XTTS-v2 |
| Typecast Instant Cloning | 상용 | 요금제별 | 예 | Studio에서 만든 클론은 API에서 바로 못 씀 | typecast.ai/pricing |
| Azure Custom Neural Voice / Personal Voice | 상용(Limited Access) | 조건부 | 확인 못 함 | MS 계정팀이 직접 관리하는 고객만 쓸 수 있다. 성우 서면 동의와 동의 녹음 필요 | learn.microsoft.com/…/custom-neural-voice |

### 6.3 STT

| 후보 | 형태 | 코드 / 가중치 라이선스 | 상업 | 한국어 | 스트리밍 | 출처 |
|---|---|---|---|---|---|---|
| **Whisper large-v3 / large-v3-turbo** | 오픈소스 | MIT / Apache-2.0(v3), MIT(turbo) | 가능 | 예 | 기본 기능으로는 실시간 불가(README) | github.com/openai/whisper, HF 카드 |
| **faster-whisper** | 오픈소스(추론 엔진) | MIT / 원본 Whisper 가중치 라이선스를 따름 | 가능 | Whisper와 같음 | 외부 프로젝트(WhisperLive 등)로 스트리밍 | github.com/SYSTRAN/faster-whisper |
| SenseVoice-Small | 오픈소스 | MIT / FunASR Model License v1.1 | 조건부(출처 표기 의무, 약관을 일방적으로 바꿀 수 있음) | 예 | 비스트리밍(VAD로 잘라 처리) | huggingface.co/FunAudioLLM/SenseVoiceSmall |
| **Return Zero(VITO)** | 상용 | — | 상용(600분 무료) | 예(`sommers_ko`) | WebSocket·gRPC 실시간 | developers.rtzr.ai/docs/stt-streaming |
| Google STT Chirp 3 | 상용 | — | 상용 | 예(ko-KR GA) | StreamingRecognize | docs.cloud.google.com/speech-to-text/docs/models/chirp-3 |
| Deepgram Nova-3 | 상용 | — | 종량제 스트리밍 $0.0048/분 | 예(최신 스트리밍 모델 Flux는 한국어 미지원) | 지원 | developers.deepgram.com/docs/models-languages-overview, deepgram.com/pricing |

탈락: NVIDIA Parakeet-tdt-0.6b-v3 / Canary-1b-v2(CC-BY-4.0으로 상업 가능하지만 지원 25개 언어에 한국어 없음).

### 6.4 음원 분리·보컬 추출·노이즈 제거

| 후보 | 코드 / 가중치 라이선스 | 상업 | 메모 | 출처 |
|---|---|---|---|---|
| **Demucs(htdemucs, htdemucs_ft, htdemucs_6s)** | MIT / 가중치 별도 표기 확인 못 함 | 코드 가능, 가중치는 확인 필요 | 원 저장소는 유지보수하지 않음(포크 있음). 4·6 스템 | github.com/facebookresearch/demucs |
| BS-RoFormer / Mel-RoFormer(python-audio-separator, ZFTurbo) | MIT / **모델마다 다름, 확인 못 함** | 가중치 출처를 하나씩 추적해야 함 | 품질은 좋다고 알려졌지만 커뮤니티가 학습한 체크포인트가 많다 | github.com/nomadkaraoke/python-audio-separator, github.com/ZFTurbo/Music-Source-Separation-Training |
| **DeepFilterNet**(음성 노이즈 제거) | MIT 또는 Apache-2.0 / 별도 표기 확인 못 함 | 코드 가능 | 실시간 버전 있음, 48kHz WAV 전용 | github.com/Rikorose/DeepFilterNet |
| Spleeter | MIT / 확인 못 함 | 코드 가능 | 2/4/5 스템 | github.com/deezer/spleeter |
| AudioShake, LALAL.AI | 상용 | 가격·약관 확인 못 함 | 위탁 처리 대안 | audioshake.ai, lalal.ai/api |

### 6.5 GPU 요구사항·처리량·첫 음성 지연 (데브옵스팀 비용 산정용)

모든 수치는 출처에 적힌 값을 **그대로** 옮겼다(환산하거나 늘려 잡지 않음). 영어·중국어 등 벤더 데이터로 잰 값이라 한국어 문장과 실제 트래픽에서는 다를 수 있다. 용량을 산정하기 전에 한국어로 자체 벤치마크가 필요하다.

| 엔진 | 기능 | GPU·VRAM | 처리량(RTF 등) | 첫 음성·첫 결과 지연 | 측정 조건 | 출처 |
|---|---|---|---|---|---|---|
| Fun-CosyVoice3-0.5B (TensorRT-LLM + Triton) | TTS·클로닝 | NVIDIA L20 1장. VRAM 사용량은 확인 못 함 | 오프라인, LLM 배치 1/2/4/8/16에서 RTF 0.1091 / 0.0822 / 0.0630 / 0.0562 / 0.0501 | 스트리밍 첫 청크, 동시 4: 평균 750.42ms, p50 740.31ms, p90 941.05ms, p99 1002.37ms | L20 1장, Triton 벤치 | github.com/FunAudioLLM/CosyVoice/blob/main/runtime/triton_trtllm/README.Cosyvoice3.md |
| CosyVoice2-0.5B (TRT-LLM + DiT Token2Wav) | TTS·클로닝 | L20 1장. VRAM 확인 못 함 | 동시 1/2/4/6/8/10에서 RTF 0.1228 / 0.0901 / 0.0741 / 0.0774 / 0.0691 / 0.0707. 오프라인 배치 16에서 RTF 0.0292 | 첫 청크 평균: 동시 1 197.50ms, 2 281.15ms, 4 510.65ms, 6 921.54ms, 8 1019.95ms, 10 1214.98ms | L20 1장, `yuekai/seed_tts_cosy2` | …/runtime/triton_trtllm/README.Cosyvoice2.DiT.md |
| CosyVoice2-0.5B (TRT-LLM + Unet Token2Wav) | TTS·클로닝 | L20 1장 | 스트리밍 RTF(화자 캐시 끔/켬): 동시 1 0.1237/0.1155, 2 0.1022/0.0905, 4 0.0922/0.0733 | 첫 청크 평균(끔/켬): 동시 1 220.43/189.88ms, 2 476.97/323.04ms, 4 1107.34/977.68ms | L20 1장, seed_tts 26쌍 | …/runtime/triton_trtllm/README.Cosyvoice2.Unet.md |
| Orpheus 3B | TTS | H100 MIG(H100의 절반, 40GB). 모델 자체 VRAM 사용량은 없음 | 동시 실시간 스트림: 원본 구현 7개, TensorRT-LLM 최적화 16개(안정 트래픽에서 최대 24개). 대량 작업 "RTF up to 60x" | TTFB: H100 MIG 200ms, H100 전체 150ms 미만 | Baseten 최적화 배포. 한국어 모델 수치는 없음 | baseten.co/blog/canopy-labs-selects-baseten-as-preferred-inference-provider-for-orpheus-tts-model |
| MeloTTS-Korean | TTS | 확인 못 함 | "CPU 실시간 추론 가능"(수치 없음) | 확인 못 함 | CPU 사양 미표기 | huggingface.co/myshell-ai/MeloTTS-Korean |
| Chatterbox Multilingual | TTS·클로닝 | 확인 못 함 | 확인 못 함 | 확인 못 함 | — | github.com/resemble-ai/chatterbox |
| XTTS-v2 | TTS·클로닝 | 추론 GPU 확인 못 함 | 확인 못 함 | "<200ms" 스트리밍(하드웨어 미표기) | — | github.com/coqui-ai/TTS |
| Whisper large / turbo | STT | VRAM: large 약 10GB, turbo 약 6GB | 상대 속도: large 1x, turbo 약 8x | 기본 기능으로는 실시간 불가 | A100, 영어 음성 | github.com/openai/whisper (README 표) |
| faster-whisper (large-v2) | STT | 13분 오디오 기준 VRAM: fp16 4525MB, fp16 batch8 6090MB, int8 2926MB, int8 batch8 4500MB | 13분 오디오 처리 시간: fp16 1분 03초, batch8 17초, int8 59초, int8 batch8 16초(원본 openai/whisper fp16은 2분 23초) | 스트리밍 수치 없음 | RTX 3070 Ti 8GB, CUDA 12.4, beam 5. large-v3·turbo 행은 없음 | github.com/SYSTRAN/faster-whisper (README Benchmark) |
| SenseVoice-Small | STT | 확인 못 함 | "10초 오디오를 70ms에 처리, Whisper-Large보다 15배 빠름"(GPU 미표기). Triton+TensorRT FP32에서 V100 "acceleration ratio 526" | 비스트리밍 | 70ms 수치의 측정 GPU 미표기 | huggingface.co/FunAudioLLM/SenseVoiceSmall, github.com/FunAudioLLM/SenseVoice |
| Demucs htdemucs / _ft | 음원 분리 | GPU 메모리 최소 3GB, 기본 설정에서 약 7GB(`--segment`로 줄일 수 있음) | CPU에서 곡 길이의 약 1.5배 시간. htdemucs_ft는 htdemucs보다 4배 오래 걸림 | 해당 없음(오프라인) | GPU 모델 미표기 | github.com/facebookresearch/demucs |
| BS / Mel-RoFormer | 음원 분리 | 추론 VRAM 확인 못 함 | 확인 못 함 | 해당 없음 | — | python-audio-separator, ZFTurbo README |
| DeepFilterNet 2 / 1 | 노이즈 제거 | GPU 불필요(CPU) | RTF 0.04(노트북 Core-i5, DFN2), 0.19(단일 스레드 노트북 CPU, DFN1) | 확인 못 함 | 현재 배포판인 DFN3 수치는 확인 못 함 | arxiv.org/abs/2205.05474, arxiv.org/abs/2305.08227 |
| (참고) ElevenLabs 자체 | TTS | — | — | 서버 쪽 중앙값: v4 Turbo·Flash v2.5 약 100ms, v3 Conversational 약 165ms | 네트워크 제외 | `overview/models.md` |

- **CosyVoice VRAM(데브옵스 추가 문의, 2026-11-21)**: 공식 README·HF 카드·TRT-LLM 벤치 문서·학습 레시피 어디에도 추론 VRAM 수치가 없다. 웹 검색에서도 믿을 만한 실측을 찾지 못했다(확인 못 함). 참고할 수 있는 것은 모델 파일 크기뿐이다(HF API 기준).
  - CosyVoice2-0.5B: 저장소 합계 4.86GB(`llm.pt` 2.02GB, `flow.pt` 0.45GB, `speech_tokenizer_v2.onnx` 0.50GB 등)
  - Fun-CosyVoice3-0.5B-2512: 저장소 합계 9.75GB(`llm.pt`와 `llm.rl.pt`가 각 2.02GB, `flow.pt` 1.33GB 등)
  - 저장소에는 같은 역할의 대체 파일(rl판, onnx판)이 함께 들어 있어서, 실제로 올라가는 크기는 합계보다 작다. **파일 크기는 VRAM이 아니다.** 실측은 GPU에서 `torch.cuda.max_memory_allocated()`로 재야 한다(2단계 벤치 항목).
- **미세조정(PVC급) 소요 시간**: CosyVoice는 짧은 참고 음성으로 클로닝(제로샷)하므로 기본 흐름에는 학습이 없다. 공식 학습 레시피(`examples/libritts/cosyvoice2|cosyvoice3/run.sh`, `conf/cosyvoice2.yaml`)는 CosyVoice2를 GPU 4장(DDP), CosyVoice3를 1장으로 잡고 `max_epoch: 200`을 쓰지만, 이건 데이터셋 전체를 학습하는 레시피이고 **걸리는 시간은 적혀 있지 않다**(화자 1명 미세조정 시간은 확인 못 함). 비교 기준으로 ElevenLabs PVC는 "약 3~6시간"(`help-center/.../when-will-my-professional-voice-clone-pvc-be-ready.md`)이라는 문서와 "미세조정 6~24시간"(`.../what-does-the-status-of-my-professional-voice-clone-mean.md`)이라는 문서가 **서로 다르게** 적혀 있다(대기열 시간 제외).
- 상용 API(Google Chirp 3 HD·STT, Azure TTS, Return Zero, Deepgram Nova-3)는 벤더 문서에 지연 수치가 없었다. 제3자 벤치는 조사하지 않았다.
- 읽는 법: RTF 0.05는 "오디오 1초를 만드는 데 0.05초가 걸린다"는 뜻이다. 다만 위 CosyVoice 수치는 **동시 요청 수가 늘면 첫 청크 지연이 빠르게 커진다**(CosyVoice2 DiT 기준 동시 1에서 197ms, 동시 10에서 1,215ms). GPU 한 장이 받을 동시 스트림 수는 지연 목표(예: 첫 음성 500ms 이하)를 먼저 정한 뒤 계산해야 한다.

### 6.6 기능별 추천과 라이선스 함정

**추천(한국 상용 제품 기준, 백엔드팀 의견)**
- **TTS·클로닝**: 자체 호스팅 1순위는 CosyVoice3(필요하면 2)다. 비교할 후보는 MeloTTS-Korean(경량, 클로닝 없음). 상용 대체·장애 대비로는 Google Chirp 3 HD 또는 Azure를 둔다. "남이 목소리를 올려 생성하는" 서비스 형태는 Fish·Higgs v3 라이선스상 불가능하고, Azure CNV는 자격 조건 때문에 제외한다.
- **STT**: 배치는 Whisper large-v3-turbo + faster-whisper. 실시간 한국어는 Return Zero, Google Chirp 3, Deepgram Nova-3 중에서 고른다(자체 스트리밍은 2차).
- **음원 분리**: Demucs로 시작하되 가중치 라이선스를 확인한다. 품질이 모자라면 RoFormer 체크포인트 출처를 하나씩 확인하거나 상용 API에 위탁한다. 음성 노이즈 제거(보이스 아이솔레이터에 해당)는 DeepFilterNet이 후보다.

**라이선스 함정**
1. F5-TTS: 코드는 MIT지만 가중치는 CC-BY-NC-4.0이다. 코드 라이선스만 보면 오판한다.
2. Fish Speech(2026-10-13판 Fish Audio Community License): 연매출 USD 500,000 미만만 상업 이용을 허용하고, **Hosted Service(API, TTS·클로닝 웹앱)는 매출과 관계없이 별도 계약이 필요**하다. S2-Pro 가중치는 연구·비상업 전용이다.
3. Higgs Audio v3: 연구·비상업 전용. v2는 Llama 3 기반 라이선스(연간 활성 사용자 100,000명을 넘으면 별도 허가).
4. XTTS-v2: Coqui Public Model License 전문을 열지 못해 판정을 보류했다. 법무 확인이 필요하다.
5. Spark-TTS는 Apache-2.0에서 CC-BY-NC-SA-4.0으로 바뀌었고, MaskGCT 가중치는 CC-BY-NC-4.0이다.
6. SenseVoice: 코드(MIT)와 가중치(FunASR Model License) 라이선스가 다르다. 출처 표기 의무가 있고 약관이 자동으로 개정될 수 있다.
7. Chatterbox: MIT지만 2026-08에 은퇴해 지원이 없다.
8. RoFormer·Demucs: 코드는 MIT지만 체크포인트(가중치)별 라이선스는 확인 못 함.
9. OpenAI TTS 3종: 2027-01-06 종료 예정이라 신규 도입은 권하지 않는다.
10. Azure CNV·Personal Voice: Limited Access(MS 직접 관리 고객만), 성우 서면 동의, 합성 사실 공개 의무.

**확인 못 함(엔진)**: Coqui CPML 전문, 상용 API 대부분의 가격(Google·Azure·CLOVA·Return Zero·AudioShake·LALAL.AI), CosyVoice VRAM 사용량과 PyTorch·vLLM 경로의 RTF, MeloTTS·Chatterbox·XTTS의 GPU 수치, faster-whisper의 large-v3·turbo 벤치, RoFormer 추론 수치, Azure CNV의 ko-KR 지원 여부, Supertone 공식 API 문서(접속 불가, 검색 요약만 봄).

---

## 7. 우리 제품 백엔드에 주는 시사점 (제안, 사실 아님)

위 사실을 바탕으로 한 백엔드팀 의견이다. 2단계에서 대표 결정이 필요하다.

1. **작업(Job) 테이블 하나로 통일**: ElevenLabs는 기능마다 상태 enum이 제각각이다(더빙 5종, PVC 6종, Flows 4종 등). 우리는 `job(id, type, status[queued|running|succeeded|failed|canceled], progress, error_code, cost_estimate, cost_charged, result_ref, webhook_target)` 하나로 묶고, 폴링(GET)과 웹훅을 같은 응답 모양으로 내보내자(Flows 방식).
2. **계량은 원장(ledger) 방식으로**: 요청마다 `예상 차감 → 확정 → 실패하면 환불` 순서로 기록한다. 더빙의 "선결제 + 실패 시 환불 또는 무료 재시도" 규칙을 일반화한다. 한도는 워크스페이스 → 그룹 → 멤버 → API 키 순으로 겹쳐 검사하고, 한 번에 쓸 수 있는 양에 상한을 둔다.
3. **스트리밍은 HTTP chunked 먼저, WebSocket은 2차**: 문서도 대부분은 HTTP 스트리밍으로 충분하다고 한다. WebSocket은 LLM과 이어지는 대화형 기능에서만 필요하다.
4. **클로닝 안전장치는 MVP에 필수**: 본인 녹음 확인(무작위 문장을 그 자리에서 읽기 + 화자 일치), 생성물 워터마크, 생성자 추적 로그, 공인 음성 차단 목록. 법적 위험은 마케팅팀 분석과 함께 봐야 한다.
5. **동시 처리 한도는 GPU 큐로**: 플랜별 동시 처리 칸 + 우선순위 큐 + `current/maximum-concurrent-requests` 헤더 방식을 그대로 가져오면 GPU 비용을 관리하기 쉽다(데브옵스팀과 협의).

---

## 8. 프론트팀 요청 반영 (설계 제안, 대표 추가 지시 2026-11-21)

요청 출처는 `03-frontend-client-logic.md` 8절의 (a)(b)(c)다. 아래는 백엔드팀 **제안**이다. ElevenLabs 사실을 인용한 곳에만 출처를 단다. 1단계는 문서 단계라서 코드는 만들지 않았다.

### 8.1 스트림 중계 방식 (`audio/mpeg` 원시 바이트로 통일)

```
브라우저                     우리 서버                                ElevenLabs(또는 2단계의 자체 엔진)
POST /api/tts  ───────────▶  ① 로그인·입력 검증(글자 수 ≤ 모델 한도)
 {text, voice_id, model}     ② 음성 사용 권한 검사(user_id·voice_id·permission)
                             ③ 크레딧 예약(원장에 '예약' 기록)
◀── {stream_url, job_id} ──  ④ 1회용 재생 ID 발급(사용자에 묶음, TTL 60초)
<audio src=stream_url> ───▶  GET /api/tts/{job_id}/stream
                             ⑤ ID 확인 후 즉시 폐기(재사용·공유 방지)
                             ⑥ POST /v1/text-to-speech/{voice}/stream ─────────▶ (xi-api-key는 서버에만)
                             ⑦ 업스트림 상태 확인: 2xx가 아니면 첫 바이트 전에 JSON 오류로 응답
◀── 200 audio/mpeg chunked ─ ⑧ 받은 바이트를 그대로 전달 + 동시에 저장소로 복사(tee) ◀── 오디오 청크
                             ⑨ 끝나면 원장 '확정', 실패하면 '환불'. 기록(history) 저장
```

- **왜 POST 후 GET인가**: `<audio src>`는 GET만 보낼 수 있다. 텍스트를 URL에 싣지 않으려고 POST로 작업을 먼저 만들고, 재생은 짧게 살아 있는 1회용 ID로 GET 한다. 프론트 1차안(`/api/tts/{id}/stream`)과 같은 구조다.
- **응답 헤더**: `Content-Type: audio/mpeg`(요청한 `output_format`이 mp3일 때. pcm이면 `audio/L16`이나 WAV 헤더를 붙여야 하는데, 이건 저지연 경로에서만 쓴다), `Cache-Control: no-store`, 리버스 프록시 버퍼링 끄기(nginx 쓰면 `X-Accel-Buffering: no`), `Content-Length`는 안 보낸다(chunked).
- **형식 흡수**: 업스트림 `Content-Type`이 `text/event-stream`이고 본문이 `data:`로 시작하면 SSE를 풀어 오디오만 꺼내고, 그 밖이면 그대로 넘긴다. 3.1의 판정이 어느 쪽으로 나와도 브라우저 계약은 바뀌지 않는다.
- **취소**: 브라우저가 연결을 끊으면 업스트림 요청도 끊는다(Node는 `AbortController`). 이때 크레딧이 차감되는지는 확인 못 함(9절). 우리 원장은 "받은 바이트가 있으면 확정"으로 둘지 대표 결정이 필요하다.
- **오류 매핑**: 업스트림 `401/403` → 우리 `502`(키 문제, 사용자 탓 아님), `422` → `400`, `429` 또는 동시 처리 한도 초과 → `429` + `Retry-After`. 업스트림 응답 헤더 `current-concurrent-requests`, `maximum-concurrent-requests`(출처: `overview/models.md`)는 로그로 남겨 혼잡도 지표로 쓴다.
- **자막·하이라이트용**: `/with-timestamps`는 줄마다 JSON이 오는 형식(NDJSON, 3.1)이라 `<audio>`에 바로 꽂을 수 없다. 이 경로는 `fetch` 스트림 리더로 받는 별도 엔드포인트(`/api/tts/{id}/timed`)로 두고, `audio_base64`와 `alignment`를 그대로 넘긴다.
- **다시 듣기**: ⑧에서 복사해 둔 파일을 객체 저장소에 두고, 서명된 URL로 `<audio>` 재생한다(프론트 2-4의 4번).

### 8.2 업로드 서버 검증·MP3 변환 (음성 클로닝 샘플)

| 단계 | 처리 | 기준·출처 |
|---|---|---|
| 1. 접수 | 로그인 필수. 리버스 프록시에서 요청 크기 상한을 둔다(파일 수 × 10MB + 여유). 스트리밍으로 받으면서 10MB를 넘는 순간 끊는다 | 앱 화면 "파일당 최대 10MB"(`00-ceo-app-notes.md`, `03-frontend` 1절) |
| 2. 형식 판별 | 확장자와 브라우저가 보낸 MIME은 믿지 않는다. 파일 앞부분 바이트(매직 넘버)와 `ffprobe`로 실제 컨테이너·코덱을 확인한다. 오디오 스트림이 없으면 거절한다. 비디오(mp4·mov·webm 등)는 오디오 트랙만 뽑는다 | 앱 `accept`에 오디오·비디오 MIME이 모두 있음(`03-frontend` 1절) |
| 3. 길이 검사 | `ffprobe`의 duration이 아니라 **실제로 디코딩한 길이**로 잰다(헤더를 조작하면 duration을 속일 수 있음). 파일당 5초 이상, 합계 10초~3분(즉시 클로닝 기준) | `eleven-creative/voices/voice-cloning/instant-voice-cloning.md` FAQ, 앱 진행 링 10초~3분(`03-frontend` 1절 인용) |
| 4. 변환 | `ffmpeg -nostdin -hide_banner -i <in> -map 0:a:0 -vn -ac 1 -ar 44100 -c:a libmp3lame -b:a 192k <out>.mp3`. 브라우저 녹음(webm/opus, 사파리 mp4/aac)도 같은 경로로 바꾼다 | MP3 192kbps 이상 권장(`03-frontend` 1절이 인용한 IVC 문서). 모노·44.1kHz는 우리 제안(문서 근거 없음) |
| 5. 품질 점검(선택) | 무음 비율, 클리핑, 너무 작은 음량을 `ffmpeg`의 `silencedetect`, `volumedetect` 필터로 재서 경고만 준다(거절하지 않음) | 제안 |
| 6. 보관 | 원본과 변환본을 비공개 객체 저장소에 사용자 ID 경로로 둔다. 클로닝에 쓴 뒤 보관 기간을 정한다(생체 정보에 해당할 수 있음, 마케팅·법무 검토 필요) | 제안. ElevenLabs도 가입 때 생체 정보 동의를 받는 필드가 있다(`UserResponseModel.show_compliance_terms`: "ToS, Privacy Policy, biometric consent") |
| 7. 동의 기록 | "본인 목소리이거나 권리가 있다" 동의 체크와 시각, IP를 클로닝 요청과 함께 저장한다. PVC급 기능은 5절의 녹음 확인(캡차)을 붙인다 | 5절 1~3 |

- **보안**: `ffmpeg`/`ffprobe`는 신뢰할 수 없는 미디어를 다루므로 별도 워커(컨테이너)에서 시간 제한(예: 30초), 메모리 제한, 네트워크 차단 상태로 돌린다. 웹 서버 프로세스 안에서 돌리지 않는다.
- **비동기로**: 변환이 몇 초 걸릴 수 있으니 업로드 응답은 `202 + upload_id`로 돌려주고, 상태는 7절의 Job 테이블로 조회한다. 진행률은 브라우저 `upload.onprogress`(전송)와 서버 Job 상태(변환)로 나눈다.
- **라이선스 메모**: `libmp3lame`은 LGPL이고, `ffmpeg`는 빌드 옵션에 따라 LGPL 또는 GPL이 된다. 서버에서 실행만 하는 경우와 배포하는 경우의 의무가 다르니 데브옵스팀이 빌드를 고를 때 확인해야 한다.

### 8.3 클라이언트용 일회용 토큰 발급 경로

| 우리 엔드포인트(제안) | 서버가 호출하는 ElevenLabs API | 돌려주는 값 | 출처 |
|---|---|---|---|
| `POST /api/realtime/token` `{kind:"tts_websocket", voice_id, model_id}` | `POST /v1/single-use-token/tts_websocket` | `{token, expires_in: 900, ws_url}` | `api-reference/tokens/create.md`: 15분 뒤 만료, 한 번 쓰면 소멸 |
| `POST /api/realtime/token` `{kind:"realtime_scribe"}` | `POST /v1/single-use-token/realtime_scribe?max_session_duration_seconds=N` | 위와 같음. 세션 최대 시간은 우리가 정한다 | 같은 문서 |
| `POST /api/realtime/token` `{kind:"batch_scribe"}` | `POST /v1/single-use-token/batch_scribe` | 위와 같음. 브라우저가 STT에 파일을 직접 올릴 때만 쓴다(보통은 8.2처럼 우리 서버를 거친다) | OpenAPI `POST /v1/speech-to-text` 쿼리 `token` |
| `GET /api/agents/{id}/session` | `GET /v1/convai/conversation/get-signed-url?agent_id=` 또는 `GET /v1/convai/conversation/token?agent_id=`(WebRTC) | `{signed_url}` 또는 `{token}` | OpenAPI |

- **발급 전 검사**(서버): 로그인 세션 확인 → 사용자별 발급 횟수 제한(예: 분당 N회) → 크레딧 잔액이 최소 기준 이상인지 확인 → 동시에 열 수 있는 세션 수 제한 → 발급 기록(누가, 언제, 어떤 종류)을 원장에 남긴다. 토큰 값 자체는 로그에 남기지 않는다.
- **보안 쟁점**: 일회용 토큰이 특정 `voice_id`·`model_id`에 묶이는지는 문서에 없다(확인 못 함). 묶이지 않는다면, 토큰을 받은 브라우저가 **우리 워크스페이스의 아무 음성**(다른 사용자의 클론 포함)이나 URL에 넣어 쓸 수 있다. 
  - **[결정 사항 · 대표 채택 2026-11-21]** 브라우저가 직접 연결하는 스트리밍(일회용 토큰 WebSocket)은 **공용(premade) 음성만** 허용한다. 사용자 클론 음성은 **반드시 서버 중계**(8.1 HTTP 중계, 실시간이 필요하면 서버가 WebSocket을 중계)로만 쓴다.
  - 구현 규칙: `POST /api/realtime/token`은 요청에 들어온 `voice_id`가 공용 음성인지 서버에서 확인한 뒤에만 토큰을 발급한다. 클론 음성이면 `403`을 돌려주고 중계 경로를 안내한다. 토큰을 발급한 기록에도 `voice_id`를 남긴다.
  - 출처: 5절 11번(`best-practices/security.md`가 백엔드에서 음성 단위 권한을 통제하라고 권장).
- **과금 쟁점**: 직결하면 사용량이 ElevenLabs 쪽에서만 잡힌다. 우리 원장에 반영하려면 사후에 `POST /v1/workspace/analytics/requests`, `GET /v1/history`로 맞춰 봐야 한다(실시간 차감 불가). 서비스 계정을 사용자 등급별로 나누고 키마다 `character_limit`을 거는 방법도 있다(1.4절).
- **2단계(자체 엔진)로 갈 때**: 같은 계약을 유지하고, 토큰만 우리가 발급한다(서명된 짧은 토큰, 15분, `jti`로 한 번만 쓰게, `voice_id`·`model_id`·최대 세션 시간을 토큰 안에 넣음). 그러면 위 보안 쟁점이 구조적으로 풀린다.

---

## 9. 확인 못 함 / 실행 확인 필요 목록

| 항목 | 상태 | 필요한 것 |
|---|---|---|
| HTTP 스트리밍 응답이 원시 바이트인지 SSE인지 | 명세 선언은 SSE, 본문 스키마는 바이너리. 공식 SDK는 원시 바이트·NDJSON으로 읽는다(3.1). 실제 `Content-Type`은 **실행 확인 필요** | 테스트 키로 짧은 TTS 스트림 1회(크레딧 소액 차감) — 대표 승인 필요 |
| 일회용 토큰(`tts_websocket`)이 특정 음성·모델에 묶이는지 | 문서·명세에 없음 → 확인 못 함. 8.3 결정 사항(직결은 공용 음성만)으로 위험을 막아 둠 | 다음 단계 SDK·문서 추가 확인 |
| (공통) 테스트 API 호출 | 사용자 계정 크레딧이 들어가므로 **대표가 사용자 승인을 받아 지시하기 전까지 호출 금지**(2026-11-21 대표 회신) | — |
| 중계 중 클라이언트가 끊겨 업스트림 요청을 취소하면 크레딧이 어떻게 되는지 | 문서에 없음 → **실행 확인 필요** | 위 테스트와 함께 |
| 응답 헤더로 비용(글자 수)과 요청 ID를 주는지 | 명세에 헤더 정의 없음 → **실행 확인 필요** | 위와 같은 호출 1회로 함께 확인 가능 |
| 기능별 정확한 크레딧 요율(보이스 체인저·아이솔레이터·STT·뮤직·API 할인율) | 가격 페이지(`elevenlabs.io/pricing`, `/pricing/api`)는 문서가 아니라 이번 범위에서 읽지 않음 | 데이터팀(07) 분석과 대조 |
| `ElevenLabs-Signature` 헤더 형식(타임스탬프 키, 알고리즘, 허용 시간 차) | 문서에 없음 | 공개 SDK 소스 확인(다음 단계) |
| IVC를 항상 확인하는지, 보호 음성과 겹칠 때만 확인하는지 | 문서 표현이 엇갈림 | 앱에서 IVC 흐름 관찰은 클로닝 금지 규칙에 걸려 불가 |
| API 키 만료 상한(30일 vs 90일) | 문서와 명세가 다름 | 명세가 더 최신일 가능성이 있으나 확인 못 함 |
| 더빙 언어 상태 `stale`의 정확한 뜻 | enum만 있고 설명 없음 | — |

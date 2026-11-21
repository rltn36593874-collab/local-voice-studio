# ElevenLabs 클라이언트 로직 분석 (1단계) — 프론트엔드팀

- 작성: 03-frontend, 2026-11-21
- 근거: 공식 문서(`llms.txt` 색인 → 각 페이지 `.md`), OpenAPI(`/docs/openapi/api-reference-2.json`), AsyncAPI(문서 페이지 내 YAML), 앱 화면 관찰(로그인 크롬, 새 탭, 관찰 후 닫음)
- 지킨 것: 녹음 시작·파일 업로드·생성·설정 변경 **안 함**. 앱에서 누른 것은 음성 라이브러리 미리듣기 재생 1회뿐이다(생성 아님, 크레딧 무관). 재생 후 바로 멈췄다.
- 표기: **[확인]** 직접 본 것 · **[문서]** 공식 문서 문구 · **[제안]** 우리 구현안(판단) · **확인 못 함** / **실행 확인 필요**

> 참고: `https://elevenlabs.io/docs/openapi.json`은 스펙 파일이 아니다. 두 스펙 파일로 연결되는 안내 페이지다. TTS·음성 복제·토큰 엔드포인트는 `openapi/api-reference-2.json`에 있다(377개 경로). 백엔드팀도 이 파일을 보면 된다.

---

## 1. 브라우저 녹음 (즉시 음성 복제 화면 기준)

### 1-1. 관찰 결과
| 항목 | 내용 | 근거 |
|---|---|---|
| 화면 구성 | 왼쪽은 업로드/녹음 영역, 하단에 "파일 업로드 · 오디오 녹음" 두 버튼, "파일당 최대 10MB" 문구가 있다. 오른쪽은 진행 링(최소 10초 ~ 최대 3분)과 "3분 분량 샘플" 안내다. | [확인] 앱 `/app/create-voice/instant` |
| 생성 한도 | 우측 상단에 "0 / 3 생성됨"이 표시된다. | [확인] 같은 화면 |
| 파일 입력 | 숨긴 `input[type=file]` 1개, `multiple=true`다. `accept`에 오디오 MIME(aac, aiff, ogg, mpeg/mp3, opus, wav, webm, flac, mp4, m4a)과 비디오 MIME(mp4, avi, mkv, quicktime, wmv, flv, webm, mpeg, 3gpp)이 들어 있다. 비디오도 받는다. | [확인] 같은 화면 DOM |
| 마이크 권한 시점 | 페이지에 들어간 뒤에도 `navigator.permissions.query({name:'microphone'})`가 `prompt` 상태였다. 페이지 진입만으로는 권한을 요청하지 않는다. 녹음 버튼을 누를 때 요청하는 것으로 보이지만 누르지 않아 **확인 못 함**. | [확인] 같은 화면 |
| 녹음 포맷 / 녹음 중 파형 / 녹음 후 흐름 | 녹음 버튼을 누르지 않아 **확인 못 함** → **실행 확인 필요**(대표 판단: 테스트 계정이나 권한 거부 상태에서 누르는 것까지만 해 볼지) | – |
| 화면상의 파형 | 이 화면에는 `<canvas>`가 0개, SVG가 77개였다. 녹음 전 상태 기준이다. | [확인] |
| 참고(브라우저 능력) | 사용자 크롬 기준 `MediaRecorder.isTypeSupported`: `audio/webm` true, `audio/mp4` true, `audio/wav` false. 크롬이 지원하는 형식이며 ElevenLabs의 실제 선택은 아니다. | [확인] |

### 1-2. 문서상의 제한·권장
| 항목 | 내용 | 출처 |
|---|---|---|
| 최소 길이 | 앱 업로드 시 **파일당 최소 5초, 전체 합계 최소 10초** | [문서] https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning.md (FAQ) |
| 권장 길이 | 1~2분이다. 2~3분을 넘기면 개선이 거의 없고 오히려 나빠질 수 있다. 파일 개수가 아니라 총 길이가 중요하다. | [문서] 같은 페이지 |
| 권장 포맷 | MP3 192kbps 이상(다른 문단은 128kbps 이상)이다. WAV 같은 무압축은 품질에 도움이 안 되고 업로드 문제를 일으킬 수 있다. | [문서] 같은 페이지 |
| 음량 | RMS -23 ~ -18 dB, true peak -3 dB | [문서] 같은 페이지 |
| 녹음 품질 | 잡음·잔향·여러 화자·긴 무음이 없어야 하고, 톤과 음량이 일정해야 한다. | [문서] 같은 페이지 |
| API | `POST /v1/voices/add`, `multipart/form-data`. 필드: `name`(필수), `files`(여러 개, 필수), `remove_background_noise`, `description`, `labels`. 응답: `voice_id`, `requires_verification`, `library_voice_match`(보호 음성과 일치할 때) | [문서] https://elevenlabs.io/docs/api-reference/voices/ivc/create.md , OpenAPI `ivc_create` |
| 10MB 제한 | 앱 UI 문구에만 있다. API 문서에는 크기 제한 수치가 없다(**확인 못 함**). | [확인] 앱 화면 |

### 1-3. 우리 구현안 [제안]
1. **권한**: 녹음 버튼을 누를 때 처음으로 `getUserMedia({audio:{echoCancellation, noiseSuppression}})`를 호출한다. 누르기 전에 왜 마이크가 필요한지 안내 문구를 보여 준다. 거부(`NotAllowedError`)·장치 없음(`NotFoundError`)·https 아님은 각각 따로 안내하고, 언제든 "파일 업로드"로 넘어갈 수 있게 한다. 상태 표시는 `navigator.permissions.query`로 한다(조회만 하므로 팝업이 뜨지 않는다).
2. **포맷**: `MediaRecorder`를 쓴다. `isTypeSupported`로 `audio/webm;codecs=opus` → `audio/mp4` 순서로 고른다(사파리는 mp4). 변환은 서버에서 한다. 문서가 MP3를 권장하므로 백엔드에서 MP3 192kbps로 바꾸는 것을 기본안으로 둔다(→ 백엔드팀 요청).
3. **길이 제한**: 녹음 중 경과 시간 타이머를 띄우고 **3:00에 자동으로 멈춘다**. 10초 전에는 "다음" 버튼을 막는다. 업로드 파일은 `AudioContext.decodeAudioData`로 길이를 재서 파일당 5초 이상·합계 10초~3분을 검사한다. 이 검사는 서버에서도 똑같이 한다(신뢰 경계).
4. **용량 제한**: 파일을 고를 때 `file.size > 10*1024*1024`면 거부한다. 서버에서도 같은 값으로 막는다. 녹음은 opus 기준 3분이면 10MB에 훨씬 못 미칠 것으로 예상하지만, PoC로 실측한다.
5. **파형**: 녹음 중에는 `AnalyserNode` 값으로 canvas에 실시간 레벨과 파형을 그린다. 녹음이 끝난 뒤나 업로드 파일은 `decodeAudioData` 결과를 구간별 peak로 줄여 그린다. 외부 라이브러리 없이 시작하고, 구간 선택·편집이 필요해지면 그때 도입을 검토한다.
6. **진행 링**: 모든 샘플의 총 길이 ÷ 180초. 10초 지점에 최소 표시를 둔다(ElevenLabs와 같은 개념이지만 디자인은 우리 것으로).
7. **업로드**: 브라우저는 우리 백엔드로만 `multipart`를 보낸다. ElevenLabs API 키는 서버에만 둔다([문서] "Do not ... expose it in any client-side code", https://elevenlabs.io/docs/api-reference/authentication.md). 진행률은 `XMLHttpRequest.upload.onprogress`로 표시한다.

---

## 2. 오디오 재생 · TTS 생성 요청/응답 흐름

### 2-1. 엔드포인트 (OpenAPI `api-reference-2.json` 기준)
| 용도 | 엔드포인트 | 응답 Content-Type |
|---|---|---|
| 한 번에 생성 | `POST /v1/text-to-speech/{voice_id}` | `application/octet-stream` (파일 통째) |
| 생성 + 문자 타이밍 | `POST /v1/text-to-speech/{voice_id}/with-timestamps` | `application/json` |
| 스트리밍 | `POST /v1/text-to-speech/{voice_id}/stream` | `text/event-stream` |
| 스트리밍 + 타이밍 | `POST /v1/text-to-speech/{voice_id}/stream/with-timestamps` | `text/event-stream`. 청크마다 `audio_base64`, `alignment`, `normalized_alignment` |

- 요청 본문(JSON): `text`(필수), `model_id`(기본 `eleven_multilingual_v2`), `language_code`, `voice_settings`, `seed`, `previous_text`/`next_text`, `previous_request_ids`/`next_request_ids`(최대 3개), `apply_text_normalization`(auto/on/off), `audio_effects`, `pronunciation_dictionary_locators`(최대 3개) — [문서] https://elevenlabs.io/docs/api-reference/text-to-speech/stream.md
- 쿼리: `output_format`(기본 `mp3_44100_128`). 선택지는 mp3 7종, pcm 8000~48000, ulaw/alaw 8000, opus_48000 5종이다. mp3 192kbps는 Creator 이상, pcm 44.1kHz는 Pro 이상 요금제에서 쓸 수 있다. `enable_logging=false`는 엔터프라이즈 전용인 무보존 모드다. — 같은 페이지
- 앱 화면에서 본 기본 출력 형식 "MP3 44.1kHz 128kbps"는 API 기본값 `mp3_44100_128`과 같다(대표실 메모 + 위 문서).

**문서끼리 맞지 않는 점 → 실행 확인 필요**: `/stream`의 응답 형식이 문서마다 다르다.
- 스트리밍 개요는 "raw audio bytes … chunked transfer encoding"이라고 쓴다. https://elevenlabs.io/docs/api-reference/streaming.md
- OpenAPI와 지연 최적화 가이드는 `text/event-stream`(SSE)이라고 쓴다. https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization.md

실제 응답 형식은 호출해 봐야 알 수 있는데, 호출하면 크레딧이 차감되므로 하지 않았다.

### 2-2. 앱 재생 방식 관찰
- 음성 라이브러리 미리듣기: 페이지 안의 HTML `<audio>` 요소가 `storage.googleapis.com`의 `.mp3`를 직접 재생한다(blob 아님). [확인] `/app/voice-library` 첫 음성 미리듣기
- 앱의 데이터 요청은 브라우저에서 `api.us.elevenlabs.io`로 직접 간다(`/v1/user`, `/v1/models`, `/v2/voices`, `/v1/workspace` 등). [확인] 같은 탭의 Performance resource 목록. 인증 헤더 내용은 보지 않았다.
- TTS 화면의 생성 결과 재생(스트리밍 재생인지, blob 재생인지)은 생성 버튼을 눌러야 알 수 있어 **확인 못 함 → 실행 확인 필요**.

### 2-3. 문서가 말하는 스트리밍 원리
- 스트리밍은 "이미 있는 파일을 내려받는 것"이 아니라 "지금 합성 중인 출력"을 받는 것이다. 그래서 첫 소리까지의 시간이 짧아진다. 체감 지연에는 모델 지연 외에 네트워크(50~200ms)와 플레이어 버퍼가 더해진다. — [문서] https://elevenlabs.io/docs/eleven-api/concepts/audio-streaming.md
- 텍스트가 미리 다 있으면 HTTP 스트리밍으로 충분하다. WebSocket은 LLM처럼 텍스트가 조금씩 생길 때 쓴다. — 같은 페이지

### 2-4. 우리 구현안 [제안]
1. **기본(텍스트를 미리 다 아는 경우)**: 브라우저 → 우리 서버 `POST /api/tts` → 서버가 ElevenLabs `/stream`을 호출해 받은 바이트를 그대로 중계한다. 브라우저는 응답을 `<audio>`에 연결한다.
   - 1차안: 서버가 생성 작업 ID를 주고, `<audio src="/api/tts/{id}/stream">`로 받으면서 바로 재생한다. mp3 점진 재생은 브라우저가 기본으로 처리한다.
   - 위 2-1의 SSE·원시 바이트 문제는 서버가 흡수한다. 브라우저에는 항상 `audio/mpeg` 원시 바이트만 준다. 그러면 프론트는 응답 형식이 바뀌어도 영향을 받지 않는다.
2. **저지연이 필요한 경우(에이전트·실시간)**: `output_format=pcm_24000` 같은 PCM을 받아 Web Audio로 직접 이어 재생한다(`AudioBufferSourceNode`를 시간순으로 예약). 재생 큐, 중단 시 큐 비우기, 지터 버퍼를 우리가 직접 관리해야 한다.
3. **자막·하이라이트**: `/with-timestamps` 계열의 문자 단위 `alignment`로 재생 위치에 맞춰 텍스트를 강조한다.
4. **생성 이력 재생**: 완성된 파일을 우리 저장소(CDN)에 올리고 `<audio>`로 재생한다(ElevenLabs 앱의 미리듣기와 같은 방식).

---

## 3. 실시간 WebSocket 입력 스트리밍

### 3-1. TTS 입력 스트리밍 (`stream-input`)
- URL: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`. 지역 서버로 us·eu·in·sg가 있다.
- 쿼리: `model_id`, `language_code`, `output_format`, `inactivity_timeout`(기본 20초, 최대 180초), `sync_alignment`, `auto_mode`, `apply_text_normalization`, `seed`, `enable_ssml_parsing`, 인증용 `authorization` 또는 `single_use_token`. 헤더로 `xi-api-key`도 받는다.
  — [문서] https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input.md
- 메시지 흐름:
  1. 첫 메시지(InitializeConnection): `text`는 공백 한 칸(" ")이어야 한다. 여기에 `voice_settings`(stability, similarity_boost, style, use_speaker_boost, speed)와 `generation_config.chunk_length_schedule`을 담는다.
  2. 이어서 텍스트 조각(SendText)을 보낸다. 조각마다 `flush: true`(버퍼를 강제로 생성)나 `try_trigger_generation`을 붙일 수 있다.
  3. `{"text": ""}`를 보내면 종료된다(CloseConnection).
  4. 서버는 `audio`(base64), `alignment`, `normalizedAlignment`를 보내고 마지막에 `isFinal`을 보낸다.
  — 같은 페이지 + https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts.md
- 버퍼링: 누적 글자 수가 `chunk_length_schedule`(예: [120,160,250,290])에 닿아야 음성이 나온다. `auto_mode`는 이 균형을 자동으로 맞춘다. — 같은 가이드, audio-streaming 개념 문서
- **브라우저 직접 연결**: 일회용 토큰 `POST /v1/single-use-token/tts_websocket`을 쓴다. 토큰은 15분 뒤 만료되고 한 번 쓰면 소멸한다. 서버가 API 키로 토큰을 발급해 브라우저에 주면, 브라우저가 `single_use_token` 쿼리로 직접 연결한다. — [문서] https://elevenlabs.io/docs/api-reference/tokens/create.md (토큰 종류: `realtime_scribe`, `batch_scribe`, `tts_websocket`)
- 문서의 주의: 텍스트가 미리 다 있으면 WS가 오히려 약간 느릴 수 있고, 다루기도 더 복잡하다. — stream-input 페이지 서두

### 3-2. 실시간 음성 인식 (마이크 → WS, 참고)
- `@elevenlabs/client`의 `Scribe.connect({ token, microphone:{echoCancellation, noiseSuppression} })`, React는 `useScribe`를 쓴다. 토큰은 서버가 `realtime_scribe` 종류로 발급한다(15분). 마이크 오디오를 SDK가 바로 흘려보낸다. 이벤트는 partial/committed transcript다.
  — [문서] https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/client-side-streaming.md

### 3-3. 우리 구현안 [제안]
1. 서버 `GET /api/tts/ws-token`(로그인 필수, 사용자별 요청 횟수 제한) → ElevenLabs 일회용 토큰 발급 → 브라우저가 `wss://…/stream-input?single_use_token=…&model_id=…&output_format=pcm_24000`으로 직접 연결한다. API 키가 브라우저에 가지 않고, 우리 서버가 오디오를 중계하지 않아도 된다.
2. 수신한 base64 PCM은 2-4의 2번 Web Audio 재생 큐로 보낸다. `isFinal`을 받으면 큐를 다 재생한 뒤 종료 상태로 바꾼다.
3. 끊기면 새 토큰을 받아 다시 연결한다(토큰은 일회용이므로 재사용하지 않는다). 20초 동안 아무것도 안 보내면 연결이 끊기므로(`inactivity_timeout`) 연결 수명을 짧게 잡는다.
4. 1단계 제품에서 텍스트를 실시간으로 생성할 필요가 없다면 WS는 미루고 2-4의 HTTP 스트리밍만 만든다.

---

## 4. 대화형 에이전트 위젯 · 클라이언트 SDK (문서 기준)

### 4-1. 위젯
- 임베드: `<elevenlabs-convai agent-id="…">` 커스텀 엘리먼트와 `@elevenlabs/convai-widget-embed` 스크립트(unpkg)를 쓴다.
- **위젯은 인증을 끈 public agent만 쓸 수 있다**("Widgets currently require public agents with authentication disabled"). 노출 범위는 에이전트 Security 탭의 hostname allowlist(최대 10개, 정확히 일치해야 함)로 제한한다.
- 속성:
  - 코어: `agent-id`, `signed-url`, `server-location`, `variant`, `dismissible`
  - 아바타·색상
  - 각종 문구(`listening-text`·`speaking-text` 등)
  - 마크다운 링크 허용 호스트
  - `dynamic-variables`(JSON 문자열)
  - `override-language` / `override-prompt` / `override-first-message` / `override-voice-id`
- 입력 모드: 음성만 / 음성+텍스트 / 채팅 모드
- 클라이언트 도구: `elevenlabs-convai:call` 이벤트에서 `clientTools`를 등록한다. 도구 이름은 대시보드에 등록한 이름과 같아야 한다.
- 문서에 없음: 위젯의 마이크 권한 흐름과 UI 상태 처리

— [문서] https://elevenlabs.io/docs/eleven-agents/customization/widget.md , https://elevenlabs.io/docs/eleven-agents/customization/authentication.md

### 4-2. 클라이언트 SDK
- 패키지: `@elevenlabs/client`(`Conversation.startSession`)와 `@elevenlabs/react`(client를 다시 내보내므로 둘 다 설치할 필요 없음, `ConversationProvider` 필요)
- 세션 시작:
  - public agent: `agentId`
  - private agent, WebSocket 연결: `signedUrl`
  - private agent, WebRTC 연결: `conversationToken`
- 연결 방식: 음성은 WebRTC, 텍스트 전용은 WebSocket이 기본이다. `connectionType`으로 직접 지정할 수 있다.
- **WebRTC에서는 입출력이 `pcm`/48000으로 고정**이다. 이때 `audio` 이벤트가 오지 않는다(오디오는 LiveKit이 처리).
- 시각화용 API:
  - `getInputVolume`/`getOutputVolume`: 0~1 값
  - `getInput/OutputByteFrequencyData`: AnalyserNode 기반 `Uint8Array`
- 제어: `setVolume`, `setMicMuted`, `changeInputDevice`/`changeOutputDevice`(장치 ID)
- 텍스트 보내기:
  - `sendUserMessage`: 응답을 유발한다
  - `sendContextualUpdate`: 응답을 유발하지 않는다
  - `sendUserActivity`: 약 2초 동안 에이전트가 말하지 않는다(입력 중 끼어들기 방지)
- 콜백: `onConnect`, `onDisconnect`, `onMessage`, `onError`, `onStatusChange`(connected/connecting/disconnected), `onModeChange`(speaking/listening) 등
- React 세분 훅: `useConversationStatus`, `useConversationMode`, `useConversationInput` 등
- 마이크: `startSession` 전에 이유를 설명하고 `getUserMedia({audio:true})`로 권한을 받으라고 권장한다. 거부되면 `startSession`이 throw한다. `textOnly:true`면 마이크 권한을 요청하지 않는다.

— [문서] https://elevenlabs.io/docs/eleven-agents/libraries/java-script.md , https://elevenlabs.io/docs/eleven-agents/libraries/react.md

### 4-3. 인증 토큰
- Signed URL: `GET /v1/convai/conversation/get-signed-url?agent_id=…` → `{signed_url: "wss://…"}`.
  - **15분 안에 연결을 시작**해야 한다. 이미 시작한 세션은 15분이 지나도 유지된다.
  - 사용자별로 새로 발급하라고 권장한다.
  - 같은 에이전트에 allowlist와 함께 쓰지 말라고 되어 있다.
- WebRTC 토큰: `GET /v1/convai/conversation/token?agent_id=…` → `{token, conversation_id}`. 만료 시간은 문서에 없다(**확인 못 함**).

— [문서] https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-signed-url.md , https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-webrtc-token.md

### 4-4. 에이전트 WebSocket 직접 프로토콜 (SDK 없이 쓸 때)
- URL: `wss://api.elevenlabs.io/v1/convai/conversation?agent_id=…`(private agent는 signed URL을 쓴다)
- 연결 직후 `conversation_initiation_client_data`를 보낸다. 마이크 오디오는 `{user_audio_chunk: base64}`로 보낸다.
- 서버가 보내는 이벤트:
  - `conversation_initiation_metadata`: 입출력 포맷(예 `pcm_16000`, `pcm_44100`)을 알려 준다
  - `audio`, `user_transcript`, `agent_response`, `agent_response_correction`, `interruption`
  - `ping`: `pong`으로 **바로 응답**해야 연결이 유지된다
  - `client_tool_call`
  - `queue_status`: timed_out이면 close 코드 4300이 온다
- 클라이언트가 보내는 이벤트: `contextual_update`, `user_message`, `user_activity`, `client_tool_result`
- 일부 이벤트는 에이전트 설정의 `client_events`에서 켜야 온다.
- 문서 안에서 표기가 다른 부분: signed URL 쿼리 이름(`token` / `conversation_signature`), pong 형식

— [문서] https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets.md , https://elevenlabs.io/docs/eleven-agents/customization/events/client-events.md , https://elevenlabs.io/docs/eleven-agents/customization/events/client-to-server-events.md

### 4-5. Overrides
- 보안 때문에 기본값은 꺼짐이다. 필드별로 켜야 하고, 켜지 않은 필드를 보내면 대부분 에러가 난다.
- 바꿀 수 있는 필드: 프롬프트, 첫 메시지, 언어, voice ID, LLM, 안정성·속도(0.7~1.2) 등
- 문서는 통째로 덮어쓰는 override보다 dynamic variables를 권장한다.

— [문서] https://elevenlabs.io/docs/eleven-agents/customization/personalization/overrides.md

### 4-6. 우리 구현안 [제안]
- 우리가 에이전트 위젯을 만든다면 SDK 구조를 참고한다: 세션 상태(연결 상태 × 말하기/듣기 모드), 마이크 사전 안내, 레벨 시각화, 텍스트 대체 입력, 서버 발급 단기 토큰.
- 우리 위젯은 Web Component(커스텀 엘리먼트)와 단일 스크립트로 배포하면 외부 사이트에 넣기 쉽다. ElevenLabs도 이 방식이다.
- 공개 위젯이라면 도메인 allowlist와 사용량 제한을 서버에 둔다.

---

## 5. 앱 기술 스택 관찰 [확인]

| 항목 | 관찰 결과 | 방법 |
|---|---|---|
| 프레임워크 | **Next.js 16.4.5**(`window.next.version`), App Router 흔적(`self.__next_f` 있음, `__NEXT_DATA__` 없음), 번들러는 **Turbopack**(`turbopack-*.js` 청크), 정적 자산 경로 `/app_assets/_next/` | 페이지 JS 조회 |
| UI | React, Tailwind식 유틸리티 클래스(`flex flex-col min-h-100dvh bg-background text-foreground`), Radix 계열 속성(`data-state` 등 53개) | DOM |
| 폰트 | `next/font` 방식의 해시 변수 클래스(`*_variable`) | body class |
| API | 브라우저 → `api.us.elevenlabs.io` 직접 fetch(공개 API와 같은 `/v1`, `/v2` 경로 체계에 내부 경로가 섞임). 기능 플래그는 `elevenlabs.io/feature-flags/flags/` | Performance resource |
| 미디어 | 미리듣기 mp3와 화면 영상 mp4를 `storage.googleapis.com`에서 받는다 | `<audio>/<video>` currentSrc |
| 결제·동의·분석 | Stripe(`js.stripe.com`), 쿠키 동의(Cookiebot, Ketch), 다수의 광고·분석 픽셀(GTM, Meta, TikTok, Reddit, LinkedIn, Bing 등) | script 호스트 |
| 기타 | Service Worker 없음, `crossOriginIsolated=false` | JS 조회 |

---

## 6. 우리 프론트 스택 제안 [제안]

| 영역 | 제안 | 이유 |
|---|---|---|
| 프레임워크 | **Next.js(App Router) + TypeScript** | 관찰 대상과 같은 계열이라 구조를 비교하기 쉽다. 토큰 발급·업로드 중계 같은 얇은 서버 경로(Route Handler)를 같은 저장소에 둘 수 있다. |
| UI | Tailwind + Radix 기반 컴포넌트(shadcn/ui 방식) | 접근성 기본기(포커스, 키보드, aria)를 직접 만들 필요가 없다. 디자인은 디자인팀 시안을 따른다. |
| 상태 | 서버 데이터는 TanStack Query, 녹음·재생 상태는 React 내부 상태와 작은 상태 기계(useReducer) | 녹음(대기→권한→녹음→검토→업로드)과 재생(로딩→재생→중단)은 상태 기계로 다루는 편이 버그가 적다. |
| 오디오 | 브라우저 표준 API만 사용: `MediaRecorder`, Web Audio(`AnalyserNode`, `decodeAudioData`, 재생 큐), `<audio>` | 1단계 기능에는 외부 라이브러리가 필요 없다. |
| 에이전트 | 직접 만드는 경우 WebRTC보다 WebSocket과 PCM 큐부터 시작하고, ElevenLabs 연동 시에는 공식 `@elevenlabs/react` 사용 | SDK가 ping/pong, 중단 처리, 장치 처리를 이미 갖고 있다. |
| 패키지 | npm (사내 규칙) | – |

**1단계 PoC 우선순위**
1. 녹음·업로드 검증(권한 오류별 안내, 3분 자동 정지, 10MB·길이 검사)
2. HTTP 스트리밍 재생(서버 중계 + `<audio>`)
3. WS·PCM 재생 큐는 필요할 때 만든다.

---

## 7. 실행 확인 필요 (대표 판단 요청)
1. 즉시 음성 복제 **녹음 버튼 이후 흐름**: 권한 요청 시점과 문구, 녹음 포맷(MIME), 녹음 중 파형, 3분 도달 시 동작. 마이크 녹음 시작이 금지 항목이라 하지 않았다.
2. TTS **생성 결과의 재생 방식**(스트리밍 재생인지, 완성 후 blob 재생인지)과 `/stream` 실제 응답 형식(SSE인지 원시 바이트인지). 생성 버튼을 눌러야 해서(크레딧 차감) 하지 않았다.
3. 업로드 10MB를 넘는 파일이나 5초 미만 파일을 넣었을 때의 클라이언트 검증 문구. 파일 업로드가 금지 항목이라 하지 않았다.

## 8. 다른 팀에 필요한 것
- **백엔드팀**: (a) `/stream`의 SSE·원시 바이트 응답 형식 확인과 브라우저용 `audio/mpeg` 중계 경로, (b) 업로드 파일 서버 검증(10MB, 파일당 5초 이상, 합계 10초~3분)과 MP3 변환, (c) 일회용 토큰 발급 경로(`tts_websocket`, `realtime_scribe`, signed URL) + 사용자 인증과 요청 횟수 제한
- **디자인팀**: 녹음 상태별 화면(권한 안내, 거부, 녹음 중, 검토, 업로드 중, 실패)과 파형·진행 링 시안
- **QA팀**: 브라우저별 녹음 포맷 차이(크롬 webm, 사파리 mp4)와 권한 거부 시나리오

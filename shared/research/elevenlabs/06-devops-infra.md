# 06 DevOps — ElevenLabs 인프라 요구사항·비용 분석 (1단계)

- 작성: 인프라/DevOps팀 · 2026-11-21 (같은 날 §4 재계산, §4.3 고정비 항목표, §4.7 PVC, §5.5 ffmpeg 추가)
- 근거: ElevenLabs 공식 문서(`.md` 원문, 2026-11-21 수집)와 각 클라우드 공식 가격 페이지(2026-11-21 열람). 출처는 항목마다 달았다.
- 이번 작업에서 ElevenLabs 앱 화면은 열지 않았다. 문서로 충분했고, 계정에 영향을 줄 일을 만들지 않으려 했다. 실측이 필요한 항목은 §7 "실행 확인 필요"에 따로 모았다.
- 표기 규칙: **[확인]**은 문서나 가격 페이지에서 직접 본 내용, **[가정]**은 비용 계산을 위해 우리가 정한 값, **[추정]**은 확인한 사실에서 끌어낸 해석이다.

---

## 1. ElevenLabs 운영 특성 (문서에서 확인한 것)

### 1.1 모델별 지연 [확인]
출처: https://elevenlabs.io/docs/overview/models.md , https://elevenlabs.io/docs/eleven-api/concepts/latency-methodology.md

| 모델 | 공개 지연(중앙값) | 측정 기준 | 1회 요청 글자 한도 |
|---|---|---|---|
| Eleven v4 Turbo (`eleven_v4_turbo`) | ~100ms | 서버측(요청 수신~첫 오디오 송신) | 확인 못 함 |
| Flash v2.5 (`eleven_flash_v2_5`) | ~100ms | 서버측 | 40,000 (~40분) |
| Flash v2 (`eleven_flash_v2`) | ~135ms | 서버측 | 30,000 (~30분) |
| v3 Conversational | ~165ms | 서버측 | 확인 못 함 |
| Scribe v2 Realtime (STT) | ~150ms | 확정(committed) 전사까지 걸린 시간 | — |
| Eleven v4 / v3 / Multilingual v2 / Scribe v3 / v2 | 공개 안 함 | "실시간용이 아니라 품질용 모델" | v4 100,000 · v3 5,000 |
| Scribe v3 Live | 아직 공개 안 함 | — | — |

- TTS 수치는 **WebSocket 스트리밍 요청 + 웜 보이스**(한 번 이상 생성에 쓰인 보이스) 기준이다. 네트워크 왕복, LLM 대기, 플레이어 버퍼는 빠져 있다. 2026-10-29 갱신값이다.
- 지연이 커지는 조건: 입력이 길 때, Professional Voice Clone(IVC나 기본 보이스보다 느림), 서버 부하로 큐에서 기다릴 때.
- 사용자가 실제로 느끼는 TTFA(첫 소리까지 시간) = 네트워크 왕복(20~200ms) + 서버 처리(한 자릿수 ms) + 추론 + 플레이어 버퍼(보통 500ms) + 앞단 파이프라인(STT→LLM). 출처: https://elevenlabs.io/docs/eleven-api/concepts/latency.md
- 서빙 클러스터: 북미·유럽·동남아. 요청은 가장 가까운 클러스터로 자동 라우팅된다(같은 문서).
- Flash v2.5는 지연을 줄이려고 숫자·날짜 정규화가 기본으로 꺼져 있다(`apply_text_normalization`, models 문서).

### 1.2 동시 처리 한도 [확인]
출처: https://elevenlabs.io/docs/overview/models.md#concurrency-and-priority

| 플랜 | Multilingual v2 | Flash | STT | 실시간 STT | Music | SFX | TTD WebSocket 세션 | 우선순위 |
|---|---|---|---|---|---|---|---|---|
| Free | 2 | 4 | 8 | 6 | 0 | 4 | 14 | 3 |
| Starter | 3 | 6 | 12 | 9 | 2 | 4 | 21 | 4 |
| Creator | 5 | 10 | 20 | 15 | 2 | 6 | 35 | 5 |
| Pro | 10 | 20 | 40 | 30 | 2 | 6 | 70 | 5 |
| Scale | 15 | 30 | 60 | 45 | 5 | 8 | 105 | 5 |
| Business | 15 | 30 | 60 | 45 | 5 | 8 | 105 | 5 |
| Enterprise | 상향 | 상향 | 상향 | 상향 | 최고 | 상향 | 상향 | 6 |

동시성을 세는 방식. 우리 설계에 그대로 필요한 규칙이다.
- **HTTP**: 요청 하나가 끝날 때까지 슬롯 하나를 쓴다.
- **TTS WebSocket**: 모델이 오디오를 **생성하는 동안만** 슬롯을 쓴다. 연결만 열려 있는 동안은 세지 않는다.
- **Text to Dialogue WebSocket**: 연결 1개가 별도 풀의 세션 1개를 연결이 열려 있는 내내 차지한다. 세션이 다 차면 새 연결은 `too_many_concurrent_requests`로 거부된다.
- **한도를 넘으면** 요청을 거부하지 않고 낮은 우선순위 큐에서 처리한다. 지연은 보통 ~50ms 늘어난다. Enterprise는 한도를 넘어도 처리 여력이 있는 만큼 best-effort로 처리한다.
- 응답 헤더 `current-concurrent-requests`, `maximum-concurrent-requests`로 동시성을 감시할 수 있다.
- 경험칙(ElevenLabs 수치): **동시성 5 ≈ 동시 방송 약 100개**, 슬롯 1개 ≈ 실시간 대화 약 20개. Flash는 같은 플랜에서 동시성이 2배다. 출처: models 문서, https://elevenlabs.io/docs/overview/administration/workspaces/concurrency-estimator.md
- 동시성 추정식(estimator): 평균 = 활성 분당 도착 수 × 평균 길이 × 여유계수(1.0/1.2/1.5), 피크 = 평균 + z·√평균(z = 1.28/1.64/2.33/3.09 → 90/95/99/99.9%). 예시: 하루 2,000통 × 4분, 8시간 주 5일이면 동시 20~28통.

에이전트(음성 통화) 쪽 [확인]
- Burst: 구독 한도의 3배까지(최대 300, Enterprise는 예외) 받는다. 초과분은 2배 요금이고 STT/TTS 우선순위가 낮아진다. https://elevenlabs.io/docs/eleven-agents/guides/burst-pricing.md
- Call queueing: 용량이 차면 대기음을 들려주며 도착 순서대로 연결한다. 대기 시간은 과금하지 않는다. 최대 대기 시간을 넘으면 끊고, WebSocket이면 `queue_status: timed_out` 후 close code 4300을 보낸다. 아웃바운드·배치 콜은 지원하지 않는다. https://elevenlabs.io/docs/eleven-agents/guides/call-queueing.md

### 1.3 스트리밍 방식 [확인]
| 방식 | 엔드포인트 | 특징 |
|---|---|---|
| HTTP chunked 스트리밍 | TTS `/stream`, Voice Changer, Audio Isolation | 텍스트를 한 번에 보내고 오디오 바이트를 chunked transfer로 받는다. https://elevenlabs.io/docs/api-reference/streaming.md |
| TTS WebSocket | `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id=` | 텍스트를 조금씩 보낸다(LLM 토큰을 바로 넘김). `chunk_length_schedule` 기본 [120,160,250,290]자, `flush: true`로 즉시 생성, `auto_mode`. **20초 동안 아무것도 오가지 않으면 자동으로 닫힌다**(공백 `" "` 하나를 보내 유지, 빈 문자열을 보내면 닫힘). https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts.md |
| Multi-context WebSocket | TTS multi-stream-input | 연결당 **컨텍스트 최대 5개**. 끼어들기(barge-in)가 오면 컨텍스트를 닫고 새로 연다. 비활성 타임아웃 기본 20초, 최대 180초. https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/multi-context-web-socket.md |
| Text to Dialogue WebSocket | v4 Turbo, v3 Conversational | 세션 기반 동시성(§1.2), 20초 비활성 시 종료, `keep_alive` |
| 실시간 STT WebSocket | `wss://api.elevenlabs.io/v1/speech-to-text/realtime` | PCM 8~48kHz, μ-law. VAD 또는 수동 commit, `commit_strategy=turn_prediction`(v3 Live) |
| Agent WebSocket / WebRTC | ElevenAgents | 위젯·SDK·직접 WebSocket. Realtime API는 OpenAI Realtime API와 호환된다(models 문서) |
| 브라우저 직결 인증 | `POST /v1/single-use-token/{realtime_scribe|batch_scribe|tts_websocket}` | **15분 만료, 1회용 토큰**. API 키를 클라이언트에 노출하지 않는다. https://elevenlabs.io/docs/api-reference/tokens/create.md |
| 데이터 레지던시 엔드포인트 | `api.{eu,in,sg}.residency.elevenlabs.io` (wss 동일) | 리전마다 완전히 분리된 워크스페이스이고 키도 따로 쓴다. https://elevenlabs.io/docs/overview/administration/data-residency.md |

### 1.4 데이터 보존과 Zero Retention [확인]
출처: https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode.md , agents privacy 문서들

- **기본값**: 보존한다(히스토리 저장). API로 생성물을 지우면 DB에서는 즉시 삭제되지만 디버깅·모더레이션 로그에는 남을 수 있다. **백업은 삭제 후 최대 30일** 보관한다. 계정을 삭제하면 전부 지운다.
- **ZRM(Enterprise 전용)**: API 요청마다 `enable_logging=false`를 붙인다. 입력과 출력은 처리 프로세스 메모리에만 있고 장기 저장 DB로 가지 않는다. 사용 통계에는 요청 사실만 남는다. **웹 UI 트래픽은 대상이 아니다.** ZRM에서는 지원·디버깅이 제한된다.
  - ZRM 가능: TTS(HTTP/WS), Text to Dialogue, Voice Changer, STT, Forced Alignment, Music 생성(`store_for_inpainting=true`는 거부), SFX, ElevenAgents(에이전트별 토글)
  - ZRM 불가: 보이스 클로닝(IVC/PVC, 클론을 저장해야 하므로), Dubbing, Studio, Image & Video(제3자 처리), Music upload/finetune(학습 데이터 30일 보관)
- **에이전트**: 대화 기록과 녹음을 **기본 2년** 보관한다. 일수 지정, `-1` 무제한, `0` 예약 삭제를 고를 수 있다. 녹음 저장은 따로 끌 수 있다. ZRM을 켜면 녹음과 PII가 든 기록을 남기지 않고 결과는 post-call webhook으로만 받는다. ZRM에서 쓸 수 있는 Realtime 모델은 v1 Max뿐이고 US/EU에서만 된다. MCP는 ZRM/HIPAA에서 쓸 수 없다.
- **레지던시**: 기본 저장 위치는 미국이다. EU·인도·싱가포르 분리 환경이 있다(Enterprise). 저장은 해당 리전에서 하지만 처리는 리전 밖에서 일어날 수 있다. EU는 ZRM과 API를 함께 쓰면 처리도 EU로 제한된다.
- **인증**: SOC2, GDPR 정합, HIPAA BAA(자격 있는 의료 고객), 전송 구간 암호화(data-residency 문서).
- **프라이빗 배포**: AWS/GCP 고객 VPC 안에서 Agents 런타임을 돌린다. TTS(v2, v2.5)와 Scribe v2는 SageMaker/Vertex AI 단독 엔드포인트로 배포한다. 문서는 NDA 후 제공한다. https://elevenlabs.io/docs/overview/capabilities/private-deployment.md
  - [추정] ElevenLabs도 저지연 모델(v2/v2.5 계열)은 고객 GPU에 독립 배포가 가능한 크기로 운영한다는 뜻이다. 우리 GPU 풀을 **저지연 모델과 고품질 모델로 나눠** 설계하는 근거로 썼다.

### 1.5 전화(SIP) 사양 [확인]
출처: https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-reference.md

- 시그널링: `sip.rtc.elevenlabs.io`(TCP/TLS), `sip-static.rtc.elevenlabs.io`(UDP/TCP/TLS, UDP는 이 주소만). 포트 5060(UDP/TCP), 5061(TLS). TCP나 TLS를 권장한다(UDP는 MTU 단편화와 LB 문제가 있음). `sips:`는 지원하지 않고 `;transport=tls`로 쓴다. TLS 1.2 이상.
- 미디어: RTP/SRTP UDP **10000–60000**, 주소 대역 **199.88.252.0/24**. 대칭 RTP로 NAT를 대응한다.
- 코덱: G.722(16kHz), PCMU/PCMA(G.711, 8kHz), G.729, AMR, AMR-WB. DTMF는 RFC 4733만 지원한다(SIP INFO와 인밴드는 미지원).
- SRTP: SDES만 지원(DTLS-SRTP와 ZRTP는 미지원). 트렁크마다 Disabled/Allowed/Required를 고른다.
- 인바운드 인증: IP 허용목록 또는 Digest 인증(권장). Digest 챌린지 응답 헤더가 `realm="LiveKit"`이다.
  - [추정] ElevenLabs SIP 계층은 LiveKit SIP 기반으로 보인다. 아래 구성안에서 LiveKit SIP를 1순위 후보로 둔 근거다.
- INVITE에 SDP가 없으면(delayed offer) `488`로 거부한다. 수신 번호는 E.164로 정확히 일치해야 한다(영숫자 문자열도 가능).
- 연동 사업자 문서: Twilio(네이티브), Telnyx, Plivo, Bandwidth, Sinch, Vonage(WebSocket), Exotel, Voximplant 등(eleven-agents 색인).

---

## 2. 우리 구성안 (텍스트 구성도)

```
 [웹/앱 클라이언트]                     [전화망 PSTN]
   │ HTTPS / WSS (1회용 토큰)              │
   ▼                                       ▼
 ┌──────────────────────┐        ┌──────────────────────────┐
 │ Edge/API 게이트웨이     │        │ SIP 트렁크 (Twilio/Telnyx) │
 │ - API 키 인증·범위 검사  │        └────────────┬─────────────┘
 │ - IP 허용목록, 레이트리밋│                     │ SIP(TLS) + SRTP
 │ - 1회용 토큰 발급(15분)  │        ┌────────────▼─────────────┐
 └───┬─────────┬────────┘        │ SIP 게이트웨이 (LiveKit SIP)│
     │REST      │WSS               │ - Digest 인증, 코덱 변환     │
     │          ▼                  │ - RFC4733 DTMF, 녹음 분기    │
     │  ┌──────────────────────┐   └────────────┬─────────────┘
     │  │ 실시간 세션 게이트웨이    │◄──────────────┘ 미디어(PCM 16k)
     │  │ (stateful, CPU)        │
     │  │ - WS 연결·컨텍스트(≤5)   │
     │  │ - 20초 비활성 종료/keepalive│
     │  │ - 동시성 카운터(생성 중만)│
     │  │ - 한도 초과 → 저우선 큐   │
     │  │ - 에이전트 오케스트레이션 │──► 외부 LLM API
     │  └───┬──────────┬───────┘     (STT→LLM→TTS)
     │      │gRPC/스트림 │
     ▼      ▼          ▼
 ┌────────────────┐  ┌──────────────────────────────┐
 │ 작업 큐           │  │ GPU 추론 풀                     │
 │ (배치: 긴 TTS,    │─►│ A. 실시간 풀(웜 상시): 저지연 TTS,  │
 │  더빙, 음악, STT  │  │    실시간 STT  — L4급              │
 │  배치, 클로닝학습) │  │ B. 배치 풀(오토스케일): 고품질 TTS,  │
 │ + DLQ, 재시도     │  │    더빙/음악/SFX/분리 — L40S~A100급 │
 └──────┬─────────┘  └──────────────┬───────────────┘
        │완료 이벤트                    │결과 오디오
        ▼                            ▼
 ┌────────────────┐  ┌──────────────────────────────┐
 │ 웹훅 디스패처      │  │ 객체 저장소 (오디오·샘플·결과)        │
 │ - HMAC 서명       │  │ - 보존기간 수명주기 규칙              │
 │ - 재시도 5회·지터  │  │ - ZRM 요청은 저장 안 함(메모리만)     │
 │ - 자동 비활성화    │  └──────────────────────────────┘
 └────────────────┘
 ┌────────────────────────────────────────────────────────┐
 │ Postgres: 계정·키·권한·사용량·히스토리 메타 / 감사로그(OCSF)    │
 │ 관측: 동시성·TTFA·큐 대기·GPU 사용률·웹훅 실패율 → 알림          │
 └────────────────────────────────────────────────────────┘
```

설계 원칙(§1에서 끌어냄)
1. **실시간 풀과 배치 풀을 나눈다.** 실시간 풀은 웜 보이스 캐시를 둔 상시 가동, 배치 풀은 큐 깊이에 맞춰 오토스케일한다. ElevenLabs도 "실시간 모델"과 "품질 모델"을 나누고 품질 모델의 지연은 공개하지 않는다.
2. **동시성은 "생성 중인 시간"으로 센다.** 한도를 넘으면 거부하지 않고 저우선 큐로 보낸다(ElevenLabs 방식, ~50ms 추가). 에이전트 통화는 burst와 대기열로 처리한다.
3. **WebSocket 게이트웨이는 GPU와 분리한다.** 연결 유지(대부분 유휴)는 싼 CPU에 두고, GPU에는 생성 요청만 보낸다.
4. **ZRM 경로**: `enable_logging=false` 요청은 저장소와 히스토리 DB 쓰기를 건너뛰고 사용량 카운터만 올린다.

---

## 3. 구성요소별 후보 서비스

| 구성요소 | 1순위 후보 | 대안 | 고른 이유 / 비고 |
|---|---|---|---|
| GPU 추론 (실시간 풀) | **[11-21 재계산으로 변경, §4.2]** 해외: RunPod L40S 48GB ($1.09/h) / 한국: Azure 서울 A100 ($4.959/h). L4는 실측 후 후보. 1차안은 RunPod Secure Cloud **L4 24GB** ($0.69/h) | AWS G6(L4) — 가격 페이지에 금액 없음, 확인 못 함 · Lambda A10 ($1.29/h) | 초당 과금, 같은 L4에서 가장 쌌다. 한국 사용자 지연을 줄이려면 아시아 리전 가용성 확인 필요(확인 못 함) |
| GPU 추론 (배치 풀) | RunPod **L40S 48GB** ($1.09/h) / **A100 80GB PCIe** ($2.09/h) | Lambda H100 PCIe ($3.79/h) · RunPod H100 PCIe ($2.89/h) | 엔진이 정해지면 VRAM 요구량에 맞춰 선택 |
| 실시간 WebSocket 게이트웨이 | 자체 서비스(Node/Go) + CPU VM | Cloudflare Workers + Durable Objects | CPU VM 가격은 이번에 확인 못 함 |
| 엣지/API 게이트웨이 | Cloudflare Workers Paid ($5/월 기본, 요청 1천만 포함 후 $0.30/백만) | 자체 Nginx/Envoy | egress 무료 |
| 파일 저장소 | **Cloudflare R2** ($0.015/GB-월, egress 무료) | AWS S3 — 단가 표 확인 못 함 | 오디오 다운로드·스트리밍이 많아 egress 무료가 결정적이다 |
| 작업 큐 | **Cloudflare Queues** (월 100만 오퍼레이션 포함, $0.40/백만, 보존 최대 14일, DLQ) | Redis + BullMQ · AWS SQS(확인 못 함) | 메시지당 3 오퍼레이션(쓰기·읽기·삭제)으로 계산 |
| DB | **Supabase Postgres** Large(전용 2vCPU/8GB, ~$110/월) | Supabase XL(~$210/월) | 플랜 기본료는 확인 못 함 |
| SIP 게이트웨이 | **LiveKit SIP**(오픈소스, 자체 호스팅) | 사업자 Media Streams(Twilio $0.0044/분) | ElevenLabs가 쓰는 것으로 보이는 스택(§1.5) |
| SIP 트렁크 | **Telnyx** (US 인바운드 $0.0032~/분, 아웃바운드 $0.005~/분, 번호 $1~/월) | **Twilio Elastic SIP** (US 인바운드 $0.0034/분, 아웃바운드 $0.0100/분, 번호 $1.15/월) | 국내(한국) 번호·요금은 이번에 확인 못 함 |
| 관측 | 확인 못 함(2단계 선정) | — | 지표: 동시성, TTFA p50/p95, 큐 대기, GPU 사용률, 웹훅 실패율 |

가격 출처: https://www.runpod.io/pricing (2026-11-12 갱신) · https://lambda.com/pricing · https://developers.cloudflare.com/r2/pricing/ · https://developers.cloudflare.com/queues/platform/pricing/ · https://developers.cloudflare.com/workers/platform/pricing/ · https://supabase.com/docs/guides/platform/compute-and-disk · https://www.twilio.com/en-us/sip-trunking/pricing/us (2026-10 기준) · https://www.twilio.com/en-us/voice/pricing/us · https://telnyx.com/pricing/elastic-sip · https://telnyx.com/pricing/numbers

---

## 4. 월 비용 추정 (2026-11-21 재계산: 기획·데이터 물량 + 백엔드 GPU 벤치 + 국내 우선)

계산 스크립트: `06-devops/work/cost_calc.py`(검산 assert 포함). 1차 추정(TTS 1,000만 자, STT 700시간, 에이전트 2만 분 가정)은 이 절로 대체한다.

> **[2026-11-21 갱신] 물량 정본이 안 B(B2B)로 바뀌었다 → §4.9가 현재 기준이다.** §4.1~4.8은 소비자형 물량(MAU 5,000) 기준으로, 단가·방법·근거 참고용으로 남긴다.

### 4.1 입력값
| 입력 | 값 | 근거 |
|---|---|---|
| TTS | 월 1,712만 자 | 기본안(MAU 5,000). `01-planning-feature-map.md` §6-3 = `07-data-metering-kpi.md` §5-3 |
| STT | 월 144시간(배치 전사) | 같은 표. 대표·기획 요청에 따라 1차의 500h+200h 가정은 폐기 |
| 에이전트·실시간 | P0 비용에서 제외 | 에이전트, 실시간 TTS/STT는 P1(기획 §5). §4.5에 별도 추가분으로 둠 |
| 한국어 1분당 글자 수 | 350~1,000자 | 350자는 데이터팀 [가정](07 §9-1), 1,000자는 ElevenLabs 영어 기준(models 문서 글자 한도 표). 실측 전 |
| GPU 처리량 | **공개 벤치마크 값(우리 실측 아님)** | `04-backend-api-engine.md` §6.5. L4 실측은 임대 비용이 들어 사용자 승인 대기 중이며, 이번 계산에서는 하지 않았다 |
| 출시 시장 | 국내 우선 → **한국 리전을 기본**으로 하고 해외와 비교 | 대표 결정(§6-0) |

### 4.2 GPU 필요량 (공개 벤치마크로 계산)
- **TTS**: CosyVoice2-0.5B(L20 1장, 벤더 벤치)에서 가장 느린 값인 스트리밍 동시 1 RTF 0.1228을 썼다. 월 오디오 17,120~48,914분 × 0.1228 = **GPU 최대 약 100시간/월**. 상시 GPU 1장(730시간)의 14% 미만이다.
- **STT**: faster-whisper int8 batch8(RTX 3070 Ti, 벤더 벤치)은 13분 오디오를 16초에 처리한다(약 49배속). 144시간이면 **GPU 약 3시간/월**이다.
- **지연 제약**: CosyVoice2 첫 청크 평균은 동시 1에서 197ms, 동시 4에서 511ms, 동시 10에서 1,215ms다(04 §6.5). 첫 음성 목표를 500ms 안팎으로 잡으면 **GPU 1장당 동시 생성은 3~4개**다.
- **피크 동시 수 [추정]**: 월 GPU 사용 100시간이 하루 12시간에 몰린다고 보면 평균 동시 생성은 약 0.27이다. ElevenLabs 추정식(평균 + 2.33×√평균, 99%)을 쓰면 피크는 약 1.5로, 2개 이하다.
- **결론 [추정]**: 기본안에서 GPU 대수를 정하는 것은 처리량이 아니라 **상시 대기(웜 모델)와 이중화**다. 최소 1장, 이중화하면 2장이다. TTS와 STT는 48GB GPU 한 장에 함께 올리는 안을 기본으로 둔다. Whisper large의 VRAM은 약 10GB, faster-whisper int8은 약 4.5GB다(04 §6.5). CosyVoice의 VRAM은 확인 못 함.
- **GPU 종류**: 벤치마크는 L20(48GB, Ada 세대)에서 잰 값인데, 조회한 어느 사업자에도 L20이 없었다. 대체 후보는 같은 48GB급 **L40S(해외)**와 **A100 80GB(한국, Azure)**다. L4(24GB)는 더 싸지만 이 엔진의 처리량 근거가 없다. 실측이 승인되면 L4 2장 안도 검토한다.
- **주의(04 백엔드 지적)**: 위 RTF와 지연은 L20에서 잰 값이다. L40S·A100에서 그대로 나온다는 보장은 없다. GPU 대수 결론이 "처리량 사용률 14%"라는 큰 여유에 기대고 있어서 방향은 유지되겠지만, 동시 생성 3~4개라는 지연 한도는 실제 GPU에서 다시 재야 한다.
- **CosyVoice VRAM은 확인 못 함**(04 §6.5 끝). 참고로 저장소 파일 크기는 CosyVoice2-0.5B 4.86GB(llm.pt 2.02GB), Fun-CosyVoice3 9.75GB(대체 파일 포함)다. 파일 크기는 VRAM이 아니므로 "48GB 한 장에 TTS+STT 공존"은 [가정]이다. 2단계에서 `max_memory_allocated`로 실측한다.

### 4.3 월 고정비 — 항목별 (인건비 제외, 데이터팀 손익분기 입력용)
단위 USD/월(730시간). 상시 GPU와 서버가 거의 전부이고, 물량에 비례하는 변동비는 작다(§4.4).

| 항목 | **한국 최소** (Azure 서울, A100×1) | 한국 이중화 (A100×2) | 해외 최소 (RunPod L40S×1) | 해외 이중화 (L40S×2) | 해외 L4×2 (실측 후 후보) | 단가·근거 |
|---|---|---|---|---|---|---|
| 상시 GPU | 3,620 | 7,240 | 796 | 1,591 | 1,007 | Azure koreacentral `Standard_NC24ads_A100_v4` $4.959/h · RunPod Secure L40S $1.09/h, L4 $0.69/h |
| 서버 CPU (API·웹 2대 + WebSocket/ffmpeg 워커·모니터링 1대) | 345 | 345 | 280 | 280 | 280 | Azure `D2s_v5` 서울 $0.118/h, 미국 동부 $0.096/h · `D4s_v5` 서울 $0.236/h, 미국 동부 $0.192/h |
| DB (Supabase Large) | 110 | 110 | 110 | 110 | 110 | ~$110/월. 서울 리전 제공 여부와 플랜 기본료는 확인 못 함 |
| 저장소 (R2) | ≤5 | ≤5 | ≤5 | ≤5 | ≤5 | $0.015/GB-월. 증가량은 월 25~56GB(§4.4) |
| 엣지 (Workers Paid) | 5 | 5 | 5 | 5 | 5 | 기본료 $5 |
| 작업 큐 (Queues) | 0 | 0 | 0 | 0 | 0 | 월 100만 오퍼레이션 무료 한도 안(메시지 약 33만 건까지) |
| 모니터링 | 0 (CPU 워커에 자체 설치) | 0 | 0 | 0 | 0 | 유료 SaaS를 쓰면 별도. 단가 확인 못 함 |
| 전화 회선 기본료 | 별도(§4.6) | 별도 | 별도 | 별도 | 별도 | 에이전트가 P1이라 P0에는 없음 |
| **합계** | **~$4,085** | **~$7,705** | **~$1,196** | **~$1,992** | **~$1,408** | `cost_calc.py` |

- **같은 사업자로 비교한 한국 vs 미국** [확인 단가 계산]: Azure A100×1 구성은 서울 $4,085, 미국 동부 $3,082다. 서울이 GPU와 CPU 모두 약 **1.35배** 비싸다(A100 $4.959 vs $3.673, A10 $4.32 vs $3.20, D2s $0.118 vs $0.096).
- **한국 리전 GPU 선택지가 좁다**: 조회 범위에서 서울 가격을 확인한 GPU는 Azure A10·A100뿐이다. AWS 서울(g6/g6e/g5), GCP 서울, 네이버클라우드의 GPU 가격은 페이지에서 숫자를 읽지 못해 확인 못 함. RunPod 가격 페이지에는 한국 리전 언급이 없다. 서울 가격이 확인되면 한국 최소 구성은 내려갈 수 있다.
- **해외 리전에 둘 때 따져야 할 것**: ① 지연 — 네트워크 왕복이 20~200ms 늘어난다(ElevenLabs latency 문서). P0의 배치·HTTP 스트리밍 TTS에는 영향이 작고, P1 실시간 에이전트에는 불리하다. ② 개인정보 국외 이전 — 클로닝 샘플과 녹취를 해외에 저장하면 법적 검토가 필요하다(08 마케팅·법무 확인 필요, 확인 못 함).
- **권고 [추정]**: P0(배치·HTTP 스트리밍 TTS, 파일 STT)는 해외 L40S 이중화(~$2,000)로 시작한다. P1에서 실시간 에이전트를 열 때 한국 리전 GPU를 추가한다. 단, 개인정보 국외 이전이 허용된다는 전제다. 허용되지 않으면 처음부터 한국 이중화(~$7,700)이고, 그때는 서울 L4/L40S급 가격 조사가 먼저다.
- 데이터팀 1차 손익분기(07 §9-2)가 쓴 고정비 $855/$2,230/$4,960은 이 표로 대체된다. 인건비와 LLM은 여전히 빠져 있다.

### 4.4 변동비와 비교 기준
- **변동비(직접 운영)**: GPU 시간은 고정비 안에서 흡수된다(TTS·STT 합계 월 약 103시간). 남는 변동비는 저장 증가분이다. TTS 결과 16~47GB, STT 입력 8.3GB(MP3 128kbps 가정), IVC 샘플 0.5GB를 합쳐 **월 25~56GB, R2 월 $0.4~0.8씩 늘어난다**. egress는 무료다.
- **같은 물량을 ElevenLabs API로 살 때**: TTS 1,712만 자 × $0.04~0.08/1천 자 + STT 144h × $0.20 = **월 $714~1,398**.
- **해석 [추정]**: 기본안 물량에서는 API를 사는 쪽이 가장 싼 직접 운영안(~$1,196)보다도 싸다. 직접 운영이 앞서려면 물량이 고정비를 덮을 만큼 커야 한다. Flash 단가 기준으로 L40S 이중화 고정비 ~$1,992를 덮으려면 대략 TTS 월 4,980만 자 이상이 필요하다($1,992 ÷ $0.04/1천 자). 다만 데이터팀 지적대로(07 §9-3) 우리 판매 단가가 ElevenLabs 원가보다 낮아서 재판매는 역마진이다. 따라서 "초기에는 API로 시작하고 물량이 커지면 직접 운영으로 전환"은 가격안과 함께 대표가 결정할 사항이다.

### 4.5 P1 에이전트 추가분 (별도 항목)
에이전트 물량은 기획 표에 없다. 아래는 1차 가정(월 2만 분, 피크 동시 20통)을 그대로 쓴 참고값이다.
| 항목 | 한국 | 해외 | 근거 |
|---|---|---|---|
| 실시간 TTS GPU 추가 1장 | +$3,620 (A100) | +$796 (L40S) | 피크 20통 × 생성 비중 → 동시 생성 1~2개 [추정, ElevenLabs "슬롯 1 ≈ 대화 20" 경험칙]. 실시간 지연 때문에 한국 리전을 권장 |
| 실시간 STT (상용 API) | +$96 | +$96 | Deepgram Nova-3 $0.0048/분 × 2만 분(04 §6.3, 백엔드 권고: 실시간 한국어는 상용) |
| LLM | 확인 못 함 | 확인 못 함 | 모델 미정 |
| 전화 | §4.6 | §4.6 | — |

### 4.6 국내 전화(SIP) — 별도 항목, 금액 확인 못 함
- 대표 결정에 따라 비용을 따로 둔다. 에이전트 우선순위가 정해진 뒤 결정한다.
- 구성: ① 회선(트렁크) 월 기본료 또는 채널료 ② 번호 월 사용료 ③ 분당 착신·발신 요금 ④ SIP 게이트웨이 서버(위 CPU 워커 1대로 시작 가능).
- **확인 못 함**: Twilio 한국 음성·SIP 요금 페이지는 가격을 브라우저에서 나중에 불러오는 방식이라 숫자를 읽지 못했다. Plivo도 같았다. 국내 통신사(KT, LG U+, SK브로드밴드)의 기업 SIP·070 요금은 공개 페이지를 찾지 못했다. 이번 세션에서는 웹 수집용 서브에이전트가 동시 실행 제한 hook에 걸려 추가 조회를 못 했다. 견적 문의가 필요할 가능성이 높다.
- 참고(미국, 확인): Twilio 번호 $1.15/월, 착신 $0.0034/분 · Telnyx 번호 $1~/월, 착신 $0.0032~/분(§3).

### 4.7 프로페셔널 클로닝(PVC, P2) 학습 GPU 시간 — 1건 기준 추정
공개 자료 중 "학습 데이터 길이 + GPU + 소요 시간"이 함께 적힌 것만 썼다. 우리 엔진(CosyVoice)의 미세조정 소요 시간은 README에 없어 확인 못 함.

| 근거 | 학습 데이터 | 소요 | GPU 시간 | 출처 |
|---|---|---|---|---|
| StyleTTS2 미세조정 | 음성 1시간(약 1천 샘플), 50 epoch | 약 4시간 | **A100 4장 × 4시간 = 16 GPU시간** | https://github.com/yl4579/StyleTTS2 README "Finetuning" |
| XTTS-v2 미세조정(Gradio 데모) | 데이터 길이 미표기 | "최대 40분" | 약 0.7 GPU시간(GPU 종류 미표기) | https://github.com/coqui-ai/TTS `docs/source/models/xtts.md` "Training" |

- **1건 추정**: PVC 샘플은 건당 약 60분(기획 §6-4)으로 StyleTTS2 조건과 같다. **상한 16 A100-시간, 하한 1 GPU시간 미만**으로 범위를 둔다. 비용은 1건에 RunPod A100 $33, Azure 서울 A100 $79(상한 기준)다.
- **월 참고 물량(1/15/128건, 상한 기준)**: GPU 16 / 240 / 2,048시간 → RunPod $33 / $502 / $4,280, Azure 서울 $79 / $1,190 / $10,156.
- 128건이면 GPU 2,048시간으로 상시 GPU 약 3장 분량이다. 학습은 상시 풀이 아니라 **배치 풀에서 필요할 때 빌리는 방식**(학습 대기열)이어야 한다. ElevenLabs의 "대기 포함 3~6시간, 최대 24시간"(기획 §6-4)과도 맞는 운영 방식이다.
- XTTS-v2는 라이선스 판정이 보류된 상태다(04 §6.6). 여기서는 소요 시간 근거로만 썼다.
- **우리 엔진 기준으로는 확인 못 함**(04 회신 2026-11-21): CosyVoice는 제로샷 클로닝이라 기본 흐름에 학습 단계가 없다. 공식 레시피(CV2 GPU 4장, CV3 1장, max_epoch 200)는 데이터셋 전체 학습용이고 소요 시간이 없다. 화자 1명 미세조정 시간은 공개 자료가 없다. 그래서 위 범위는 다른 엔진의 값을 빌린 **참고 추정**이다.
- 비교: ElevenLabs PVC 소요는 문서마다 "약 3~6시간"과 "6~24시간"으로 다르다(대기 제외, 04 회신).
- **대표 결정 사항**: 미세조정형 PVC를 아예 만들지, 제로샷 클로닝 품질로 대신할지. 이미 P2지만, 안 만들기로 하면 학습 대기열과 배치 학습 GPU 비용은 0이다.

---

### 4.8 손익분기 물량에서의 GPU 용량 점검 (07 데이터팀 요청, 2026-11-21)
- 방법: 데이터팀의 손익분기 MAU(07 §9-2 v2)를 기본안 MAU 5,000으로 나눈 배수만큼 TTS·STT 물량을 늘렸다. 나머지는 §4.2와 같은 식이다. 한국어 350자/분(보수적), 하루 12시간 활성 [가정], 피크 = 평균 + 2.33√평균, GPU 1장당 동시 3.5(첫 청크 ~500ms). RTF는 두 값으로 봤다: 0.1228(스트리밍 동시 1, 가장 느림)과 0.0741(동시 4). 모두 **L20 공개 벤치마크**이고, L4·L40S·A100 실측 전이다. 스크립트는 `cost_calc.py`의 `capacity()`다.

| 손익분기 구성 | 물량 배수 | TTS GPU시간/월 | 피크 동시 생성 | 필요 GPU(서비스용) | 이중화 포함 | 판정 |
|---|---|---|---|---|---|---|
| 해외 L4×2 | ×2.9 | 176~292 | 2.1~2.9 | 1 | 2 | **충분**. 단, L4 성능은 실측 전이라 조건부 |
| 해외 이중화 (L40S×2) | ×4.1 | 250~414 | 2.6~3.6 | 1~2 | **2~3** | **경계**. 느린 값 기준이면 2장이 모두 서비스에 들어가 예비가 없다. 이중화를 지키려면 1장 추가(+$796/월) |
| 한국 이중화 (A100×2) | ×16.0 | 966~1,600 | 6.4~9.3 | 2~3 | **3~4** | **부족**. A100 1~2장 추가(+$3,620~7,240/월)가 필요하고, 그만큼 손익분기가 다시 올라간다 |

- STT는 16배에서도 GPU 47시간/월이라 영향이 작다. 배치라서 한가한 시간에 몰아 처리할 수 있다.
- 한국어가 1분당 1,000자에 가까우면 GPU 시간과 피크는 약 1/3로 줄어 위 판정이 한 단계씩 좋아진다.
- [추정] 처리량(GPU시간)보다 **피크 동시 생성 수와 첫 음성 지연 한도**가 먼저 걸린다. 지연 목표를 완화하거나(예: 첫 청크 1초 → 동시 8~10개) 배치·스트리밍 GPU를 나누면 대수가 줄 수 있다.

### 4.9 [현재 기준] 안 B 물량 재계산 — 에이전트·녹취 STT·고품질 TTS (2026-11-21)
입력은 `01-planning-feature-map.md` §6-0(정본, 마케팅 08 §5 기반, 모두 추정)이다. 계산은 `cost_calc.py`의 `plan_b()`(assert 검산)다. GPU 수치는 전부 **L20 공개 벤치마크**이고 실측 전이다(L4 실측은 사용자 승인 대기).

**입력 물량(월)**
| 시점·안 | 에이전트(분) | STT 녹취(시간, 상한) | 고품질 TTS(자) | 피크 동시 통화 |
|---|---|---|---|---|
| 3개월 보수 | 12,000 | 1,127 | 270만 | 5 |
| **3개월 기본** | **156,000** | **14,651** | **2,146만** | **29** |
| 3개월 낙관 | 336,000 | 31,556 | 4,742만 | 55 |
| 12개월 기본 | 480,000 | 45,080 | 6,438만 | 75 |
| 12개월 낙관 | 1,080,000 | 101,430 | 1억 4,081만 | 155 |

**사이징 방법**
- **실시간 풀(에이전트 TTS, 상시)**: 동시 생성 기대값 = 피크 동시 통화 × 에이전트 발화 비중 0.5 × RTF 0.1228이다. 발화 비중은 ElevenLabs 스케일 테스트 패턴(사용자 10초 발화 / 오디오 10초 재생, models 문서)에서 가져왔다. 피크 = 기대값 + 2.33√기대값, GPU 1장당 동시 3.5(첫 청크 ~500ms), 여기에 **예비 1장**을 더했다. 지연 때문에 **한국 리전을 권장**한다.
- **배치 풀(고품질 TTS + 녹취 STT)**: GPU시간 = TTS(350자/분, RTF 0.0741) + STT(faster-whisper 약 49배속)이다. 하루 24시간 큐로 돌리고 목표 사용률 70%로 대수를 정했다. 지연에 민감하지 않아 해외에 둘 수 있다(국외 이전이 허용될 때).
- **실시간 STT**: 상용 API를 쓴다(백엔드 권고). Deepgram Nova-3 $0.0048/분 × 에이전트 분.
- **SIP 게이트웨이**: CPU `D4s_v5` 1대당 동시 50통 [가정. LiveKit SIP 사이징은 확인 못 함].
- **저장**: 녹취를 MP3 128kbps로 30일 보관한다고 [가정]하면 상시 보관량은 월 처리량과 같다.

**결과 (USD/월, 인건비·LLM 제외)**
| 시점·안 | 실시간 GPU(예비 포함) | 배치 GPU (GPU시간) | SIP VM | 저장 | **고정비: 전부 한국** (Azure 서울 A100) | **고정비: 혼합** (실시간 한국 + 배치 해외 L40S) | **고정비: 전부 해외** (L40S) | 변동비 (실시간 STT + 전화*) | 비교: ElevenLabs API (+LLM) |
|---|---|---|---|---|---|---|---|---|---|
| 3개월 보수 | 2 | 1 (33h) | 1 | 72GB | 11,493 | 8,669 | 2,924 | 98 | 1,401 |
| **3개월 기본** | **3** | **1 (376h)** | **1** | **903GB** | **15,126** | **12,301** | **3,732** | **1,279** | **17,127** |
| 3개월 낙관 | 4 | 2 (815h) | 2 | 1.9TB | 22,554 | 16,905 | 5,479 | 2,755 | 36,985 |
| 12개월 기본 | 4 | 3 (1,152h) | 2 | 2.8TB | 26,186 | 17,713 | 6,287 | 3,936 | 52,566 |
| 12개월 낙관 | 6 | 6 (2,577h) | 4 | 6.2TB | 44,683 | 27,737 | 10,598 | 8,856 | 117,951 |

\* 전화 단가는 국내 요금을 확인 못 해 Twilio 미국 착신 $0.0034/분을 참고로 넣었다(§4.6). ElevenLabs API 비교값은 고품질 TTS $0.08/1천 자 + STT $0.20/h + 에이전트 $0.08/분이고, 전화와 LLM은 양쪽 다 별도다.

**실시간 GPU 대수 차이 정리 (07 데이터팀 §9-5와 비교, 2026-11-21)**
3개월 기본 기준으로 데이터팀은 1장, DevOps는 3장이다. 동시 생성 평균은 양쪽 모두 1.78(= 29통 × 0.5 × 0.1228)이다. 차이는 아래 두 가지에서만 난다.

| 안 | 계산 | 장수 | 피크 시간대에 첫 음성 ~500ms를 넘는 비율 | 장애 시 |
|---|---|---|---|---|
| A. 평균만 덮음 (07) | 1.78 ÷ 3.5 → 1 | 1 | 약 10% (동시 4개 이상일 확률, 이항분포 n=29, p=0.0614) | GPU 1장이 멈추면 통화 전부 중단 |
| B. 99% 피크 덮음 | 이항분포 99% 분위 = 동시 5 → ÷3.5 → 2 | 2 | 약 1% | 1장 장애 시 절반 용량 |
| **C. B + 예비 1 (06 권고)** | 2 + 1 | **3** | 약 1% | 1장이 멈춰도 99% 수준 유지 |

- 정규근사(평균 + 2.33√평균 = 4.9)와 이항분포 정확값(99% 분위 5)이 같은 답을 낸다. 피크 29통일 때 동시 생성이 4개 이상인 확률은 9.9%, 5개 이상은 3.0%다.
- 장당 비용은 해외 L40S $796, 한국 A100 $3,620이다. A → C는 해외 +$1,592, 한국 +$7,240이다.
- 몇 안을 쓸지는 서비스 품질 목표(SLA)를 정하는 **대표 결정 사항**이다. DevOps 권고는 C다(전화 상담은 끊기면 바로 고객 피해). 데이터팀 손익 계산에도 같은 안을 쓰도록 맞춘다.

**해석 [추정]**
1. **소비자형(§4.3)과 결론이 뒤집힌다.** 안 B 물량(3개월 기본)이면 직접 운영(고정비 + 변동비)이 ElevenLabs API 구매($17,127+LLM)보다 싸다. 전부 해외 약 $5,000, 혼합 약 $13,600, 전부 한국 약 $16,400이다. 차이를 만드는 것은 에이전트($0.08/분 × 15.6만 분 = $12,480)와 녹취 STT($2,930)다.
2. **비용을 좌우하는 것은 한국 리전 GPU 단가다.** 서울 A100($3,620/장)이 해외 L40S($796/장)의 4.5배라서 "전부 한국"은 해외의 약 4배다. 서울 리전 L4/L40S 가격(AWS·GCP·국내 클라우드)을 확보하는 것이 가장 큰 절감 지렛대다. 지금은 확인 못 함.
3. **권고**: 실시간(에이전트)만 한국에 두고 배치는 해외에 두는 **혼합안**이다. 단, 녹취를 해외에서 처리해도 되는지(개인정보 국외 이전) 법무 확인이 먼저다. 허용되지 않으면 전부 한국안이다.
4. **녹취 STT는 상한 가정이다**(전량 전사). 녹취 저장은 3개월 기본에서 월 약 0.9TB씩 생기므로 보관 기간 정책이 필요하다. 30일 보관이면 R2 약 $14/월로 작다. 다만 녹취는 개인정보라 암호화와 삭제 정책이 비용보다 중요하다.
5. **불확실성**: 시간대 몰림이 빠져 있어 실제 피크가 더 크면 실시간 GPU가 는다(기획 §6-0 주의). L20 → A100/L40S 환산, 한국어 낭독 속도, SIP VM 사이징 모두 실측 전이다.
6. LLM 비용은 에이전트 분당 비용에서 가장 클 수 있는데 모델이 정해지지 않아 확인 못 함이다. 에이전트 손익은 LLM 단가가 들어와야 완성된다.

## 5. 보안 요구사항 (ElevenLabs 수준을 기준선으로)

### 5.1 API 키 [확인 → 요구사항]
출처: https://elevenlabs.io/docs/overview/administration/workspaces/api-keys.md , service-accounts.md , best-practices/security.md , https://elevenlabs.io/docs/api-reference/service-accounts/api-keys/create.md
- 키 종류 두 가지: **사용자 키**(개인 권한 상속, 만료 15분~30일 또는 무기한)와 **서비스 계정 키**(멤버 변동과 무관, 만료 없음, 운영용).
- 키마다 제한 3가지: **엔드포인트 범위(scope)**, **크레딧 한도**, **IP 허용목록**(공인 IPv4/IPv6/CIDR 1~100개, 사설 대역 불가, 위반 시 403).
- 범위 목록(ElevenLabs 실제 값, 우리 권한 모델 초안으로 쓴다): `text_to_speech`, `speech_to_speech`, `speech_to_text`, `voices_read/write`, `voice_collections_read/write`, `models_read/write`, `projects_read/write`, `dubbing_read/write`, `audio_native_read/write`, `pronunciation_dictionaries_read/write`, `speech_history_read/write`, `convai_read/write`, `agents_environment_variables_write`, `user_read/write`, `workspace_read/write`, `workspace_members_read`, `workspace_analytics_full_read`, `webhooks_write`, `service_account_write`, `audit_log_read`
- 교체(rotation): 새 키를 만들고 → 앱을 전환하고 → 옛 키를 삭제한다. 권한은 그대로 복사한다.
- 유출 대응: GitHub secret scanning 파트너로 공개 저장소에 올라간 키는 자동 비활성화(`disable_reason: exposed_publicly`). 키 소유자가 스스로 끄는 엔드포인트(`api_key_name=self`). `third_party_disable_allowed` 정책(Enterprise 기본 off). 비활성화되면 소유자에게 메일을 보낸다.
- 환경 분리: 운영·테스트·UAT마다 서비스 계정을 따로 둔다. 보이스 같은 리소스는 백엔드에서 `user_id | voice_id | permission_level` 단위로 권한을 검사한다.
- 브라우저와 앱에는 키 대신 **1회용 토큰**(15분)을 준다.
- **우리 요구사항**: 키는 해시로만 저장한다. 범위, 크레딧 한도, IP 허용목록, 만료를 1단계부터 지원한다. 키 접두어를 정해 secret scanning 패턴을 등록한다. 키 사용 기록은 감사로그로 남긴다.

### 5.2 웹훅 [확인 → 요구사항]
출처: https://elevenlabs.io/docs/eleven-api/resources/webhooks.md , https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks.md
- 서명: `ElevenLabs-Signature` 헤더의 **HMAC**. SDK의 `constructEvent`/`construct_event`가 서명 검증과 **타임스탬프 검증**을 함께 한다. 서명 문자열 형식과 허용 시간 오차는 문서에 없어 확인 못 함. 검증하려면 원문 body(raw)를 보존해야 한다.
- 추가 방어: 사용자 지정 헤더(HMAC과 함께 전송), 발신 고정 IP 허용목록.
- 재시도(웹훅별로 켬, 기본 꺼짐): 최대 5회 — 즉시 / 30초 / 2분 / 8분 / 30분, 지터 ≤10%. 재시도하는 오류는 5xx, 429, 408, 연결 오류뿐이고 그 외 4xx는 재시도하지 않는다. 웹훅당 대기 재시도는 100건까지. 오디오 페이로드가 50MiB를 넘으면 재시도하지 않고, 오디오 재시도 합계는 400MiB까지.
- 자동 비활성화: 연속 실패 10회 이상 **이고** 마지막 성공이 7일보다 오래됐거나 성공한 적이 없으면 끄고, 관리자에게 메일을 보낸다.
- 재전송 페이로드가 원본과 같으므로 수신측은 **멱등(idempotent)**으로 처리해야 한다.
- 이벤트: `post_call_transcription`, `post_call_audio`, `call_initiation_failure`, `voice_removal_notice(_withdrawn)`, `voice_removed`, `flows_generation`, `flows_template_run`, STT 비동기 완료.
- **우리 요구사항**: 발신측은 HMAC-SHA256 + 타임스탬프 서명, 위와 같은 재시도 스케줄과 DLQ, 자동 비활성화, 이벤트 ID(중복 제거용)를 갖춘다.

### 5.3 감사 로그 [확인 → 요구사항]
출처: https://elevenlabs.io/docs/overview/administration/workspaces/audit-logs.md
- Enterprise 전용, `audit_log_read` 권한, `GET /v1/workspace/audit-logs`. 사용자당 30회/분, 1회 최대 100건.
- **OCSF v1.6.0** 스키마(datetime, host 프로필). 클래스: Account Change(3001), Authentication(3002), Entity Management(3004), User Access Management(3005), Group Management(3006). 엔드포인트 100개 이상을 다룬다.
- URL이나 쿼리에 든 비밀값(예: 비밀번호 재설정 토큰)은 기록 전에 가린다.
- **우리 요구사항**: 처음부터 OCSF 형태로 적재해 SIEM에 그대로 넣을 수 있게 한다. 기록 대상은 키 생성·삭제·범위 변경, 멤버·권한 변경, 로그인, 웹훅 설정, 보존 설정 변경. 감사로그는 추가만 가능하게(append-only) 하고, 감사로그 자체의 보존 기간은 2단계에서 정한다.

### 5.4 데이터 보호
- 기본 보존과 삭제 API, 백업 30일 만료, 에이전트 대화 보존기간 설정(기본 2년), 녹음 저장 끄기, 기록 내 개인정보 자동 가림(redaction) 문서 존재(색인에서 확인, 본문은 안 읽음).
- ZRM과 같은 경로(§2 원칙 4)를 엔터프라이즈 기능으로 설계에 넣는다.
- 클로닝 샘플은 ZRM 대상이 될 수 없다(저장이 필수). 암호화 저장, 접근 통제, 삭제 시 즉시 파기가 필요하다.
- SIP: TLS와 SRTP(Required 옵션), Digest 인증 권장.

### 5.5 ffmpeg 격리 워커와 빌드 라이선스 (04 백엔드 §8.2 요청 회신)
출처: https://ffmpeg.org/legal.html (법률 자문 아님)
- [확인] FFmpeg 기본 라이선스는 **LGPL 2.1 이상**이다. GPL 부품을 켜면(`--enable-gpl`) FFmpeg **전체가 GPL**이 된다. `--enable-nonfree`는 별도 문제다. 상용 라이선스는 돈을 내도 없다. LAME(`libmp3lame`)은 LGPL이고, FFmpeg에 넣으면 같은 LGPL 준수 항목을 거친다.
- [확인] FFmpeg 체크리스트의 소스 공개·고지 의무는 **바이너리를 배포할 때** 기준으로 적혀 있다.
- [추정] 우리는 서버에서 `ffmpeg` 실행 파일을 별도 프로세스로 돌리기만 하고 배포하지 않는다. 그래서 배포 의무가 생기지 않을 가능성이 높다. 그래도 아래 기준을 지킨다.
  1. 빌드는 `--enable-gpl`, `--enable-nonfree` 없이 **LGPL 빌드**로 하고 `--enable-libmp3lame`만 켠다. 필요한 코덱은 오디오(mp3, aac 디코드, opus 디코드, wav)뿐이다.
  2. 우리 코드는 FFmpeg 라이브러리에 링크하지 않고 CLI를 프로세스로 호출한다. 백엔드 §8.2 설계와 같다.
  3. 빌드 설정(configure 줄)과 소스 버전을 저장소에 기록한다. 온프레미스 설치판이나 SDK처럼 나중에 배포하게 되면 LGPL 체크리스트를 그대로 적용한다.
  4. 격리: 컨테이너 1회용 실행, 네트워크 차단, CPU·메모리·시간 제한(백엔드 제안 30초), 읽기 전용 루트 파일시스템, 비루트 사용자. 입력은 임시 볼륨에만 둔다. 이 워커는 §4.3의 CPU 워커(D4s급)에서 돌린다.
- 최종 판단은 법무 검토가 필요하다(확인 못 함).

---

## 6-0. 대표 잠정 결정 (2026-11-21, MVP 범위 확정 때 다시 봄)
1. **한국 리전을 기본 전제로 한다.** 비용표를 갱신할 때 해외 리전 비용과 나란히 제시한다. **국내 SIP**는 에이전트 기능 우선순위가 정해진 뒤 결정하므로 비용을 별도 항목으로 분리한다.
2. **엔터프라이즈 기능(SSO, 감사 로그, 서비스 계정, 그룹 권한)은 MVP에서 제외(P2).** §5.1의 서비스 계정, §5.3의 감사 로그 요구사항은 P2로 미룬다. 단, 나중에 붙이기 쉽도록 MVP 설계에서 막히지 않게만 한다.
3. 갱신 조건: 04 백엔드 GPU 처리량과 01/07 초기 물량이 들어오면 §4 비용표를 다시 계산한다(대표가 각 팀에 요청함). → **2026-11-21 반영 완료(§4)**. 출시 시장은 국내 우선(대표 잠정 결정)이다.

## 6. 다른 팀에 필요한 것 / 요청 사항
- **04 백엔드**: CosyVoice VRAM과 미세조정 시간은 공개 자료가 없다고 회신받았다(2026-11-21). 2단계에서 실측한다(VRAM, L4·L40S의 RTF와 첫 청크 지연). 실측은 사용자 승인 대기다.
- **01 기획 / 07 데이터**: 마케팅 B2B 고객당 물량으로 다시 산정한 값(TTS 자, STT 시간, 통화 분, **피크 동시 통화 수**). 받으면 `cost_calc.py` 입력만 바꿔 다시 계산한다. 07 데이터는 §4.3 고정비 표를 손익분기 입력으로 쓴다.
- **08 마케팅 / 법무**: 클로닝 샘플·녹취의 해외 리전 저장(개인정보 국외 이전) 허용 여부. §4.3 한국·해외 리전 선택을 좌우한다.
- **대표**: ① P0를 해외 GPU로 시작할지, 처음부터 한국 리전으로 갈지(§4.3 권고) ② 초기에는 ElevenLabs 등 외부 API로 시작할지(§4.4) ③ 국내 SIP 견적 문의를 진행할지(§4.6)

## 7. 확인 못 한 것 / 실행 확인 필요
- **실행 확인 필요(크레딧 차감이라 하지 않음)**: 실제 TTFA 측정(한국 → ElevenLabs), 응답 헤더 `current-concurrent-requests` 실측, 웹훅 서명 문자열 형식 실물 확인.
- **실측 안 함(사용자 승인 대기)**: L4 GPU 처리량. §4의 GPU 수치는 모두 **공개 벤치마크(벤더가 L20, RTX 3070 Ti에서 잰 값)**다.
- 확인 못 함: AWS G6/G5(서울 포함)와 S3 단가, GCP·네이버클라우드 GPU 단가, 서울 리전 L4/L40S 가격, LLM 단가, Supabase 플랜 기본료와 서울 리전, 국내 SIP·전화번호 요금, CosyVoice VRAM과 미세조정 시간, 한국어 1분당 글자 수, v4 Turbo·v3 Conversational 글자 한도, 웹훅 타임스탬프 허용 오차. 1차 때 "확인 못 함"이던 CPU VM 단가는 Azure Retail Prices API로 확인했다.
- 앱 화면(`/app/developers`, `/app/subscription`)은 열지 않았다. 문서로 확인한 범위를 넘는 화면 정보는 없다.

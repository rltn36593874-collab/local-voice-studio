# 사내 음성 도구 — 웹 화면 (v0.1.0 · 2026-11-22 · 03-frontend)

대표 1명이 이 PC 브라우저로 쓰는 로컬 도구의 화면 뼈대.
- 계획 문서: `shared/research/elevenlabs/03-frontend-internal-plan.md`
- API 계약: `shared/research/elevenlabs/04-backend-local-api.md` §3 (합의 완료)

## 실행 (npm)
```
npm install
npm run dev        # mock 데이터로 실행 → http://127.0.0.1:5173
npm run dev:real   # 백엔드(127.0.0.1:8000)에 연결. /api를 프록시한다
npm test           # 검증 규칙 테스트(node --test)
npm run build      # dist/ 생성
npm run sync-design  # 디자인 시안(02-design/work/mockup) CSS를 src/design.css로 다시 복사
```
- dev 서버는 쓸 때만 켜고, 다 쓰면 끈다(Ctrl+C). 꺼졌는지는 `netstat -ano | findstr :5173`로 확인한다.

## 구조
| 경로 | 내용 |
|---|---|
| `src/App.jsx` | 셸(왼쪽 메뉴, 상단 바, 작업 서랍, 토스트, 사용량 배너)과 해시 라우팅 5화면 |
| `src/pages/` | ① Tts ② Transcribe ③ Briefing ④ Clone ⑤ History |
| `src/components/` | Recorder(녹음 S0~S2), SampleList(드롭존·샘플·합계), JobCard(진행률·대기열), ResultCard(재생·AI 배지), SpeechMaker(①③ 공용) |
| `src/lib/api.js` | 실서버 호출. 기본은 mock(`VITE_API=real`이 아니면 mock) |
| `src/lib/mock.js` | 계약과 같은 모양의 가짜 서버. 줄(cpu/llm)마다 순차 처리. 텍스트에 '실패'가 들어가면 그 작업이 실패한다 |
| `src/lib/rules.js` | 샘플 규칙(10MB·5초·10초~3분), 사용량 단계, 날짜 계산 |
| `src/design.css` | 디자인 시안 복사본. 손으로 고치지 않는다 |
| `src/styles.css` | 구현에서만 필요한 작은 규칙 |

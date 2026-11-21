# MM5050SE 홍보 영상 2단계 — C안 대본 + Flow 프롬프트
작성: 08-marketing · 2026-11-21 · 근거: `08-product-brief.md`, `09-legal-claims.md`, 사용자 확정안(directives 2단계)
**아직 생성·다운로드 안 함.**

---
## 1. Flow 기능 확인 결과 (2026-11-21 23:0x, 사용자 크롬 사용자 계정, 화면만 봄)
확인한 프로젝트: https://flow.google.com/project/3f0cb80d-5b45-472d-b95e-83e6d02146bc (확인용으로 빈 프로젝트 1개와 빈 장면 1개를 만들었다. 생성 버튼은 누르지 않았다)

| 항목 | 확인 결과 |
|---|---|
| 크레딧 | **무료, 하루 50 크레딧**(매일 오후 11:03 갱신). 계정 메뉴 "Google Flow 크레딧 50개 / 업그레이드" |
| 워터마크 | "거주 중인 지역에서는 워터마크 표시가 필수" → 끌 수 없음 |
| 동영상 모델 | Omni 1.2 Flash, Omni 1.1 Flash, **Veo 3.1 Lite**(기본값), Veo 3.1 Fast, Veo 3.1 Quality. Omni 1.1·Veo Fast·Quality는 "12월 5일 지원 중단 예정" |
| 클립 길이·비용 | **Veo 3.1 Lite: 720p·8초, 1개에 10 크레딧**(길이 조절 없음). **Omni 1.2 Flash: 길이 3~10초 슬라이더**, 360p는 8초에 8 크레딧(초당 1), 720p는 3초 9·10초 30 크레딧(초당 3) |
| 9:16 | **지원**(동영상 16:9 / 9:16 선택) |
| 참고 이미지 | 동영상 모드에 **"프레임"(시작·끝 이미지)**과 **"소재"(참고 이미지)** 두 방식이 있다. 업로드 메뉴도 있다. 실제로 이미지를 넣어 보지는 않았다 |
| 음성·대사·음악 | 설정에 "무음 동영상 반환" 끄기·켜기가 있다(기본 꺼짐) → 기본은 **소리가 있는 영상**으로 보인다. 한국어 대사 품질과 음악 지정이 되는지는 **확인 못 함**(생성해 봐야 앎). 상단에 별도 메뉴 "Flow Music"이 있다(열어 보지 않음) |
| 장면(이어 붙이기) | 새 장면 편집기가 있다: 타임라인(0~20초 눈금), 클립 추가(프로젝트 영상 또는 업로드), "수정할 클립 선택" + Veo 3.1 Lite 수정, 장면 전체 다운로드 버튼. **extend(연장)가 무료 계정에서 되는지는 확인 못 함** — 클립이 있어야 메뉴가 보인다 |
| 한국어 자막·글자 넣기 | 장면 편집기·메뉴에서 **텍스트/자막 기능을 찾지 못함.** 영상 위에 글자를 얹을 방법이 Flow 안에는 없다 |
| 이미지 생성(참고) | Flow 안 이미지(Nano Banana 2.1)는 "0 크레딧"으로 표시됐다. 하지만 대전제에 따라 이미지는 gemini.google.com에서 만든다 |

### 이 결과로 생기는 제약
1. **크레딧**: 15~20초를 720p로 만들려면 Veo 3.1 Lite 8초 × 2개 = 20 크레딧이 든다. 다시 뽑기(컷당 최대 2회)를 포함해도 **최대 40 크레딧이라 하루 안에 가능**하다. Omni 720p는 10초 × 2 = 60 크레딧이라 하루 한도를 넘는다 → **Veo 3.1 Lite를 쓴다.**
2. **음성·음악 연속성**: 한 번에 만들 수 있는 길이가 8초(Veo Lite)라 최소 2번 생성해야 한다. 따로 만든 클립은 **목소리와 음악이 같다는 보장이 없다**(아래 3절).
3. **한국어 자막**: Flow 안에 자막 도구가 없다. 다른 편집 툴은 쓰지 않는다는 조건이라 **영상 위에 자막을 얹을 수 없다**(아래 4절).

---
## 2. 대본 (16초, 세로 9:16, 2클립)
| # | 시간 | 화면 | 내레이션 | 화면 글자 | 소리 |
|---|---|---|---|---|---|
| 1 | 0–8s | 밝은 아침 헬스장. 50대 여성이 가파른 경사의 MM5050SE 위를 손잡이를 잡고 힘차게 걸어 오른다. 카메라가 옆 전경(가파른 데크가 보이게)에서 다리 쪽으로 천천히 다가간다. 뒤에는 다른 기구와 회원들이 흐릿하게 보인다 | "센터에 등산을 들이세요. 최대 오십 퍼센트 경사, 디랙스 마이마운틴." (27자, 약 6초) | 없음 | 밝은 어쿠스틱 팝 시작 |
| 2 | 8–16s | 카메라가 여성 뒤쪽 위로 올라가면, 헬스장 천장과 벽이 열리듯 사라지고 햇살 가득한 산 정상과 구름 바다가 펼쳐진다. 여성은 정상에 선 듯 가볍게 두 팔을 든다. 마지막 2초는 엔드카드로 이어진다 | 없음(추천) — 대안은 3절 | 끝 장면(엔드카드 이미지): **짐링크 / 디랙스 정품 판매·설치 / 010-2760-3659 / DM 견적 문의** / 작게 "AI 생성 연출 영상 포함" | 음악이 크게 올라가 마무리 |

- 법무 판정을 따랐다: 최저가·2배·1/2 문구는 쓰지 않는다. "디랙스 정품 판매·설치"는 정품 매입 증빙이 있어야 한다(사용자 확인 항목). 사양은 "최대 50% 경사"만 쓴다. 데크가 움직이는 장면은 없다(처음부터 경사진 상태로만 보여 준다).
- 로고는 만들지 않는다(대표 지시). 엔드카드는 글자만 쓴다.
- 음악 방향: 밝고 경쾌한 어쿠스틱 팝, **약 118 BPM, 장조**. 어쿠스틱 기타 스트럼, 손뼉, 가벼운 킥·셰이커를 쓴다. 2클립 시작점(8초)에서 심벌 스웰과 함께 크게 올라간다.
- 목소리 묘사(두 클립에 똑같이 고정): "a warm, bright, confident Korean female narrator in her 30s, clear standard Seoul accent, upbeat pace"

---
## 3. 음성·음악 연속성 계획
| 안 | 방법 | 장점 | 단점 |
|---|---|---|---|
| **① 추천: 내레이션은 1클립에만** | 내레이션은 1클립(0~8초) 안에서 끝낸다. 2클립은 음악 + 장면 전환만 넣는다. 음악 묘사(장르·BPM·악기)는 두 프롬프트에 똑같이 적는다. 8초 컷을 "산 정상이 열리는" 순간에 맞춰 음악이 바뀌어도 의도한 전환처럼 들리게 한다 | 목소리가 한 번만 나와 **목소리가 바뀌는 문제는 없다** | 음악은 두 클립에서 다를 수 있다(전환 순간이라 덜 튄다) |
| ② extend로 이어 만들기 | 1클립을 만든 뒤 장면 편집기에서 연장(extend)으로 2클립을 만든다 | 앞 클립의 소리를 이어 받을 가능성이 가장 높다 | 무료 계정에서 되는지 **확인 못 함**. 한 번 시도해 봐야 안다 |
| ③ 2클립 모두 내레이션 | 목소리 묘사를 고정하고 두 클립에 내레이션을 나눠 넣는다 | 내레이션 분량이 늘어난다 | **목소리가 바뀔 위험이 크다**(사용자 요구와 충돌) |
| ④ 업그레이드 | Google AI 유료 요금제(사용자 구독 결정) | 더 긴 클립·연장으로 한 번에 만들 수 있을 가능성(제3자 자료 기준, Flow 화면에서 확인 못 함) | 비용이 든다. 사용자 결정 사항 |

진행 순서(추천): 먼저 ②(extend)가 되는지 본다. 되면 ②로 만들고, 안 되면 ①로 만든다.

---
## 4. 한국어 자막·엔드카드 글자 처리 (Flow에 자막 도구 없음)
1. **엔드카드 글자**: gemini.google.com에서 9:16 엔드카드 이미지를 만든다(아래 5-0). 이 이미지를 2클립의 **"프레임" 끝 이미지**로 넣어, 영상이 엔드카드 화면으로 끝나게 한다. 글자가 깨졌는지 사람이 확인한다.
2. **내레이션 자막**: Flow 안에서 넣을 방법이 없다. 대신 업로드할 때 플랫폼 자막 기능을 쓰는 것을 제안한다(인스타 릴스 자동 자막, 유튜브 자막). 다른 편집 툴이 아니라 업로드 화면의 기능이다 → **사용자 결정 필요**
3. Veo에 화면 글자를 직접 그리게 하는 방법은 한글이 깨질 위험이 커서 쓰지 않는다.
4. "AI 생성 연출 영상 포함" 표시는 엔드카드 이미지에 작게 넣고, 게시물 본문에도 쓴다. 업로드할 때 AI 라벨을 켠다(법무).

---
## 5. 프롬프트

### 5-0. 엔드카드 이미지 — gemini.google.com
**영문**
```
Vertical 9:16 end card for a fitness equipment ad. Background: a bright sunlit mountain summit above a sea of clouds, soft morning light, with a deep navy blue gradient panel across the lower half. Korean text, large bold white sans-serif, centered, exactly as written:
line 1 (largest): 짐링크
line 2: 디랙스 정품 판매·설치
line 3 (inside a rounded sky-blue button, navy text): 010-2760-3659
line 4: DM 견적 문의
At the very bottom, very small light grey text: AI 생성 연출 영상 포함
No logo, no other text, no people. Clean, bright, modern.
```
**한글 설명**: 위쪽은 해 뜨는 산 정상과 구름 바다, 아래 절반은 짐링크 네이비 그라데이션이다. 흰 굵은 글씨로 "짐링크 / 디랙스 정품 판매·설치 / 하늘색 버튼 안 010-2760-3659 / DM 견적 문의"를 넣고, 맨 아래에 작게 "AI 생성 연출 영상 포함"을 넣는다. 로고와 사람은 없다.
※ 전화번호 숫자와 한글이 정확한지 한 글자씩 대조한다. 틀리면 다시 만든다.

### 5-1. 참고 이미지 — 제품 사진
- 짐링크 IG 게시물(https://www.instagram.com/gymlink_official/p/DfzKkWHoDMA/) 1번 슬라이드의 MM5050SE 제품 사진을 쓴다. 저장 위치는 `08-marketing/work/mm5050se/ref/`다(다운로드 승인 뒤).
- Flow "소재"에 올려 1클립을 만든다.

### 5-2. 1클립 (0–8s) — Veo 3.1 Lite · 9:16 · 소재(제품 사진)
**영문**
```
Vertical 9:16, 8 seconds, one continuous shot. A bright, modern fitness center in the morning, large windows, clean light-wood floor, other gym machines and members softly blurred in the background. A cheerful, fit Korean woman in her 50s with short bob hair, coral athletic top and black leggings, walks powerfully uphill on the steeply inclined walking treadmill from the reference image, holding the side handrails, smiling with confidence. Keep the treadmill's exact shape from the reference: black and dark grey frame, tall front console with high arched handrails, long steep deck. The camera starts with a side view showing the steep incline, then slowly pushes in toward her striding legs. She walks, never runs. Bright, light, upbeat mood, photorealistic.
Audio: upbeat bright acoustic pop music, about 118 BPM, major key, acoustic guitar strums, hand claps, light kick and shaker, starting from the first second. A warm, bright, confident Korean female narrator in her 30s, clear standard Seoul accent, upbeat pace, says in Korean: "센터에 등산을 들이세요. 최대 오십 퍼센트 경사, 디랙스 마이마운틴." No on-screen text, no logos, no subtitles.
```
**한글 설명**: 아침 햇살이 드는 밝은 헬스장이다. 단발머리 50대 여성이 코랄 상의에 검정 레깅스를 입고 참고 이미지의 기구 위를 손잡이를 잡고 힘차게 걸어 오른다. 뛰지 않는다. 기구 모양은 참고 사진 그대로다. 카메라는 경사가 보이는 옆모습에서 다리 쪽으로 다가간다. 밝은 어쿠스틱 팝(118 BPM)이 흐르고, 30대 여성 내레이터가 대사를 말한다. 화면에 글자는 없다.

### 5-3. 2클립 (8–16s) — Veo 3.1 Lite · 9:16
- **②안(extend가 되면)**: 1클립에서 연장(extend)한다. 프롬프트는 아래와 같다.
- **①안(안 되면)**: "프레임" 모드로 만든다. 시작 이미지는 1클립 마지막 장면과 비슷한 이미지(1클립 마지막 화면을 Flow에서 쓸 수 있으면 그것)로, 끝 이미지는 5-0 엔드카드로 넣는다.

**영문**
```
Vertical 9:16, 8 seconds, continuing the same scene. The same Korean woman in her 50s (short bob hair, coral athletic top, black leggings) keeps walking uphill on the same incline treadmill. The camera rises up behind her; the gym ceiling and walls open up and dissolve into a bright sunlit mountain summit above a sea of clouds, as if she has reached the peak. She lightly raises both arms with a joyful smile. In the final two seconds the view settles smoothly into the end card image. Bright, uplifting, photorealistic.
Audio: the same upbeat bright acoustic pop music continues, about 118 BPM, major key, acoustic guitar, hand claps, light kick and shaker, with a cymbal swell as the summit opens and a clean ending on the last beat. No narration, no speech. No added text other than the end card image, no logos.
```
**한글 설명**: 같은 여성이 같은 기구를 계속 걷는다. 카메라가 뒤쪽 위로 올라가면 헬스장 천장과 벽이 열리며 햇살 가득한 산 정상과 구름 바다로 바뀐다. 여성은 정상에 오른 듯 두 팔을 가볍게 든다. 마지막 2초는 엔드카드 화면으로 자연스럽게 넘어간다. 음악은 같은 곡 느낌으로 이어지다가 정상이 열릴 때 크게 올라가고 마지막 박자에서 끝난다. 내레이션은 없다.

### 5-4. 장면 조립
Flow 장면 편집기에서 1클립 → 2클립 순서로 타임라인에 올린다(총 16초). 장면 전체 다운로드는 승인 뒤에 한다. 저장 위치는 `08-marketing/work/mm5050se/output/`이다.

---
## 6. 크레딧 계획 (하루 50)
| 작업 | 크레딧 |
|---|---|
| 1클립 Veo Lite 8초 × 최대 2회 | 20 |
| 2클립 Veo Lite 8초(또는 extend) × 최대 2회 | 20 |
| 합계 최대 | **40** (남는 10은 예비) |
※ extend의 크레딧 소모는 확인 못 함.

## 7. 생성 전 사용자 확인 필요
1. 한국어 자막: Flow에 자막 도구가 없다. 플랫폼 자막(인스타·유튜브)으로 넣을지, 다른 방법을 허용할지
2. 연속성: 내레이션을 1클립에만 넣는 ①안(목소리 일관성 우선)으로 진행해도 되는지
3. 다운로드 2건: IG 제품 사진 1장(ref/), 완성 영상(output/)
4. 짐링크의 디랙스 정품 매입 증빙(세금계산서 등) 여부("디랙스 정품 판매·설치" 문구의 전제)
5. 업로드할 때 AI 라벨 켜기(인스타·틱톡·유튜브)

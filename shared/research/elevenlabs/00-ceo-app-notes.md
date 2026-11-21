# 대표실 앱 화면 관찰 메모 (2026-11-21, 로그인 계정, 한국어 UI)

직접 본 것만 적었다. 나머지 화면은 각 팀이 확인한다.

## 왼쪽 메뉴 → 경로
홈 `/app/home` · 음성 `/app/voice-library` · 스튜디오 `/app/studio` · 흐름 `/app/flows` · Producer `/app/producer` · 앱 `/app/apps` · 자산 `/app/files`
고정 메뉴: 텍스트 음성 변환 `/app/speech-synthesis/text-to-speech` · 음성 생성 `/app/create-voice` · 효과음 `/app/sound-effects` · 이미지 및 비디오 `/app/image-video` · 보이스 아이솔레이터 `/app/voice-isolator` · 보이스 체인저 `/app/speech-synthesis/speech-to-speech` · 뮤직 `/app/music` · 음성 텍스트 변환 `/app/speech-to-text` · 더빙 `/app/dubbing` · 오디오북 `/app/audiobooks` · 더 많은 도구(펼침 메뉴, 내용 확인 못 함)
하단: MCP 및 API `/app/developers` · 구독 `/app/subscription`
앱 예시: `/app/apps/dub-and-sync`, `/app/apps/moodboard-generator`, `/app/apps/product-to-lifestyle` 외(목록 잘림)
홈: Producer 프롬프트 입력창이 중심에 있고, 아래에 바로가기(음성, 뮤직, 음성 복제, 이미지, 비디오, 더빙, 아바타, 필사, 오디오북, 더보기)가 있다.

## 음성 생성 `/app/create-voice`
- 상단에 생성 한도 표시: "0 / 3 생성됨"(현재 계정 기준)
- 즉시 음성 복제: 최소 10초, 최대 3분. 업로드나 직접 녹음. → `/app/create-voice/instant`
  - 화면: 왼쪽은 "파일 업로드 | 오디오 녹음" 영역(파일당 최대 10MB), 오른쪽은 진행 링(10초~3분)과 "품질을 높이려면 3분 분량 샘플" 안내
  - 녹음 버튼 이후 흐름은 누르지 않아 확인 못 함
- 프로페셔널 음성 복제: 최소 10분, 최대 2시간, 30분 이상 권장. 라이브러리에 게시해 수익을 낼 수 있음. 현재 계정은 "생성하려면 업그레이드" 상태. `/app/create-voice/professional`은 404라 진입 경로 확인 못 함
- 보이스 디자인: 프롬프트로 음성 생성, 예시 칩 제공
- 기타 도구 > 음성 리믹싱: 프롬프트와 피치·속도 설정으로 기존 음성을 변형

## 텍스트 음성 변환
- 가운데: 화자 이름표, 텍스트 입력("[웃음] 같은 오디오 태그" 지원), "화자 추가"(여러 화자 대화), 시작 예시 칩
- 오른쪽 탭: 설정 | 기록
  - 음성 선택(추천)
  - 모델: Eleven v4, v4 Turbo, v3, Multilingual v2, Flash v2.5, Turbo v2.5, Turbo v2, Flash v2 (설명: v4는 90개 이상 언어, v3는 70개 이상, Multilingual v2는 29개, Flash·Turbo v2.5는 32개, v2 계열은 영어 전용 저지연)
  - 안정성 슬라이더(기본 50%, 창의적 ↔ 견고한), 유사성 슬라이더(기본 75%)
  - 언어(기본 자동), 오디오 효과(필터, 노이즈, Space, 거리), 출력 형식(기본 MP3 44.1kHz 128kbps, 다른 선택지는 확인 못 함)
- 첫 진입 때 신규 모델 소개 팝업이 뜬다

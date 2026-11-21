# ROADMAP (예정·보류 작업, 2026-11-22 기준)

원본 현황판: `shared/board.md`

## 음성 품질 (QA·DevOps)
- [ ] **R3 최종 청취**: Supertonic F2(속도 0.95·1.05) + CosyVoice3를 한 세트로 사용자가 청취·판정 (R3+R3b 통합)
- [ ] **CosyVoice3 CPU 실측**: 설치 완료, 남은 RAM 6GB 이상일 때 단독 실행. RTF 2.0 이하이면 R3 샘플 6개 생성
- [ ] 제로샷 클로닝 속도 측정 (참조 음성은 TTS 합성음만, 실존 화자 복제 금지)
- [ ] 내레이션 용도를 P1로 내릴지 결과 보고 결정
- [ ] Chatterbox: 보류 / GPU: 최후 수단

## 받아쓰기 (STT)
- [ ] **Zeroth-Korean 회의 유사 세트**: 10GB 다운로드 마무리 → test 분할만 풀기 → QA 도구로 5·5·30분(가능하면 60분 1회) 세트 → small·medium 측정
- [ ] 화자 분리(diarization) 후보 검토

## 클로닝·편집
- [ ] **목소리 복제 2차**: OpenVoice V2 CPU 실측(한 문장 30초 이하 기준), 동의 절차·보관 규칙 반영
- [ ] 잡음 제거: DeepFilterNet / noisereduce 실측
- [ ] 음량 정규화 후처리(Supertonic 출력 약 −25 dBFS)

## 서버·화면
- [ ] **프론트 재개 항목**: disclosure(AI 고지) 필드 반영, 실제 백엔드 연결 점검, ElevenLabs look and feel 자체 점검(법무 권고 3)
- [ ] ffmpeg LGPL 빌드 제공(백엔드 오디오 변환용)
- [ ] 엔진 가상환경 패키지 목록 고정(pip freeze) 전달
- [ ] 라이선스 원문 재확인: UniDic, mecab-ko-dic

## 마케팅
- [ ] **MM5050SE 영상**(짐링크): C안 센터 납품형, 세로 9:16, Flow 제작 → 플랫폼 자막(SRT), 엔드카드, 업로드 시 AI 라벨

## 운영
- [ ] 이 PC 메모리 관리: 실측 중에는 다른 무거운 작업(다수 세션, 브라우저 영상 작업)을 줄인다

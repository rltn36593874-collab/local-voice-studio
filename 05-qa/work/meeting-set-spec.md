# 회의 유사 STT 세트 — 구성 방법 (QA → DevOps 전달용)

- 작성: 05-qa, 2026-11-21
- 근거: `shared/research/elevenlabs/05-qa-quality-baseline.md` A2·A3·A8
- 목적: 공개 낭독 음성만 있어 실제 회의 녹음이 없다. 여러 화자를 번갈아 이어 붙이고 잡음을 넣어 회의와 비슷한 STT 시험 파일을 만든다. 만드는 과정에서 **정답 전사와 발화 시작·끝 시각**이 정확히 남으므로, 자막 타이밍 기준으로도 쓴다.
- 도구: `C:\Users\user\agent-company\05-qa\work\make_meeting_set.py`
  - 표준 라이브러리만 쓴다. 설치할 것이 없다.
  - `selftest` 통과(2026-11-21).

## 1. 원천 데이터
| 쓰는 것 | 이유 |
|---|---|
| **Zeroth-Korean 시험 분할만**(1.2시간, 457발화, 화자 10명) | 화자 ID가 있다 |
| FLEURS 한국어는 **쓰지 않는다** | `test.tsv`에 화자 ID 열이 없다(문장 ID·성별만 있음, QA 확인). FLEURS는 STT 낭독 세트와 TTS 명료도 기준 녹음으로만 쓴다 |

## 2. 준비 (DevOps)
1. Zeroth 시험 분할의 FLAC을 **16kHz 모노 WAV**로 변환한다.
   - 16bit PCM과 32bit float 모두 읽는다.
   - 변환 도구(ffmpeg 또는 venv의 soundfile)는 DevOps 환경 기준으로 고른다.
2. `manifest.csv`(UTF-8, 머리줄 필수)를 만든다.
   ```
   path,speaker,text
   C:\...\104_003_0001.wav,104,전사 문장
   ```
   - `speaker` = 화자 ID. Zeroth 파일·폴더 이름 규칙에서 뽑는다. QA는 압축을 풀기 전이라 규칙을 **확인하지 못했다.**
   - `text` = Zeroth 전사 원문 그대로
3. 화자가 **8명 이상**이어야 한다. 웅성거림 잡음용 4명과 대화용 4명을 겹치지 않게 나눈다. 시험 분할은 10명이라 충분하다.

## 3. 실행
```
python -I C:\Users\user\agent-company\05-qa\work\make_meeting_set.py build <manifest.csv> C:\Users\user\agent-company\06-devops\work\voice-bench\datasets\meeting_like --minutes 5 5 30 --seed 20261121
```
- **시간·메모리(QA 실측 기준 추정)**: 잡음 섞기 1분 분량당 약 1초. 5분+5분+30분 × 잡음 조건 5개는 수 분 안에 끝날 것으로 본다. 메모리는 30분 파일 기준 1GB 미만으로 예상한다.
- **seed 고정**(20261121): 같은 manifest로 다시 돌리면 같은 파일이 나온다.

## 4. 구성 규칙 (스크립트에 들어 있음)
| 항목 | 값 |
|---|---|
| 화자 | 파일마다 4명. 웅성거림용 4명과 겹치지 않는다(웅성거림 속 말은 정답에 없음) |
| 발언 차례 | 한 화자가 연속 1~3발화를 한 뒤 다른 화자로 바뀐다 |
| 발화 사이 무음 | 0.3~1.5초(무작위) |
| 잡음만 있는 구간 | 파일마다 20초 1개. 이 구간에 글자가 나오면 "없는 말 지어내기" 1건(A2 기준) |
| 잡음 조건 | `clean` · `pink15`·`pink10`(분홍 잡음, 직접 생성) · `babble15`·`babble10`(다른 화자 4명을 합친 웅성거림). 숫자는 SNR(dB)이고, 말소리 구간 RMS 기준이다 |
| 겹쳐 말하기 | 넣지 않는다(정답 전사가 모호해짐). 실제 회의보다 쉬운 쪽이라는 한계로 기록한다 |
| 길이 | 목표 분량에 닿거나 화자의 발화가 떨어지면 끝난다. 실제 길이는 `SUMMARY.json`에 남는다 |
| 클리핑 방지 | 잡음을 더한 뒤 피크가 넘으면 파일 전체를 줄인다 |

## 5. 결과물 (`meeting_like\` 안)
| 파일 | 내용 |
|---|---|
| `meeting_01_5min_{clean,pink15,pink10,babble15,babble10}.wav` | 시험 음성(16kHz 모노 16bit). 02·03도 같은 형식 |
| `meeting_XX.ref.txt` | 정답 전사(발화당 한 줄, 잡음 구간 제외) |
| `meeting_XX.ref.srt` | 정답 자막(발화 하나 = 블록 하나, 정확한 시작·끝) |
| `meeting_XX.segments.json` | 발화별 시작·끝·화자·문장 + 잡음만 있는 구간(`noise_only`) |
| `SUMMARY.json` | seed, 화자 배정, 파일별 길이·발화 수 |

## 6. 측정 때 남겨 줄 것 (QA 판정용)
- 모델·조건별 STT 결과 텍스트와 SRT(타임스탬프 포함). 위치는 `voice-bench\results\<모델>\`(DevOps 회신대로).
- 처리 시간, RTF, 최대 RAM. 30분 파일은 "1시간 환산" 대신 실측 근거로 쓴다(A5).
- QA가 `audio_check.py cer`와 자막 시작 시각 비교로 CER, 숫자 정확도, 없는 말 지어내기, 자막 오차를 계산한다.

## 7. 출처 표기 (CC BY 4.0 — 결과 폴더와 문서에 그대로 남긴다)
- Zeroth-Korean (SLR40), Lucas Jo(Atlas Guide Inc.)·Wonkyum Lee(Gridspace Inc.), CC BY 4.0, https://www.openslr.org/40/ — QA가 화자 이어 붙이기·잡음 추가로 가공함
- (STT 낭독·TTS 기준) FLEURS, Google, CC BY 4.0, https://huggingface.co/datasets/google/fleurs

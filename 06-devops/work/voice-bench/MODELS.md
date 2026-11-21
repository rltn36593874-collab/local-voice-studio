# 받은 모델 대장 (voice-bench)

| 이름 | 기능 | URL | 라이선스(코드/가중치) | 디스크 크기 | 받은 날 | 상태 |
|---|---|---|---|---|---|---|
| faster-whisper small / medium / large-v3 (CT2) | STT | https://huggingface.co/Systran/faster-whisper-small (·medium·large-v3) | MIT / MIT | 464MB / 1,460MB / 2,948MB | 2026-11-21 | 사용(실측) |
| MeloTTS-Korean | TTS | https://huggingface.co/myshell-ai/MeloTTS-Korean | MIT / MIT | 198MB | 2026-11-21 | 사용(실측) |
| kykim/bert-kor-base (MeloTTS 의존) | TTS 보조 | https://huggingface.co/kykim/bert-kor-base | HF 메타 `license` 비어 있음 → 법무 판단(09-legal) 따름 | 454MB | 2026-11-21 | 사용. **리비전 고정 `1779cc0982ada0216dd6de0dd4e86fb78201926d`**(2026-11-22 대표·법무 지시). 캐시 스냅샷과 일치함을 확인했다. `.venv-melo/.../melo/text/korean.py`, `japanese_bert.py`의 from_pretrained에 `revision=`을 넣었다 |
| UniDic 3.1.0 (MeloTTS 의존, `python -m unidic download`) | 일본어 형태소 사전 | https://pypi.org/project/unidic/ | 확인 필요 | 약 0.5GB(.venv-melo 안) | 2026-11-21 | 사용(한국어 경로에서는 안 씀) |
| python-mecab-ko 1.3.7 + mecab-ko-dic 2.1.1 | 한국어 형태소(g2pkk) | https://pypi.org/project/python-mecab-ko/ | BSD(패키지 메타) / mecab-ko-dic Apache-2.0 — 원문 확인 필요 | 109MB(vendor) | 2026-11-21 | 사용 |
| Supertonic-3 | TTS(비교) | https://huggingface.co/Supertone/supertonic-3 | MIT / **OpenRAIL-M(용도 제한)** | 385MB | 2026-11-21 | 비교 측정, 채택은 QA·대표 판단 뒤. **리비전**: 실제로 받아 측정에 쓴 것은 supertonic 1.3.1 패키지가 고정한 `724fb5abbf5502583fb520898d45929e62f02c0b`(2026-05-06 첫 릴리스). 대표 지시 리비전 `3cadd1ee6394…`(2026-05-18, 현재 main)과 HF tree 해시를 비교했다. onnx·voice_styles·config.json·LICENSE는 **같다**. 차이는 README·.gitattributes·audio_samples(데모 wav 12개)뿐이다. 즉 가중치와 라이선스 파일은 같다 |

| Fun-CosyVoice3-0.5B-2512 | TTS·제로샷 클로닝(비교) | https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 (리비전 `29e01c4e8d000f4bcd70751be16fa94bf3d85a18`) | Apache-2.0 / Apache-2.0 (HF 메타 `apache-2.0`, 저장소 LICENSE Apache 2.0) | 5.05GB 받음(전체 9.08GB 중 CPU에서 안 쓰는 `llm.rl.pt`, `speech_tokenizer_v3.batch.onnx`, `flow.decoder.estimator.fp32.onnx` 제외) | 2026-11-22 | 받음, `models/Fun-CosyVoice3-0.5B/`. 코드는 `engines/CosyVoice`(github FunAudioLLM/CosyVoice @ `074ca6dc`, Matcha-TTS 서브모듈 포함) |

## 데이터셋 (사용자 승인 2026-11-21, 대표 전달)
| 이름 | 용도 | URL | 라이선스 (원문 확인) | 크기 | 받은 날 | 상태 |
|---|---|---|---|---|---|---|
| FLEURS 한국어 test 분할 (`ko_kr`) | STT 정확도(사람 녹음) | https://huggingface.co/datasets/google/fleurs (`data/ko_kr/test.tsv`, `audio/test.tar.gz`) | CC BY 4.0 (데이터셋 카드 `license: cc-by-4.0`) | tar 214MB, 풀어서 382개, 폴더 합계 499MB | 2026-11-21 | 받음, `datasets/fleurs_ko/` |
| Zeroth-Korean | STT 정확도(test 1.2시간, 457발화, 10명) | https://www.openslr.org/40/ (실제 받은 곳: https://www.openslr.org/resources/40/zeroth_korean.tar.gz, 10,339,720,618바이트. 페이지의 외부 링크 storage.googleapis.com은 2026-11-21 기준 AccessDenied) | CC BY 4.0 (OpenSLR 페이지 "Attribution 4.0 International") | tar 약 10GB(학습분 포함 단일 파일) | 2026-11-21 | 받는 중, `datasets/zeroth/`. test만 풀고, 실측이 끝나면 tar는 지운다(다시 받을 수 있음) |

- 표기 의무(CC BY): 결과 문서에 출처를 적는다. "Google FLEURS (CC BY 4.0)", "Zeroth-Korean, Zeroth Project / Atlas Labs (CC BY 4.0)".
- `datasets/SRCLOG.tsv`에도 기록했다(srclog).

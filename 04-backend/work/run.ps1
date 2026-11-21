# 사내 음성 도구 로컬 API 서버 실행 (127.0.0.1:8000에만 바인딩)
# Claude 키: server\.env 파일에 ANTHROPIC_API_KEY=... 한 줄(사용자가 직접 씀). 셸 환경변수가 있으면 그쪽이 우선.
# 이 스크립트와 서버는 키 값을 화면·로그에 출력하지 않는다(있는지 여부만 표시).
# 엔진 바꾸기: $env:VOICETOOL_TTS_ENGINE = "mock" | "melo" | "supertonic", $env:VOICETOOL_STT_ENGINE = "mock" | "faster_whisper"
$W = $PSScriptRoot
if (-not $env:VOICETOOL_TTS_ENGINE) { $env:VOICETOOL_TTS_ENGINE = "melo" }
if (-not $env:VOICETOOL_STT_ENGINE) { $env:VOICETOOL_STT_ENGINE = "faster_whisper" }
if (-not $env:VOICETOOL_PORT) { $env:VOICETOOL_PORT = "8000" }  # 프론트 프록시는 8000을 본다
Write-Host "TTS=$env:VOICETOOL_TTS_ENGINE STT=$env:VOICETOOL_STT_ENGINE 키 환경변수: $([bool]$env:ANTHROPIC_API_KEY) / server\.env 파일: $(Test-Path "$W\server\.env")"
Set-Location $W
& "$W\.venv\Scripts\python.exe" -m uvicorn server.app:app --host 127.0.0.1 --port $env:VOICETOOL_PORT --no-access-log

# Pixel Agents 오피스 서버 실행 (http://127.0.0.1:3100)
# Windows에서 pixel-agents가 확장자 없는 "claude"를 실행하므로,
# 실제 claude.exe 폴더를 PATH 맨 앞에 둬야 오피스에서 세션 실행이 된다.
$claudeBin = Join-Path $env:APPDATA 'npm\node_modules\@anthropic-ai\claude-code\bin'
$env:PATH = "$claudeBin;$env:PATH"
pixel-agents --port 3100

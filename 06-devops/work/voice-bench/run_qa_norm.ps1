# QA A7-2 요청: 숫자를 한글로 풀어 쓴 2문장(L3n, L4n) TTS 2엔진 → faster-whisper small 역전사. 한 번에 하나씩 실행.
# 실행 조건: 대표 승인 + 메모리 여유(작업 전 남은 RAM 4GB 이상). 결과: results\melo_norm, supertonic_norm, fw_small_norm
$B = $PSScriptRoot
. "$B\env.ps1"
Set-Location $B
$free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
if ($free -lt 4) { "중단: 남은 RAM {0:N1}GB < 4GB" -f $free; exit 1 }
python bench_run.py tts_melo_norm "$B\.venv-melo\Scripts\python.exe" tts_bench.py melo 10 "$B\results\melo_norm" "$B\samples\L3n-L4n.txt" | Select-Object -Last 1
python bench_run.py tts_supertonic_norm "$B\.venv-supertonic\Scripts\python.exe" tts_bench.py supertonic 10 "$B\results\supertonic_norm" "$B\samples\L3n-L4n.txt" | Select-Object -Last 1
$W = $B -replace '\\', '/'
Get-Content "$B\samples\L3n-L4n.txt" -Encoding utf8 | ForEach-Object { $l, $t = $_ -split "`t", 2; foreach ($e in 'melo_norm', 'supertonic_norm') { "$W/results/$e/$l.wav`t$t" } } | Set-Content "$B\samples\backtx_norm.tsv" -Encoding utf8
python bench_run.py stt_fw_small_norm "$B\.venv\Scripts\python.exe" stt_fw.py small 10 "$B\results\fw_small_norm" "$B\samples\backtx_norm.tsv" | Select-Object -Last 1
"QA norm done $(Get-Date -Format s)"

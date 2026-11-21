# STT 실측을 순차로 실행(한 번에 하나). 결과: results\bench.jsonl, results\fw_<model>_<set>\
$B = $PSScriptRoot
. "$B\env.ps1"
Set-Location $B
foreach ($m in "small", "medium", "large-v3") {
    foreach ($s in "backtx", "fleurs60") {
        python bench_run.py "stt_fw_${m}_$s" "$B\.venv\Scripts\python.exe" stt_fw.py $m 10 "$B\results\fw_${m}_$s" "$B\samples\$s.tsv" | Select-Object -Last 1
    }
}
"STT done $(Get-Date -Format s)"

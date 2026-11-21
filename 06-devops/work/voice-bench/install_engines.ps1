# 엔진별 가상환경에 설치(순차). 로그: results\install.log
$B = $PSScriptRoot
. "$B\env.ps1"
$log = "$B\results\install.log"
function Step($name, $py, $pkgs) {
    "=== $name $(Get-Date -Format s)" | Tee-Object -Append $log
    & uv pip install --python $py @pkgs 2>&1 | Tee-Object -Append $log | Select-Object -Last 3
}
Step "supertonic" "$B\.venv-supertonic\Scripts\python.exe" @("supertonic==1.3.1", "soundfile", "psutil")
Step "deepfilternet" "$B\.venv-df\Scripts\python.exe" @("torch==2.2.2", "torchaudio==2.2.2", "--index-url", "https://download.pytorch.org/whl/cpu")
Step "deepfilternet2" "$B\.venv-df\Scripts\python.exe" @("deepfilternet==0.5.6", "soundfile", "psutil", "noisereduce==3.0.3")
Step "melotts-torch" "$B\.venv-melo\Scripts\python.exe" @("torch==2.2.2", "torchaudio==2.2.2", "--index-url", "https://download.pytorch.org/whl/cpu")
Step "melotts" "$B\.venv-melo\Scripts\python.exe" @("git+https://github.com/myshell-ai/MeloTTS.git", "psutil", "soundfile")
"=== done $(Get-Date -Format s)" | Tee-Object -Append $log

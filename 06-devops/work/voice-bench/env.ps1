# 이 셸 세션에서만 적용: 모든 캐시를 voice-bench 안에 두고 GPU는 쓰지 않는다. 사용: . .\env.ps1
$B = $PSScriptRoot
$env:HF_HOME = "$B\cache\hf"
$env:TORCH_HOME = "$B\cache\torch"
$env:XDG_CACHE_HOME = "$B\cache"
$env:PIP_CACHE_DIR = "$B\cache\pip"
$env:MODELSCOPE_CACHE = "$B\cache\modelscope"
$env:NLTK_DATA = "$B\cache\nltk"
$env:CUDA_VISIBLE_DEVICES = ""
$env:SUPERTONIC_CACHE_DIR = "$B\cache\supertonic3"
$env:UV_CACHE_DIR = "$B\cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$B\pythons"   # uv 휴대용 Python(3.10/3.11), --no-bin --no-registry로 설치함
& "$B\.venv\Scripts\Activate.ps1"

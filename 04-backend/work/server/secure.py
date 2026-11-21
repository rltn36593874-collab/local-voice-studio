"""복제 샘플·목소리 특징값(target_se) 암호화(법무 09 §3-3: 분리 폴더 + 암호화).
이 PC는 Windows 11 Home이라 EFS를 못 쓴다 → Windows DPAPI(CryptProtectData, 현재 Windows 사용자 계정에 묶임)로 파일 단위 암호화.
외부 라이브러리 없이 ctypes로 부른다. 다른 계정·다른 PC로 복사하면 풀리지 않는다(반출 방지에도 맞다)."""
import ctypes
import ctypes.wintypes as wt
import shutil
from pathlib import Path

ENTROPY = b"voicetool-secure-v1"  # 앱 고유 값(비밀이 아님, 같은 계정의 다른 앱이 무심코 풀지 못하게)


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(b: bytes):
    buf = ctypes.create_string_buffer(b, len(b))
    return _Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _call(fn, data: bytes) -> bytes:
    inp, _keep = _blob(data)
    ent, _keep2 = _blob(ENTROPY)
    out = _Blob()
    if not fn(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):  # 0x1 = UI 없음
        raise OSError(ctypes.get_last_error() or "DPAPI 실패")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    return _call(lambda i, d, e, r, p, f, o: crypt32.CryptProtectData(i, d, e, r, p, f, o), data)


def unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    return _call(lambda i, d, e, r, p, f, o: crypt32.CryptUnprotectData(i, None, e, r, p, f, o), data)


def write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(path.suffix + ".enc").write_bytes(protect(data))


def read(path: Path) -> bytes:
    return unprotect(path.with_suffix(path.suffix + ".enc").read_bytes())


def wipe_dir(path: Path):
    """폴더째 지운다(복호화한 임시 파일·캐시 포함). shortcut: SSD에서는 덮어쓰기 삭제가 의미가 없어 일반 삭제."""
    if path.exists():
        shutil.rmtree(path)

import io
import os
import sys
from datetime import datetime

# Windows cp949 stdout에서 이모지 깨짐 방지
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 프로젝트 루트 기준 로그 파일 경로
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_log_dir = os.path.join(_project_root, "logs")
_log_path = os.path.join(_log_dir, "collector.log")

# 파일 핸들 (import 시 1회 오픈)
_file_handle = None
try:
    os.makedirs(_log_dir, exist_ok=True)
    _file_handle = open(_log_path, "a", encoding="utf-8")
except Exception:
    pass


def log(message: str):
    """통일된 로그 포맷 — stdout + 파일 동시 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    if _file_handle:
        try:
            _file_handle.write(line + "\n")
            _file_handle.flush()
        except Exception:
            pass

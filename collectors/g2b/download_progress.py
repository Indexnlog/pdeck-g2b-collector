import os
from utils.drive import download_file
from utils.logger import log

# progress.json이 존재해야 하는 위치
LOCAL_PATH = "progress.json"

FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")

if __name__ == "__main__":
    log("🔽 progress.json 다운로드 시작")

    if not FILE_ID:
        log("❌ GDRIVE_PROGRESS_FILE_ID 누락")
        raise SystemExit(1)

    # 로컬 progress.json 제거 (항상 Drive 기준으로 덮어쓰기)
    if os.path.exists(LOCAL_PATH):
        os.remove(LOCAL_PATH)
        log("🗑 기존 progress.json 삭제")

    success = download_file(FILE_ID, LOCAL_PATH)

    if success:
        log("⬇ progress.json 다운로드 완료")
    else:
        log("⚠ 다운로드 실패 — 로컬 progress.json 기본값 사용 가능")

import os
from utils.drive import download_file
from utils.logger import log

LOCAL_PATH = "progress.json"
FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")


if __name__ == "__main__":
    log("🔽 Drive → progress.json 다운로드 시작")

    if not FILE_ID:
        log("❌ GDRIVE_PROGRESS_FILE_ID 없음")
        raise SystemExit(1)

    if os.path.exists(LOCAL_PATH):
        os.remove(LOCAL_PATH)

    success = download_file(FILE_ID, LOCAL_PATH)

    if success:
        log("✅ progress.json 다운로드 완료")
    else:
        log("⚠ progress.json 다운로드 실패")

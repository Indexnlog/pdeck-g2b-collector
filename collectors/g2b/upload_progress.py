import os
from utils.drive import upload_file
from utils.logger import log

LOCAL_PATH = "progress.json"
FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")

if __name__ == "__main__":
    log("📤 progress.json 업로드 시작")

    if not FILE_ID:
        log("❌ GDRIVE_PROGRESS_FILE_ID가 없습니다.")
        raise SystemExit(1)

    if not os.path.exists(LOCAL_PATH):
        log("❌ progress.json 파일이 없습니다.")
        raise SystemExit(1)

    success = upload_file(LOCAL_PATH, FILE_ID)

    if success:
        log("✔ progress.json 업로드 완료")
    else:
        log("⚠ 업로드 실패")

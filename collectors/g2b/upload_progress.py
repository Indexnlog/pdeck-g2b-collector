import os
from utils.drive import upload_file
from utils.logger import log
from utils.slack import send_slack_message

# collect_all.py와 동일한 경로
LOCAL_PATH = "progress.json"

# Google Drive File ID
DRIVE_FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")

if __name__ == "__main__":
    log("🔼 Uploading updated progress.json to Google Drive...")

    if not DRIVE_FILE_ID:
        log("❌ ERROR: 환경변수 GDRIVE_PROGRESS_FILE_ID가 설정되지 않았습니다.")
        raise SystemExit(1)

    if not os.path.exists(LOCAL_PATH):
        log(f"❌ ERROR: {LOCAL_PATH} 파일이 존재하지 않아 업로드할 수 없습니다.")
        raise SystemExit(1)

    success = upload_file(LOCAL_PATH, DRIVE_FILE_ID)

    if success:
        log("✅ progress.json 업로드 완료")
    else:
        log("⚠️ progress.json 업로드 실패 — 상태 저장이 Drive에 반영되지 않음")

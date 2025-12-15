import os
from utils.drive import upload_file
from utils.logger import log
from utils.slack import send_slack_message

# progress.json 위치 (collect_all.py와 동일)
LOCAL_PATH = "progress.json"

# Google Drive 파일 ID
DRIVE_FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")


if __name__ == "__main__":
    log("🔼 progress.json → Drive 업로드 시작")

    if not DRIVE_FILE_ID:
        msg = "❌ 환경변수 GDRIVE_PROGRESS_FILE_ID 설정되지 않음"
        log(msg)
        send_slack_message(msg)
        raise SystemExit(1)

    if not os.path.exists(LOCAL_PATH):
        msg = f"❌ {LOCAL_PATH} 파일이 존재하지 않아 업로드 불가"
        log(msg)
        send_slack_message(msg)
        raise SystemExit(1)

    success = upload_file(LOCAL_PATH, DRIVE_FILE_ID)

    if success:
        log("✅ progress.json 업로드 성공")
        send_slack_message("✔ progress.json 업로드 완료")
    else:
        msg = "⚠️ progress.json 업로드 실패 — Drive와 동기화되지 않음"
        log(msg)
        send_slack_message(msg)

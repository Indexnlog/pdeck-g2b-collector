import os
from utils.drive import download_file
from utils.logger import log
from utils.slack import send_slack_message

# progress.json 로컬 저장 위치 (collect_all.py와 동일하게!)
LOCAL_PATH = "progress.json"

# Google Drive File ID
DRIVE_FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")

if __name__ == "__main__":
    log("🔽 Downloading progress.json from Google Drive...")

    if not DRIVE_FILE_ID:
        log("❌ ERROR: 환경변수 GDRIVE_PROGRESS_FILE_ID가 설정되지 않았습니다.")
        raise SystemExit(1)

    # 기존 파일 삭제
    if os.path.exists(LOCAL_PATH):
        os.remove(LOCAL_PATH)
        log("🗑 기존 progress.json 삭제 완료")

    success = download_file(DRIVE_FILE_ID, LOCAL_PATH)

    if success:
        log("✅ progress.json 다운로드 완료")
    else:
        log("⚠️ progress.json 다운로드 실패 — 기본 progress.json이 사용될 수 있음")

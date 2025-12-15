import os
from utils.drive import download_file
from utils.logger import log
from utils.slack import send_slack_message

# 다운로드 후 루트에 둘 progress.json 위치
LOCAL_PATH = "progress.json"

# Google Drive 파일 ID (GitHub Secrets에서 주입됨)
DRIVE_FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")


if __name__ == "__main__":
    log("🔽 Drive → progress.json 다운로드 시작")

    if not DRIVE_FILE_ID:
        msg = "❌ 환경변수 GDRIVE_PROGRESS_FILE_ID가 설정되지 않음"
        log(msg)
        send_slack_message(msg)
        raise SystemExit(1)

    # 기존 파일 삭제
    if os.path.exists(LOCAL_PATH):
        os.remove(LOCAL_PATH)
        log("🗑 기존 progress.json 삭제 완료")

    # Drive에서 다운로드
    success = download_file(DRIVE_FILE_ID, LOCAL_PATH)

    if success:
        log("✅ progress.json 다운로드 성공")
        send_slack_message("🔽 progress.json 다운로드 완료")
    else:
        log("⚠️ progress.json 다운로드 실패 — 기본 progress.json이 사용될 수 있음")
        send_slack_message("⚠️ progress.json 다운로드 실패 — 로컬 기본값으로 진행됨")

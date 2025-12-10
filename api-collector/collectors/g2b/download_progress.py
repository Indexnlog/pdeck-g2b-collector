from __future__ import print_function
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import sys

FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
LOCAL_PATH = "data/logs/progress.json"


def download_progress():
    # --------------------------
    # 🔥 환경변수 확인
    # --------------------------
    if not FOLDER_ID:
        print("❌ ERROR: GDRIVE_FOLDER_ID is missing. Check GitHub Secrets.")
        return False

    if not os.path.exists("service_account.json"):
        print("❌ ERROR: service_account.json is missing!")
        return False

    # --------------------------
    # 🔐 Google 인증
    # --------------------------
    try:
        creds = Credentials.from_service_account_file(
            "service_account.json",
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Google Drive auth failed: {e}")
        return False

    # --------------------------
    # 🔎 progress.json 찾기
    # --------------------------
    try:
        query = f"'{FOLDER_ID}' in parents and name='progress.json'"
        res = service.files().list(q=query, fields="files(id,name)").execute()
        files = res.get("files", [])
    except Exception as e:
        print(f"❌ Drive query failed: {e}")
        return False

    if not files:
        print("⚠ No progress.json found on Google Drive → fresh start.")
        return False

    file_id = files[0]['id']

    # --------------------------
    # ⬇ 다운로드
    # --------------------------
    try:
        request = service.files().get_media(fileId=file_id)
        os.makedirs(os.path.dirname(LOCAL_PATH), exist_ok=True)

        with io.FileIO(LOCAL_PATH, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        print("✅ progress.json downloaded successfully")
        return True

    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


if __name__ == "__main__":
    download_progress()

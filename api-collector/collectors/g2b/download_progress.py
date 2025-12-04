# download_progress.py
from __future__ import print_function
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
LOCAL_PATH = "data/logs/progress.json"


def download_progress():
    # service_account.json 사용해 인증
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    service = build('drive', 'v3', credentials=creds)

    # progress.json 검색
    query = f"'{FOLDER_ID}' in parents and name='progress.json'"
    res = service.files().list(q=query, fields="files(id,name)").execute()
    files = res.get("files", [])

    if not files:
        print("⚠ No progress.json found on Google Drive → fresh start")
        return

    file_id = files[0]['id']

    # 다운로드
    request = service.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(LOCAL_PATH), exist_ok=True)

    fh = io.FileIO(LOCAL_PATH, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    print("✅ progress.json downloaded successfully")


if __name__ == "__main__":
    download_progress()

# upload_progress.py
from __future__ import print_function
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
LOCAL_PATH = "data/logs/progress.json"


def upload_progress():

    if not os.path.exists(LOCAL_PATH):
        print("⚠ No local progress.json to upload.")
        return

    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    service = build('drive', 'v3', credentials=creds)

    # 기존 progress.json 삭제
    query = f"'{FOLDER_ID}' in parents and name='progress.json'"
    res = service.files().list(q=query, fields="files(id)").execute()
    files = res.get("files", [])

    for f in files:
        service.files().delete(fileId=f["id"]).execute()

    # 새 파일 업로드
    metadata = {
        "name": "progress.json",
        "parents": [FOLDER_ID]
    }

    media = MediaFileUpload(LOCAL_PATH, mimetype="application/json")

    service.files().create(
        body=metadata,
        media_body=media,
        fields="id"
    ).execute()

    print("✅ progress.json uploaded to Google Drive")


if __name__ == "__main__":
    upload_progress()

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

FOLDER_ID = "1HkBpWUauvTLoLlc6R57ikc-Vso4ZzYgN"
RAW_DIR = "./data/raw"

def main():
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )

    service = build("drive", "v3", credentials=creds)

    for filename in os.listdir(RAW_DIR):
        if filename.endswith(".xml"):
            file_path = os.path.join(RAW_DIR, filename)

            media = MediaFileUpload(file_path, resumable=True)
            metadata = {"name": filename, "parents": [FOLDER_ID]}

            uploaded = service.files().create(
                body=metadata,
                media_body=media,
                fields="id"
            ).execute()

            print(f"✅ 업로드 완료: {filename} (ID: {uploaded.get('id')})")

if __name__ == "__main__":
    main()

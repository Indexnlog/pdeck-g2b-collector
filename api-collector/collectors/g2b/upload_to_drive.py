from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# GitHub Secret에서 설정한 환경변수 가져오기 (없으면 하드코딩된 값 사용)
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1HkBpWUauvTLoLlc6R57ikc-Vso4ZzYgN")
RAW_DIR = "data/raw"  # YAML 실행 위치 기준 경로


def main():
    # 1. 데이터 폴더가 있는지 먼저 확인 (없으면 조용히 종료)
    if not os.path.exists(RAW_DIR):
        print(f"📂 '{RAW_DIR}' 폴더가 없습니다. 수집된 데이터가 없어 업로드를 건너뜁니다.")
        return

    files = [f for f in os.listdir(RAW_DIR) if f.endswith(".xml")]

    if not files:
        print("📂 업로드할 XML 파일이 없습니다.")
        return

    print(f"🚀 구글 드라이브 업로드 시작 (대상 폴더 ID: {FOLDER_ID})")

    # 2. 인증 정보 로드 (YAML에서 생성된 service_account.json 사용)
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )

    service = build("drive", "v3", credentials=creds)

    # 3. 파일 순차 업로드
    for filename in files:
        file_path = os.path.join(RAW_DIR, filename)

        media = MediaFileUpload(file_path, resumable=True)
        metadata = {"name": filename, "parents": [FOLDER_ID]}

        try:
            uploaded = service.files().create(
                body=metadata,
                media_body=media,
                fields="id"
            ).execute()
            print(f"✅ 업로드 완료: {filename} (ID: {uploaded.get('id')})")
        except Exception as e:
            print(f"❌ 업로드 실패: {filename} / 에러: {e}")


if __name__ == "__main__":
    main()

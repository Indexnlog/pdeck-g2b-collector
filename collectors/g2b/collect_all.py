#!/usr/bin/env python3
import os
import sys
import time
import traceback
from datetime import datetime
import pytz

# -----------------------------------------------------------
# 프로젝트 루트 계산 (collectors/g2b 기준)
# -----------------------------------------------------------
current_file_path = os.path.abspath(__file__)
g2b_dir = os.path.dirname(current_file_path)
collectors_dir = os.path.dirname(g2b_dir)
project_root = os.path.dirname(collectors_dir)

# GitHub Actions / 로컬 공통 대응
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"✅ 프로젝트 루트: {project_root}")
print(f"📂 루트 내용물: {os.listdir(project_root)}")

# -----------------------------------------------------------
# imports (정리된 최종 형태)
# -----------------------------------------------------------
try:
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    from utils.drive import (
        download_progress_json,
        upload_progress_json,
        test_drive_connection,
        get_drive_service,
    )
    from utils.g2b_client import G2BClient
    from utils.logger import log
    from utils.slack import send_slack_message

except ImportError as e:
    print(f"\n🚫 Import 실패: {e}")
    print(f"sys.path = {sys.path}")
    sys.exit(1)

# -----------------------------------------------------------
# 설정값
# -----------------------------------------------------------
PROGRESS_FILE_ID = "1_AKg04eOjQy3KBcjhp2xkkm1jzBcAjn-"
SHARED_DRIVE_ID = "0AOi7Y50vK8xiUk9PVA"
API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 500


# -----------------------------------------------------------
# Shared Drive 업로드
# -----------------------------------------------------------
def upload_file_to_shared_drive(local_path: str, filename: str) -> bool:
    try:
        log(f"📤 Shared Drive 업로드 시작: {filename}")

        service = get_drive_service()

        file_metadata = {
            "name": filename,
            "parents": [SHARED_DRIVE_ID],
        }

        media = MediaFileUpload(local_path, resumable=True, chunksize=1024 * 1024)

        request = service.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log(f"📊 업로드 {int(status.progress() * 100)}%")

        log(f"✅ 업로드 완료: {filename} (ID: {response.get('id')})")
        return True

    except Exception as e:
        log(f"❌ 업로드 실패: {e}")
        return False


# -----------------------------------------------------------
# 연도별 XML 파일 누적
# -----------------------------------------------------------
def append_to_year_file(job, year, xml_content):
    filename = f"{job}_{year}.xml"
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    local_path = os.path.join(data_dir, filename)

    if not os.path.exists(local_path):
        with open(local_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<root>\n')
            f.write(xml_content)
            f.write("\n</root>")
    else:
        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read().replace("</root>", "")
        content += xml_content + "\n</root>"
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(content)

    return local_path, filename


# -----------------------------------------------------------
# 다음 수집 구간 계산
# -----------------------------------------------------------
def get_next_period(job, year, month):
    jobs = ["물품", "공사", "용역", "외자"]

    if month < 12:
        return job, year, month + 1

    idx = jobs.index(job)
    if idx < len(jobs) - 1:
        return jobs[idx + 1], year, 1
    else:
        return jobs[0], year + 1, 1


# -----------------------------------------------------------
# 메인 로직
# -----------------------------------------------------------
def main():
    try:
        log("🚀 G2B 수집 시작")

        if not test_drive_connection():
            raise Exception("Drive 연결 실패")

        progress = download_progress_json(PROGRESS_FILE_ID)
        if not progress:
            raise Exception("progress.json 로드 실패")

        # 한국 기준 일일 리셋
        tz = pytz.timezone("Asia/Seoul")
        today = datetime.now(tz).strftime("%Y-%m-%d")
        if progress.get("last_api_reset_date") != today:
            progress["daily_api_calls"] = 0
            progress["last_api_reset_date"] = today

        if not API_KEY:
            raise Exception("API_KEY 환경변수 없음")

        client = G2BClient(API_KEY)

        total_new = 0
        uploaded = []

        while progress["daily_api_calls"] < MAX_API_CALLS:
            job = progress["current_job"]
            year = progress["current_year"]
            month = progress["current_month"]

            xml, count, used = client.fetch_data(job, year, month)
            progress["daily_api_calls"] += used

            if count > 0:
                local_path, fname = append_to_year_file(job, year, xml)
                if upload_file_to_shared_drive(local_path, fname):
                    uploaded.append(fname)
                total_new += count
                progress["total_collected"] += count

            next_job, next_year, next_month = get_next_period(job, year, month)
            progress.update(
                {
                    "current_job": next_job,
                    "current_year": next_year,
                    "current_month": next_month,
                }
            )

            if next_year > 2025:
                break

        progress["last_run_date"] = today
        upload_progress_json(progress, PROGRESS_FILE_ID)

        send_slack_message(
            f"""🎯 G2B 수집 완료
오늘 수집: {total_new:,}건
API 호출: {progress['daily_api_calls']}/{MAX_API_CALLS}
업로드 파일: {len(uploaded)}개

"""
코드 복사
        )

        log("🎉 작업 완료")
        return True

    except Exception as e:
        msg = f"❌ 수집 실패: {e}\n```{traceback.format_exc()}```"
        log(msg)
        send_slack_message(msg)
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
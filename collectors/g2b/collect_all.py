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

    # 에러 핸들링 추가
    from utils.api_error_handler import (
        retry_on_error,
        error_context,
        safe_api_call,
        APIException,
        NetworkError,
        RateLimitError,
        ValidationError
    )

except ImportError as e:
    print(f"\n🚫 Import 실패: {e}")
    print(f"sys.path = {sys.path}")
    traceback.print_exc()
    sys.exit(1)

# -----------------------------------------------------------
# 설정값
# -----------------------------------------------------------
PROGRESS_FILE_ID = "1_AKg04eOjQy3KBcjhp2xkkm1jzBcAjn-"
SHARED_DRIVE_ID = "0AOi7Y50vK8xiUk9PVA"
API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 500


# -----------------------------------------------------------
# Shared Drive 업로드 (자동 재시도 적용)
# -----------------------------------------------------------
@retry_on_error(
    max_retries=3,
    base_delay=2.0,
    on_retry=lambda e, attempt: log(f"⏳ Drive 업로드 재시도 {attempt}/3: {e}")
)
def upload_file_to_shared_drive(local_path: str, filename: str) -> bool:
    """
    Shared Drive에 파일 업로드 (자동 재시도)

    Args:
        local_path: 로컬 파일 경로
        filename: 업로드할 파일명

    Returns:
        bool: 업로드 성공 여부
    """
    with error_context(f"Drive 업로드: {filename}"):
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
# 메인 로직 (강화된 에러 핸들링)
# -----------------------------------------------------------
def main():
    progress = None
    total_new = 0
    uploaded = []
    errors = []

    try:
        log("🚀 G2B 수집 시작")

        # 1. 입력값 검증
        if not API_KEY:
            raise ValidationError("API_KEY 환경변수가 설정되지 않았습니다")

        # 2. Drive 연결 테스트 (재시도 적용)
        with error_context("Google Drive 연결 확인"):
            connection_test = safe_api_call(
                test_drive_connection,
                max_retries=3,
                default_value=False
            )
            if not connection_test:
                raise NetworkError("Google Drive 연결에 실패했습니다")

        # 3. progress.json 다운로드 (재시도 적용)
        with error_context("progress.json 다운로드"):
            progress = safe_api_call(
                download_progress_json,
                PROGRESS_FILE_ID,
                max_retries=3,
                default_value=None
            )
            if not progress:
                raise Exception("progress.json 로드 실패 - Drive에서 파일을 가져올 수 없습니다")

        # 4. 한국 시간 기준 일일 리셋
        tz = pytz.timezone("Asia/Seoul")
        today = datetime.now(tz).strftime("%Y-%m-%d")
        if progress.get("last_api_reset_date") != today:
            progress["daily_api_calls"] = 0
            progress["last_api_reset_date"] = today
            log(f"🔄 일일 API 카운터 리셋 (날짜: {today})")

        # 5. G2B 클라이언트 생성
        client = G2BClient(API_KEY)

        # 6. 데이터 수집 루프
        while progress["daily_api_calls"] < MAX_API_CALLS:
            job = progress["current_job"]
            year = progress["current_year"]
            month = progress["current_month"]

            log(f"\n{'='*60}")
            log(f"📍 현재 작업: {job} {year}년 {month}월")
            log(f"📊 API 사용량: {progress['daily_api_calls']}/{MAX_API_CALLS}")
            log(f"{'='*60}")

            try:
                # API 호출 (G2BClient 자체에 재시도 로직 있음)
                xml, count, used = client.fetch_data(job, year, month)
                progress["daily_api_calls"] += used

                # 데이터가 있으면 저장 및 업로드
                if count > 0:
                    local_path, fname = append_to_year_file(job, year, xml)

                    # 업로드 시도 (자동 재시도 적용)
                    try:
                        if upload_file_to_shared_drive(local_path, fname):
                            uploaded.append(fname)
                            log(f"✅ {fname} 업로드 성공")
                        else:
                            log(f"⚠️ {fname} 업로드 실패 (로컬에는 저장됨)")
                            errors.append(f"업로드 실패: {fname}")
                    except Exception as upload_err:
                        log(f"⚠️ {fname} 업로드 에러: {upload_err} (로컬에는 저장됨)")
                        errors.append(f"업로드 에러: {fname} - {upload_err}")

                    total_new += count
                    progress["total_collected"] += count
                else:
                    log(f"ℹ️ {job} {year}년 {month}월 - 데이터 없음")

            except RateLimitError as e:
                log(f"⚠️ API 한도 도달: {e}")
                errors.append(f"API 한도 도달: {job} {year}-{month}")
                break

            except APIException as e:
                log(f"⚠️ API 에러 ({job} {year}-{month}): {e}")
                errors.append(f"API 에러: {job} {year}-{month} - {e}")
                # API 에러는 해당 구간만 건너뛰고 계속 진행

            except Exception as e:
                log(f"❌ 예상치 못한 에러 ({job} {year}-{month}): {e}")
                errors.append(f"예상치 못한 에러: {job} {year}-{month} - {e}")
                # 예상치 못한 에러도 일단 계속 시도

            # 다음 구간으로 이동
            next_job, next_year, next_month = get_next_period(job, year, month)
            progress.update({
                "current_job": next_job,
                "current_year": next_year,
                "current_month": next_month,
            })

            # 2025년까지만 수집
            if next_year > 2025:
                log("📅 2025년까지 모든 데이터 수집 완료")
                break

        # 7. 진행 상황 저장 (중요: 반드시 저장)
        progress["last_run_date"] = today
        with error_context("progress.json 업로드"):
            try:
                upload_progress_json(progress, PROGRESS_FILE_ID)
                log("✅ progress.json 업로드 완료")
            except Exception as e:
                log(f"⚠️ progress.json 업로드 실패: {e}")
                errors.append(f"progress.json 업로드 실패: {e}")

        # 8. 결과 알림
        status_emoji = "🎯" if not errors else "⚠️"
        error_summary = ""
        if errors:
            error_summary = f"\n\n❌ 발생한 에러 ({len(errors)}개):\n" + "\n".join(f"  • {e}" for e in errors[:5])
            if len(errors) > 5:
                error_summary += f"\n  • ... 외 {len(errors) - 5}개"

        message = f"""{status_emoji} G2B 수집 완료
오늘 수집: {total_new:,}건
API 호출: {progress['daily_api_calls']}/{MAX_API_CALLS}
업로드 파일: {len(uploaded)}개
총 누적: {progress.get('total_collected', 0):,}건{error_summary}
"""

        send_slack_message(message)
        log("🎉 작업 완료")

        # 에러가 있었어도 일부 성공했으면 성공으로 간주
        return True

    except ValidationError as e:
        msg = f"❌ 입력값 검증 실패: {e}"
        log(msg)
        send_slack_message(msg)
        return False

    except NetworkError as e:
        msg = f"❌ 네트워크 연결 실패: {e}\n재시도했지만 연결할 수 없습니다."
        log(msg)
        send_slack_message(msg)
        return False

    except APIException as e:
        msg = f"❌ API 에러: {e}\n상세: {traceback.format_exc()}"
        log(msg)
        send_slack_message(msg)
        return False

    except Exception as e:
        msg = f"❌ 치명적 오류 발생: {e}\n```{traceback.format_exc()}```"
        log(msg)
        send_slack_message(msg)
        return False

    finally:
        # 진행 상황이 있으면 최후의 수단으로라도 저장 시도
        if progress:
            try:
                import json
                with open("progress_backup.json", "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                log("📁 로컬 백업 저장 완료: progress_backup.json")
            except:
                pass


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
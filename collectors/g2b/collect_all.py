import json
import os
from utils.logger import log
from utils.slack import send_slack_message
from utils.g2b_client import fetch_raw_data, append_to_year_file


PROGRESS_PATH = "progress.json"


def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        log("⚠ progress.json 없음 → 기본값 사용")
        return {
            "current_job": "물품",
            "current_year": 2014,
            "current_month": 1,
            "total_collected": 0,
            "daily_api_calls": 0,
        }

    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(p):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def increment_month(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


if __name__ == "__main__":
    log("🚀 G2B 자동 수집 시작")

    progress = load_progress()
    job = progress["current_job"]
    year = progress["current_year"]
    month = progress["current_month"]

    # Slack 시작 메시지
    send_slack_message(
        f"```\\n"
        f":rocket: G2B 수집 시작\\n"
        f"• 업무: {job}\\n"
        f"• 위치: {year}년 {month}월\\n"
        f"• 누적: {progress['total_collected']:,}건\\n"
        f"```"
    )

    # API 호출
    try:
        xml_text = fetch_raw_data(job, year, month)
    except Exception as e:
        send_slack_message(
            f"```\\n:x: 수집 오류 발생\\n→ {e}\\n```"
        )
        raise

    # 연단위 파일 Append
    filename = append_to_year_file(job, year, xml_text)

    # 건수 증가 (실제 XML 파싱 로직 추가 가능)
    progress["total_collected"] += 1
    progress["daily_api_calls"] += 1

    # 다음 월로 이동
    next_year, next_month = increment_month(year, month)
    progress["current_year"] = next_year
    progress["current_month"] = next_month

    save_progress(progress)

    # Slack 완료 메시지
    send_slack_message(
        f"```\\n"
        f":white_check_mark: G2B 수집 완료\\n"
        f"• 처리: {year}-{month}\\n"
        f"• 신규 수집: 1건 (샘플 카운트)\\n"
        f"• 누적: {progress['total_collected']:,}건\\n"
        f"• 다음: {next_year}-{next_month}\\n"
        f"```"
    )

    log("✔ 전체 프로세스 완료")

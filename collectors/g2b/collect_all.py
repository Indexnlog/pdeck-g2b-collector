import json
import os
from utils.g2b_client import fetch_raw_data, append_to_year_file
from utils.logger import log
from utils.slack import send_slack_message

PROGRESS_PATH = "progress.json"


def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {
            "업무": "물품",
            "current_year": 2014,
            "current_month": 1,
            "total_collected": 0
        }

    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(p):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def next_month(y, m):
    return (y+1, 1) if m == 12 else (y, m+1)


if __name__ == "__main__":
    progress = load_progress()

    업무 = progress["업무"]
    year = progress["current_year"]
    month = progress["current_month"]

    log(f"🚀 자동 수집 시작: {업무} {year}-{month}")

    # 1) API 수집
    try:
        xml_text = fetch_raw_data(업무, year, month)
        new_count = xml_text.count("<item>")
    except Exception as e:
        log(f"❌ API 실패: {e}")
        send_slack_message(f"❌ API 실패: {e}")
        raise

    # 2) 연도 파일 append
    path = append_to_year_file(업무, year, xml_text)

    # 3) 진행상태 갱신
    progress["total_collected"] += new_count
    progress["current_year"], progress["current_month"] = next_month(
        year, month)
    progress["last_run_date"] = "2025-12-15"

    save_progress(progress)

    # 4) Slack 알림
    message = (
        "```"
        f"✔ 데이터 수집 완료\n"
        f"• 진행: {업무} {year}년 {month}월\n"
        f"• 신규 수집: {new_count:,}건\n"
        f"• 누적: {progress['total_collected']:,}건\n"
        f"• 다음 예정: {progress['current_year']}년 {progress['current_month']}월\n"
        "```"
    )
    send_slack_message(message)

    log("🎉 완료")

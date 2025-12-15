import json
import os
from utils.g2b_client import get_monthly_data
from utils.logger import log
from utils.slack import send_slack_message

PROGRESS_PATH = "progress.json"


def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        log("⚠️ progress.json 없음 — 기본값 사용")
        return {"current_year": 2014, "current_month": 3, "total_collected": 0}

    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def increment_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


if __name__ == "__main__":
    progress = load_progress()
    year = progress["current_year"]
    month = progress["current_month"]

    # ▣ Slack 시작 메시지
    send_slack_message(
        f":large_blue_circle: 데이터 수집 시작\n"
        f"• 업무: {업무}\n"
        f"• 진행: {year}년 {month}월\n"
        f"• 누적: {progress.get('total_collected'):,}건"
    )

    # 수집
    try:
        items = get_monthly_data(year, month)
    except Exception as e:
        log(f"❌ API 오류: {e}")
        items = []

    if items:
        progress["total_collected"] += len(items)

    next_year, next_month = increment_month(year, month)

    progress["current_year"] = next_year
    progress["current_month"] = next_month

    save_progress(progress)

    # ▣ Slack 종료 메시지
    send_slack_message(
        f":white_check_mark: 데이터 수집 완료\n"
        f"• 처리: {업무} {year}년 {month}월\n"
        f"• 신규: {len(items):,}건\n"
        f"• 누적: {progress['total_collected']:,}건\n"
        f"• 다음: {next_year}년 {next_month}월"
    )

    log("✔ 전체 수집 종료")

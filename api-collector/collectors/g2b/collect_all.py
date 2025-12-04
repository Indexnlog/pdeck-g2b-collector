import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import time
import json
import sys

load_dotenv()

SERVICE_KEY = os.getenv('API_KEY')
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')
BASE_URL = "https://apis.data.go.kr/1230000/ao/CntrctInfoService"

PROGRESS_FILE = 'data/logs/progress.json'
MAX_DAILY_CALLS = 500

# 한국시간
KST = timezone(timedelta(hours=9))


# -------------------------------------------------
# 🔢 숫자 포맷 통일 함수
# -------------------------------------------------
def fmt(n):
    try:
        return f"{int(n):,}"
    except:
        return n


# -------------------------------------------------
# 💬 Slack 메시지 함수 (thread 지원)
# -------------------------------------------------
def send_slack_message(message, is_error=False, thread_ts=None):
    """Slack Bot Token으로 메시지 전송 (thread 지원)"""
    if not SLACK_TOKEN or not SLACK_CHANNEL_ID:
        return None

    emoji = "🔴" if is_error else "✅"

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": SLACK_CHANNEL_ID,
        "text": f"{emoji} {message}",
    }

    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()

        if not result.get("ok"):
            print(f"⚠ Slack 전송 실패: {result.get('error')}")
            return None

        return result.get("ts")

    except Exception as e:
        print(f"⚠ Slack 오류: {e}")
        return None


# -------------------------------------------------
# 🔄 진행 상황 파일 로드
# -------------------------------------------------
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress = json.load(f)

            today = datetime.now(KST).strftime('%Y-%m-%d')
            if progress.get('last_run_date') != today:
                progress['daily_api_calls'] = 0
                progress['last_run_date'] = today

            return progress

    return {
        'current_업무': '물품',
        'current_year': 2005,
        'current_month': 1,
        'daily_api_calls': 0,
        'last_run_date': datetime.now(KST).strftime('%Y-%m-%d'),
        'total_collected': 0
    }


# -------------------------------------------------
# 💾 진행 상황 저장
# -------------------------------------------------
def save_progress(progress):
    os.makedirs('data/logs', exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# -------------------------------------------------
# 📡 단일 월 데이터 수집
# -------------------------------------------------
def get_month_data(업무코드, year, month, progress, max_retries=3):
    endpoint = f"/getCntrctInfoList{업무코드}"
    url = BASE_URL + endpoint

    month_start = f"{year}{month:02d}010000"

    # 다음달 1일
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    last_day = (next_month - relativedelta(days=1)).day

    month_end = f"{year}{month:02d}{last_day}2359"

    all_items = []
    page = 1

    while True:
        if progress['daily_api_calls'] >= MAX_DAILY_CALLS:
            return None

        params = {
            'serviceKey': SERVICE_KEY,
            'numOfRows': 999,
            'pageNo': page,
            'inqryDiv': '1',
            'inqryBgnDt': month_start,
            'inqryEndDt': month_end
        }

        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                progress['daily_api_calls'] += 1

                if '<resultCode>00</resultCode>' in response.text:
                    if '<item>' not in response.text:
                        return all_items

                    all_items.append(response.text)
                    page += 1
                    time.sleep(0.5)
                    break

                else:
                    if attempt < max_retries - 1:
                        time.sleep(3)
                    else:
                        return all_items

            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return all_items

    return all_items


# -------------------------------------------------
# 🧠 연도별 파일 저장
# -------------------------------------------------
def save_year_file(filename, year_data, 업무명):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<contracts>\n')
        for data in year_data:
            if '<item>' in data:
                items = data.split('<item>')[1:]
                for item in items:
                    f.write('<item>' + item)
        f.write('</contracts>\n')


# -------------------------------------------------
# 🚀 전체 수집 with resume + Slack thread
# -------------------------------------------------
def collect_with_resume():
    start_time = datetime.now(KST)

    print("="*60)
    print("🚀 계약 데이터 수집 시작 (자동 재개)")
    print("="*60)

    os.makedirs('data/raw', exist_ok=True)
    os.makedirs('data/logs', exist_ok=True)

    progress = load_progress()

    # -------------------------------------------------
    # 🔵 Slack 시작 메시지 (thread 시작)
    # -------------------------------------------------
    thread_ts = send_slack_message(
        f"*데이터 수집 시작*\n\n"
        f"• 업무: `{progress['current_업무']}`\n"
        f"• 위치: `{progress['current_year']}년 {progress['current_month']}월`\n"
        f"• 누적: `{fmt(progress.get('total_collected', 0))}건`"
    )

    업무구분 = {'물품': 'Thng', '용역': 'Servc', '공사': 'Cnstwk'}
    업무리스트 = list(업무구분.keys())
    start_idx = 업무리스트.index(progress['current_업무'])

    end_year = datetime.now(KST).year
    today_collected = 0

    for 이름 in 업무리스트[start_idx:]:
        코드 = 업무구분[이름]
        start_year = progress['current_year'] if 이름 == progress['current_업무'] else 2005

        for year in range(start_year, end_year + 1):
            filename = f"data/raw/{이름}_{year}.xml"

            year_data = []
            start_month = progress['current_month'] if (
                year == progress['current_year'] and 이름 == progress['current_업무']) else 1

            for month in range(start_month, 13):

                if year == datetime.now(KST).year and month > datetime.now(KST).month:
                    break

                month_data = get_month_data(코드, year, month, progress)

                # 🔴 API 일일 제한 도달
                if month_data is None:
                    save_year_file(filename, year_data, 이름)
                    save_progress(progress)

                    send_slack_message(
                        f"*일일 API 제한 도달* ⏸️\n\n"
                        f"• 진행: `{이름} {year}년 {month}월`\n"
                        f"• 오늘 수집: `{fmt(today_collected)}건`\n"
                        f"• API 호출: `{fmt(progress['daily_api_calls'])}/{MAX_DAILY_CALLS}회`\n"
                        f"• 누적: `{fmt(progress.get('total_collected', 0))}건`\n\n"
                        f"내일 자동으로 이어서 수집합니다!",
                        thread_ts=thread_ts
                    )

                    return

                if month_data:
                    year_data.extend(month_data)
                    count = sum(d.count('<item>') for d in month_data)
                    today_collected += count
                    progress['total_collected'] += count

                progress['current_month'] = month + 1
                save_progress(progress)

            save_year_file(filename, year_data, 이름)
            progress['current_year'] = year + 1
            progress['current_month'] = 1
            save_progress(progress)

        progress['current_업무'] = 업무리스트[업무리스트.index(
            이름) + 1] if 이름 != 업무리스트[-1] else '완료'
        progress['current_year'] = 2005
        progress['current_month'] = 1
        save_progress(progress)

    # -------------------------------------------------
    # 🎉 전체 수집 완료 slack 메시지
    # -------------------------------------------------
    elapsed = datetime.now(KST) - start_time
    send_slack_message(
        f"*전체 수집 완료!* 🎉\n\n"
        f"• 오늘 수집: `{fmt(today_collected)}건`\n"
        f"• 총 누적: `{fmt(progress.get('total_collected', 0))}건`\n"
        f"• 소요시간: `{elapsed.seconds//3600}시간 {(elapsed.seconds//60)%60}분`",
        thread_ts=thread_ts
    )


# -------------------------------------------------
# 🏁 main
# -------------------------------------------------
if __name__ == "__main__":
    try:
        collect_with_resume()
    except Exception as e:
        send_slack_message(f"*오류 발생* 💥\n```{str(e)}```", is_error=True)
        raise

import os
import time
import requests
from utils.logger import log

API_KEY = os.getenv("API_KEY")


def fetch_raw_data(job, year, month, retries=5):
    """나라장터 원본 XML 다운로드 (재시도 포함)"""

    url = "https://apis.data.go.kr/1230000/ScsbidInfoService/getBidInfoList"

    params = {
        "serviceKey": API_KEY,
        "pageNo": 1,
        "numOfRows": 9999,
        "inqryDiv": 1,
        "inqryBgnDt": f"{year}{month:02}01",
        "inqryEndDt": f"{year}{month:02}28",
        "type": "xml",
    }

    for attempt in range(1, retries + 1):
        resp = requests.get(url, params=params)

        if resp.status_code == 200:
            log(f"📄 XML 다운로드 성공: {year}-{month}")
            return resp.text

        log(f"⚠ API 오류 {resp.status_code} → 재시도 {attempt}/{retries}")
        time.sleep(2 + attempt)  # 점진적 대기 증가

    raise Exception(f"API 반복 오류 발생: {year}-{month}")


def append_to_year_file(job, year, xml_text):
    """연단위 파일에 월 데이터를 계속 Append"""
    filename = f"{job}_{year}.xml"

    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"\n<!-- {year}년 데이터 추가 -->\n")
        f.write(xml_text)

    log(f"💾 연단위 파일 저장 완료 → {filename}")
    return filename

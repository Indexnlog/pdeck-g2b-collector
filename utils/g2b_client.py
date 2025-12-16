import os
import requests
from utils.logger import log

API_KEY = os.getenv("API_KEY")

BASE_URL = "https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfo"


def fetch_raw_data(업무, year, month):
    """특정 연/월 데이터를 API로 수집하여 Python 리스트로 반환"""
    params = {
        "serviceKey": API_KEY,
        "numOfRows": 9999,
        "pageNo": 1,
        "inqryDiv": "1",
        "inqryBgnDt": f"{year}{month:02d}01",
        "inqryEndDt": f"{year}{month:02d}28",
    }

    response = requests.get(BASE_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"API 오류: {response.status_code}")

    return response.text  # XML 문자열 반환


def append_to_year_file(업무, year, xml_text):
    """연도별 XML 파일로 저장/추가"""

    folder = "data/raw"
    os.makedirs(folder, exist_ok=True)

    path = f"{folder}/{업무}_{year}.xml"

    # 새 파일 생성이면 루트 태그부터
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("<items>\n")

    # XML append
    with open(path, "a", encoding="utf-8") as f:
        f.write(xml_text)
        f.write("\n")

    log(f"📁 연도 파일 업데이트 완료 → {path}")
    return path

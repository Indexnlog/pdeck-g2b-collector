import os
import requests
import time
from datetime import datetime


# .env 파일 로드 추가
from dotenv import load_dotenv
load_dotenv("collectors/g2b/.env")  # 경로 명시적으로 지정


def test_g2b_api():
    """G2B API 기본 연결 테스트"""

    api_key = os.getenv("API_KEY")
    if not api_key:
        print("❌ API_KEY 환경변수가 없습니다")
        return

    print(f"🔑 API Key 확인: {api_key[:10]}...")

    # 1. 기본 연결 테스트
    base_url = "http://apis.data.go.kr/1230000/ao/CntrctInfoService"
    operation = "getCntrctInfoListThng"
    url = f"{base_url}/{operation}"

    print(f"🌐 테스트 URL: {url}")

    # 2. API 명세에 맞는 정확한 파라미터
    params = {
        "ServiceKey": api_key,  # serviceKey → ServiceKey (대문자 S)
        "numOfRows": 10,
        "pageNo": 1,
        "inqryDiv": 1,
        "inqryBgnDt": "202412010000",  # 시간 포함 (YYYYMMDDHHMM)
        "inqryEndDt": "202412012359",  # 시간 포함 (YYYYMMDDHHMM)
        "type": "xml"
    }

    print("📋 요청 파라미터:")
    for k, v in params.items():
        if k == "ServiceKey":
            print(f"  {k}: {v[:10]}...")
        else:
            print(f"  {k}: {v}")

    # 3. 여러 타임아웃으로 테스트
    timeouts = [30, 60, 120]

    for timeout in timeouts:
        print(f"\n⏱️ 타임아웃 {timeout}초로 테스트 중...")
        start_time = time.time()

        try:
            response = requests.get(url, params=params, timeout=timeout)
            end_time = time.time()

            print(f"✅ 응답 성공! ({end_time - start_time:.1f}초)")
            print(f"📊 HTTP 상태: {response.status_code}")
            print(f"📦 응답 크기: {len(response.text)} bytes")

            # XML 내용 일부 출력
            response_preview = response.text[:500] + \
                "..." if len(response.text) > 500 else response.text
            print(f"📄 응답 내용 미리보기:\n{response_preview}")
            break

        except requests.Timeout:
            print(f"❌ 타임아웃 발생 ({timeout}초)")

        except requests.ConnectionError as e:
            print(f"❌ 연결 오류: {e}")
            break

        except Exception as e:
            print(f"❌ 기타 오류: {e}")
            break

    # 4. 다른 날짜로도 테스트
    print("\n📅 다른 날짜로 테스트...")
    test_dates = [
        ("202412010000", "202412012359"),  # 최근 (시간 포함)
        ("202401010000", "202401012359"),  # 2024년 1월
        ("201401010000", "201401012359"),  # 2014년 1월 (현재 수집 중)
    ]

    for start_date, end_date in test_dates:
        print(f"\n📍 날짜 범위: {start_date} ~ {end_date}")
        params["inqryBgnDt"] = start_date
        params["inqryEndDt"] = end_date

        try:
            response = requests.get(url, params=params, timeout=30)
            print(
                f"✅ {start_date[:8]}: HTTP {response.status_code}, {len(response.text)} bytes")
        except:
            print(f"❌ {start_date[:8]}: 실패")


if __name__ == "__main__":
    print("🧪 G2B API 진단 테스트 시작")
    print(f"🕐 실행 시간: {datetime.now()}")
    test_g2b_api()
    print("🏁 테스트 완료")

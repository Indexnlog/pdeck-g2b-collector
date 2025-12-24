import os
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수 확인
api_key = os.getenv("API_KEY")
if not api_key:
    print("❌ API_KEY가 없습니다. .env 파일을 확인해주세요.")
    exit()

print(f"🔑 API Key 로드 완료: {api_key[:5]}...")

# ✅ 계약정보 서비스 URL (물품)
url = "http://apis.data.go.kr/1230000/ao/CntrctInfoService/getCntrctInfoListThng"

params = {
    "serviceKey": api_key,
    "numOfRows": 10,         # 10개만 요청해서 빠르게 확인
    "pageNo": 1,
    "inqryDiv": 1,
    "inqryBgnDate": "20240101",  # 2024년 1월 1일
    "inqryEndDate": "20240103",  # 2024년 1월 3일
    "type": "xml"
}

try:
    print("📡 2024년 데이터(물품 계약) 요청 중... (Timeout 30초)")
    # 타임아웃을 넉넉하게 30초 줌 (본 코드는 180초로 설정했음)
    response = requests.get(url, params=params, timeout=30)

    print(f"✅ 응답 코드: {response.status_code}")

    if response.status_code == 200:
        # 데이터 앞부분 500글자만 출력해서 눈으로 확인
        print(f"📄 응답 데이터(일부):\n{response.text[:500]}")

        if "<resultCode>00</resultCode>" in response.text:
            print("\n🎉 [성공] 정상적으로 데이터를 받아왔습니다!")
        elif "<resultCode>03</resultCode>" in response.text:
            print("\nℹ️ [정상] 요청은 성공했으나 해당 기간에 데이터가 없습니다.")
        else:
            print("\n⚠️ [주의] 에러 코드가 포함되어 있을 수 있습니다.")
    else:
        print("❌ 서버 오류 발생")

except Exception as e:
    print(f"❌ 연결 실패: {e}")

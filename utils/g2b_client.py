import os
import time
import requests
import calendar
import xml.etree.ElementTree as ET
from utils.logger import log


class G2BClient:
    # ✅ 1. 핵심: 계약정보 서비스 URL로 변경 (매출 데이터용)
    BASE_URL = "http://apis.data.go.kr/1230000/ao/CntrctInfoService"

    # 작업별 오퍼레이션 매핑
    OPERATION_MAP = {
        "물품": "getCntrctInfoListThng",
        "공사": "getCntrctInfoListCnstwk",
        "용역": "getCntrctInfoListServc",
        "외자": "getCntrctInfoListFrgcpt"
    }

    def __init__(self, api_key):
        self.api_key = api_key

    def fetch_data(self, job_type, year, month, retries=5):
        """
        API 호출 및 정밀한 에러 핸들링
        """
        if not self.api_key:
            raise ValueError("API_KEY가 설정되지 않았습니다.")

        if job_type not in self.OPERATION_MAP:
            return {'success': False, 'code': 'ERR', 'msg': f"잘못된 업무 구분: {job_type}"}

        operation = self.OPERATION_MAP[job_type]

        # ✅ 2. 지수 님의 훌륭한 날짜 계산 로직 적용
        last_day = calendar.monthrange(year, month)[1]
        start_dt = f"{year}{month:02d}01"
        end_dt = f"{year}{month:02d}{last_day}"

        params = {
            "serviceKey": self.api_key,
            "numOfRows": 9999,
            "pageNo": 1,
            "inqryDiv": 1,      # 1: 계약체결일 기준
            "inqryBgnDate": start_dt,
            "inqryEndDate": end_dt,
            "type": "xml"
        }

        url = f"{self.BASE_URL}/{operation}"

        for attempt in range(1, retries + 1):
            try:
                # 타임아웃 30초 설정
                response = requests.get(url, params=params, timeout=30)
                response.encoding = 'utf-8'  # 한글 깨짐 방지

                if response.status_code != 200:
                    log(f"⚠ HTTP 오류 {response.status_code} (시도 {attempt}/{retries})")
                    time.sleep(2 + attempt)
                    continue

                # XML 파싱 및 결과 코드 분석
                try:
                    root = ET.fromstring(response.text)

                    # ✅ 3. 문서 기반 결과 코드(resultCode) 분석 로직
                    result_code = root.findtext('.//resultCode')
                    result_msg = root.findtext('.//resultMsg')

                    if not result_code:
                        # 가끔 HTML 에러가 올 때가 있음
                        raise ValueError("XML 구조가 올바르지 않음 (resultCode 누락)")

                    # [Case 1] 정상 성공 (00)
                    if result_code == '00':
                        items = root.findall('.//item')
                        return {
                            'success': True,
                            'code': '00',
                            'msg': '정상 수집',
                            'data': response.text,
                            'count': len(items)
                        }

                    # [Case 2] 데이터 없음 (03) -> 성공으로 간주하되 데이터는 비움
                    elif result_code == '03':
                        return {
                            'success': True,
                            'code': '03',
                            'msg': '데이터 없음 (정상)',
                            'data': None,
                            'count': 0
                        }

                    # [Case 3] 트래픽/인증 에러 (20, 22, 99) -> 즉시 중단 필요
                    elif result_code in ['20', '21', '22', '99']:
                        return {
                            'success': False,
                            'code': result_code,
                            'msg': f"API 호출 제한/인증 오류: {result_msg}"
                        }

                    # [Case 4] 서버 에러 (05 등) -> 재시도 필요
                    else:
                        log(f"⚠ API 서버 메시지: {result_msg} (코드: {result_code})")
                        # 루프를 돌며 재시도

                except ET.ParseError:
                    log(f"⚠ XML 파싱 실패 (시도 {attempt}/{retries})")

            except requests.RequestException as e:
                log(f"⚠ 네트워크 오류: {e} (시도 {attempt}/{retries})")

            # 재시도 대기
            if attempt < retries:
                time.sleep(2 + attempt)

        # 모든 재시도 실패 시
        return {'success': False, 'code': 'TIMEOUT', 'msg': '최대 재시도 횟수 초과'}

# 호환성 래퍼 함수


def fetch_raw_data(job_type, year, month):
    client = G2BClient(os.getenv("API_KEY"))
    return client.fetch_data(job_type, year, month)


# ✅ 4. 지수 님의 파일 저장 로직 유지 (데이터 폴더 생성, 헤더 처리 등)
def append_to_year_file(job, year, xml_text):
    if not xml_text:
        return None

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(data_dir, f"{job}_{year}.xml")

    file_exists = os.path.exists(filename)

    try:
        with open(filename, "a", encoding="utf-8") as f:
            # 새 파일이면 루트 태그 시작
            if not file_exists:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(f'<root year="{year}" category="{job}">\n')

            # 주석 및 데이터 추가
            f.write(f"\n\n")
            f.write(xml_text)
            f.write("\n")

        return filename
    except Exception as e:
        log(f"❌ 파일 저장 실패: {e}")
        return None

import os
import time
import requests
import calendar
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import random

# logger 임포트 (같은 utils 폴더 내)
try:
    from .logger import log
except ImportError:
    try:
        from utils.logger import log
    except ImportError:
        # 로거가 없으면 print로 대체
        def log(msg):
            print(f"[LOG] {msg}")


class G2BClient:
    # ✅ 올바른 계약정보 서비스 URL
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
        self.session = self._create_session()

    def _create_session(self):
        """강화된 세션 설정"""
        session = requests.Session()

        # 재시도 전략 설정
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504, 408],
            backoff_factor=2
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def fetch_data(self, job_type, year, month, retries=5):
        """
        G2B API 호출 및 데이터 수집
        
        Args:
            job_type: 업무구분 (물품, 공사, 용역, 외자)
            year: 조회 년도
            month: 조회 월
            retries: 재시도 횟수
            
        Returns:
            tuple: (xml_content, item_count, api_calls_used)
        """
        if not self.api_key:
            raise ValueError("API_KEY가 설정되지 않았습니다.")

        if job_type not in self.OPERATION_MAP:
            log(f"❌ 잘못된 업무 구분: {job_type}")
            return "", 0, 0

        operation = self.OPERATION_MAP[job_type]
        
        # 월 시작일과 종료일 계산
        start_date = f"{year}{month:02d}010000"  # YYYYMMDDHHMM
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}{month:02d}{last_day}2359"
        
        log(f"📅 조회 기간: {start_date} ~ {end_date}")
        
        # 페이지별 수집
        all_items = []
        api_calls_used = 0
        page_no = 1
        max_pages = 500  # API 한도 고려
        
        while page_no <= max_pages:
            try:
                # API 파라미터
                params = {
                    "serviceKey": self.api_key,
                    "numOfRows": 1000,  # 최대 페이지 크기
                    "pageNo": page_no,
                    "inqryDiv": 1,  # 등록일시 기준
                    "inqryBgnDt": start_date,
                    "inqryEndDt": end_date
                }
                
                # API 호출
                url = f"{self.BASE_URL}/{operation}"
                log(f"📡 API 호출: {operation} (페이지 {page_no})")
                
                response = self.session.get(
                    url, 
                    params=params,
                    timeout=30
                )
                
                api_calls_used += 1
                
                # 응답 상태 확인
                if response.status_code != 200:
                    log(f"❌ HTTP 오류: {response.status_code}")
                    break
                
                # XML 파싱
                try:
                    root = ET.fromstring(response.text)
                    
                    # 에러 코드 확인
                    result_code = root.find('.//resultCode')
                    if result_code is not None and result_code.text != "00":
                        result_msg = root.find('.//resultMsg')
                        error_msg = result_msg.text if result_msg is not None else "Unknown error"
                        log(f"❌ API 에러: {result_code.text} - {error_msg}")
                        break
                    
                    # 데이터 추출
                    items = root.findall('.//item')
                    if not items:
                        log(f"ℹ️ 페이지 {page_no}: 데이터 없음 (수집 완료)")
                        break
                    
                    all_items.extend(items)
                    log(f"✅ 페이지 {page_no}: {len(items)}건 수집 (총 {len(all_items)}건)")
                    
                    # 다음 페이지
                    page_no += 1
                    
                    # 요청 간격 (API 제한 방지)
                    time.sleep(0.1)
                    
                except ET.ParseError as e:
                    log(f"❌ XML 파싱 오류: {e}")
                    break
                    
            except requests.exceptions.RequestException as e:
                log(f"❌ 네트워크 오류: {e}")
                if retries > 0:
                    log(f"⏳ {retries}회 재시도 남음...")
                    time.sleep(2)
                    retries -= 1
                    continue
                else:
                    break
        
        # 결과 XML 생성
        if all_items:
            xml_content = ""
            for item in all_items:
                xml_content += ET.tostring(item, encoding='unicode') + "\n"
            
            log(f"🎯 수집 완료: {len(all_items):,}건 (API 호출: {api_calls_used}회)")
            return xml_content, len(all_items), api_calls_used
        else:
            log(f"ℹ️ 수집 결과: 0건 (API 호출: {api_calls_used}회)")
            return "", 0, api_calls_used

    def test_connection(self):
        """API 연결 테스트"""
        try:
            # 간단한 테스트 호출
            params = {
                "serviceKey": self.api_key,
                "numOfRows": 1,
                "pageNo": 1,
                "inqryDiv": 1,
                "inqryBgnDt": "202401010000",
                "inqryEndDt": "202401012359"
            }
            
            url = f"{self.BASE_URL}/getCntrctInfoListThng"
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                log("✅ G2B API 연결 테스트 성공")
                return True
            else:
                log(f"❌ G2B API 연결 실패: {response.status_code}")
                return False
                
        except Exception as e:
            log(f"❌ G2B API 테스트 오류: {e}")
            return False
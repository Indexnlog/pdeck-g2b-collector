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

# 에러 핸들링 임포트
try:
    from .api_error_handler import (
        retry_on_error,
        APIErrorHandler,
        ParseError,
        APIResponseError,
        ValidationError,
        RateLimitError
    )
except ImportError:
    try:
        from utils.api_error_handler import (
            retry_on_error,
            APIErrorHandler,
            ParseError,
            APIResponseError,
            ValidationError,
            RateLimitError
        )
    except ImportError:
        # 에러 핸들러가 없으면 기본 동작
        log("⚠️ api_error_handler를 찾을 수 없습니다. 기본 에러 처리를 사용합니다.")

        def retry_on_error(max_retries=3, base_delay=1.0, on_retry=None, on_final_failure=None):
            def decorator(func):
                return func
            return decorator

        class APIErrorHandler:
            @staticmethod
            def handle_http_response(response):
                response.raise_for_status()

            @staticmethod
            def handle_requests_error(error):
                return error

        class ParseError(Exception):
            pass

        class APIResponseError(Exception):
            pass

        class ValidationError(Exception):
            pass

        class RateLimitError(Exception):
            pass


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

    def fetch_pages(self, job_type, year, month, retries=5):
        """
        G2B API 페이지별 제너레이터 — 메모리 효율적.
        한 페이지(999건)씩 yield하므로 호출자가 즉시 DB insert 가능.

        Yields:
            tuple: (xml_items: list[Element], api_calls_used: int)
        """
        if not self.api_key:
            raise ValidationError("API_KEY가 설정되지 않았습니다.")

        if job_type not in self.OPERATION_MAP:
            raise ValidationError(
                f"잘못된 업무구분: {job_type}. "
                f"가능한 값: {', '.join(self.OPERATION_MAP.keys())}"
            )

        operation = self.OPERATION_MAP[job_type]
        start_date = f"{year}{month:02d}010000"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}{month:02d}{last_day}2359"

        log(f"📅 조회 기간: {start_date} ~ {end_date}")

        page_no = 1
        max_pages = 500

        while page_no <= max_pages:
            try:
                xml_items, page_api_calls = self._fetch_single_page(
                    operation, start_date, end_date, page_no, retries
                )

                if not xml_items:
                    log(f"ℹ️ 페이지 {page_no}: 데이터 없음 (수집 완료)")
                    break

                log(f"✅ 페이지 {page_no}: {len(xml_items)}건 수집")
                yield xml_items, page_api_calls

                page_no += 1
                time.sleep(0.1)

            except (APIResponseError, ParseError, RateLimitError) as e:
                log(f"❌ API/파싱 에러 (페이지 {page_no}): {e}")
                raise

            except Exception as e:
                log(f"❌ 페이지 {page_no} 수집 실패 (상위로 전파): {e}")
                raise

    def fetch_data(self, job_type, year, month, retries=5):
        """하위 호환용 — 소량 데이터에만 사용. 대량은 fetch_pages() 권장."""
        all_items = []
        api_calls_used = 0
        for xml_items, page_calls in self.fetch_pages(job_type, year, month, retries):
            all_items.extend(xml_items)
            api_calls_used += page_calls

        if all_items:
            xml_content = ""
            for item in all_items:
                xml_content += ET.tostring(item, encoding='unicode') + "\n"
            log(f"🎯 수집 완료: {len(all_items):,}건 (API 호출: {api_calls_used}회)")
            return xml_content, len(all_items), api_calls_used
        else:
            log(f"ℹ️ 수집 결과: 0건 (API 호출: {api_calls_used}회)")
            return "", 0, api_calls_used

    def _fetch_single_page(self, operation, start_date, end_date, page_no, max_retries):
        """
        단일 페이지 데이터 fetch (재시도 로직 포함)

        Returns:
            tuple: (items, api_calls_used)
        """
        retries = max_retries
        last_error = None

        while retries >= 0:
            try:
                # API 파라미터
                params = {
                    "serviceKey": self.api_key,
                    "numOfRows": 999,
                    "pageNo": page_no,
                    "inqryDiv": "1",
                    "inqryBgnDt": start_date,
                    "inqryEndDt": end_date
                }

                # API 호출
                url = f"{self.BASE_URL}/{operation}"
                log(f"📡 API 호출: {operation} (페이지 {page_no})")

                response = self.session.get(url, params=params, timeout=60)

                # HTTP 상태 검증
                try:
                    APIErrorHandler.handle_http_response(response)
                except Exception as e:
                    raise APIErrorHandler.handle_requests_error(e)

                # XML 파싱
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError as e:
                    raise ParseError(f"XML 파싱 실패: {e}")

                # API 에러 코드 확인
                result_code = root.find('.//resultCode')
                if result_code is not None and result_code.text != "00":
                    result_msg = root.find('.//resultMsg')
                    error_msg = result_msg.text if result_msg is not None else "Unknown error"

                    # 특정 에러 코드 처리
                    if result_code.text == "99":
                        raise RateLimitError(f"API 한도 초과: {error_msg}")
                    else:
                        raise APIResponseError(result_code.text, error_msg)

                # 데이터 추출
                items = root.findall('.//item')
                return items, 1  # (items, api_calls_used)

            except (APIResponseError, ParseError, RateLimitError):
                # 재시도 불가능한 에러는 즉시 발생
                raise

            except requests.exceptions.RequestException as e:
                last_error = e
                if retries > 0:
                    wait_time = 2 ** (max_retries - retries)  # 지수 백오프
                    log(f"⏳ 네트워크 오류, {wait_time}초 후 재시도 ({retries}회 남음): {e}")
                    time.sleep(wait_time)
                    retries -= 1
                else:
                    log(f"❌ 최대 재시도 횟수 초과: {e}")
                    raise APIErrorHandler.handle_requests_error(e)

            except Exception as e:
                last_error = e
                if retries > 0:
                    log(f"⚠️ 예상치 못한 오류, 재시도 ({retries}회 남음): {e}")
                    time.sleep(2)
                    retries -= 1
                else:
                    log(f"❌ 최대 재시도 횟수 초과: {e}")
                    raise

        # 모든 재시도 실패
        if last_error:
            raise last_error
        return [], 1

    @retry_on_error(
        max_retries=2,
        base_delay=1.0,
        on_retry=lambda e, attempt: log(f"⏳ 연결 테스트 재시도 {attempt}/2: {e}")
    )
    def test_connection(self):
        """
        API 연결 테스트 (자동 재시도 적용)

        Returns:
            bool: 연결 성공 여부
        """
        try:
            # 간단한 테스트 호출
            params = {
                "serviceKey": self.api_key,
                "numOfRows": 1,
                "pageNo": 1,
                "inqryDiv": "1",  # 문자열로 수정
                "inqryBgnDt": "202401010000",
                "inqryEndDt": "202401012359"
            }

            url = f"{self.BASE_URL}/getCntrctInfoListThng"
            response = self.session.get(url, params=params, timeout=10)

            # HTTP 상태 검증
            APIErrorHandler.handle_http_response(response)

            # XML 파싱 및 에러 확인
            try:
                root = ET.fromstring(response.text)
                result_code = root.find('.//resultCode')

                if result_code is not None and result_code.text != "00":
                    result_msg = root.find('.//resultMsg')
                    error_msg = result_msg.text if result_msg is not None else "Unknown error"
                    log(f"❌ G2B API 테스트 실패: {result_code.text} - {error_msg}")
                    return False

            except ET.ParseError as e:
                log(f"❌ 응답 파싱 실패: {e}")
                return False

            log("✅ G2B API 연결 테스트 성공")
            return True

        except requests.exceptions.RequestException as e:
            log(f"❌ G2B API 연결 실패: {e}")
            raise APIErrorHandler.handle_requests_error(e)

        except Exception as e:
            log(f"❌ G2B API 테스트 오류: {e}")
            return False
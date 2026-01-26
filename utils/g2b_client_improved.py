"""
개선된 G2B API 클라이언트
api_error_handler를 활용한 강화된 에러 처리
"""

import os
import time
import requests
import calendar
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 에러 핸들링 유틸리티
from utils.api_error_handler import (
    retry_on_error,
    error_context,
    APIErrorHandler,
    ParseError,
    APIResponseError,
    ValidationError,
    RateLimitError
)

try:
    from .logger import log
except ImportError:
    try:
        from utils.logger import log
    except ImportError:
        def log(msg):
            print(f"[LOG] {msg}")


class G2BClientImproved:
    """개선된 G2B API 클라이언트"""

    BASE_URL = "http://apis.data.go.kr/1230000/ao/CntrctInfoService"

    OPERATION_MAP = {
        "물품": "getCntrctInfoListThng",
        "공사": "getCntrctInfoListCnstwk",
        "용역": "getCntrctInfoListServc",
        "외자": "getCntrctInfoListFrgcpt"
    }

    def __init__(self, api_key: str, max_retries: int = 3):
        """
        Args:
            api_key: G2B API 키
            max_retries: 최대 재시도 횟수
        """
        if not api_key:
            raise ValidationError("API_KEY가 제공되지 않았습니다")

        self.api_key = api_key
        self.max_retries = max_retries
        self.session = self._create_session()
        self.daily_api_calls = 0
        self.daily_limit = 500

    def _create_session(self):
        """강화된 세션 설정"""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            backoff_factor=2,
            raise_on_status=False  # 직접 처리
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _validate_params(self, job_type: str, year: int, month: int):
        """입력 파라미터 검증"""
        if job_type not in self.OPERATION_MAP:
            raise ValidationError(
                f"잘못된 업무구분: {job_type}. "
                f"가능한 값: {', '.join(self.OPERATION_MAP.keys())}"
            )

        current_year = time.localtime().tm_year
        if year < 2000 or year > current_year + 1:
            raise ValidationError(f"유효하지 않은 연도: {year}")

        if month < 1 or month > 12:
            raise ValidationError(f"유효하지 않은 월: {month}")

    def _check_rate_limit(self):
        """API 호출 한도 확인"""
        if self.daily_api_calls >= self.daily_limit:
            raise RateLimitError(
                f"일일 API 호출 한도({self.daily_limit}회)를 초과했습니다"
            )

    def _build_params(self, year: int, month: int, page_no: int = 1):
        """API 파라미터 생성"""
        start_date = f"{year}{month:02d}010000"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}{month:02d}{last_day}2359"

        return {
            "serviceKey": self.api_key,
            "numOfRows": 999,
            "pageNo": page_no,
            "inqryDiv": "1",
            "inqryBgnDt": start_date,
            "inqryEndDt": end_date
        }

    @retry_on_error(
        max_retries=3,
        base_delay=1.0,
        on_retry=lambda e, attempt: log(f"⏳ 재시도 {attempt}회: {e}")
    )
    def _fetch_page(self, operation: str, params: dict) -> requests.Response:
        """단일 페이지 데이터 fetch (자동 재시도 적용)"""
        try:
            url = f"{self.BASE_URL}/{operation}"
            response = self.session.get(url, params=params, timeout=30)

            # HTTP 상태 검증
            APIErrorHandler.handle_http_response(response)

            self.daily_api_calls += 1
            return response

        except requests.exceptions.RequestException as e:
            raise APIErrorHandler.handle_requests_error(e)

    def _parse_xml_response(self, xml_text: str) -> ET.Element:
        """XML 응답 파싱"""
        try:
            return ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise ParseError(f"XML 파싱 실패: {e}", original_error=e)

    def _check_api_error(self, root: ET.Element):
        """API 응답 내 에러 코드 확인"""
        result_code = root.find('.//resultCode')

        if result_code is not None and result_code.text != "00":
            result_msg = root.find('.//resultMsg')
            error_msg = result_msg.text if result_msg is not None else "Unknown error"

            # 특정 에러 코드 처리
            if result_code.text in ["30", "31", "32", "33"]:
                raise ValidationError(f"입력값 오류: {error_msg}")
            elif result_code.text == "99":
                raise RateLimitError(f"API 한도 초과: {error_msg}")
            else:
                raise APIResponseError(result_code.text, error_msg)

    def fetch_data(
        self,
        job_type: str,
        year: int,
        month: int,
        max_pages: int = 500
    ) -> tuple[str, int, int]:
        """
        G2B API 호출 및 데이터 수집

        Args:
            job_type: 업무구분 (물품, 공사, 용역, 외자)
            year: 조회 년도
            month: 조회 월
            max_pages: 최대 페이지 수

        Returns:
            tuple: (xml_content, item_count, api_calls_used)

        Raises:
            ValidationError: 입력값 검증 실패
            RateLimitError: API 호출 한도 초과
            APIResponseError: API 응답 에러
            NetworkError: 네트워크 오류
            ParseError: XML 파싱 오류
        """
        # 입력값 검증
        self._validate_params(job_type, year, month)

        # API 한도 확인
        self._check_rate_limit()

        operation = self.OPERATION_MAP[job_type]
        context_name = f"{job_type} {year}년 {month}월 데이터 수집"

        with error_context(context_name):
            all_items = []
            api_calls_used = 0
            page_no = 1

            log(f"📅 조회 기간: {year}-{month:02d}")

            while page_no <= max_pages:
                # 페이지별 파라미터
                params = self._build_params(year, month, page_no)

                try:
                    log(f"📡 페이지 {page_no} 요청")

                    # API 호출 (자동 재시도 적용)
                    response = self._fetch_page(operation, params)
                    api_calls_used += 1

                    # XML 파싱
                    root = self._parse_xml_response(response.text)

                    # API 에러 확인
                    self._check_api_error(root)

                    # 데이터 추출
                    items = root.findall('.//item')

                    if not items:
                        log(f"ℹ️ 페이지 {page_no}: 데이터 없음 (수집 완료)")
                        break

                    all_items.extend(items)
                    log(f"✅ 페이지 {page_no}: {len(items)}건 (총 {len(all_items):,}건)")

                    page_no += 1

                    # 요청 간격 (API 제한 방지)
                    time.sleep(0.1)

                except (ValidationError, RateLimitError, APIResponseError):
                    # 복구 불가능한 에러는 즉시 중단
                    raise

                except Exception as e:
                    # 기타 에러는 로깅 후 중단
                    log(f"❌ 페이지 {page_no} 수집 실패: {e}")
                    break

            # 결과 XML 생성
            if all_items:
                xml_content = ""
                for item in all_items:
                    xml_content += ET.tostring(item, encoding='unicode') + "\n"

                log(f"🎯 총 {len(all_items):,}건 수집 완료 (API 호출: {api_calls_used}회)")
                return xml_content, len(all_items), api_calls_used
            else:
                log(f"ℹ️ 수집 결과: 0건 (API 호출: {api_calls_used}회)")
                return "", 0, api_calls_used

    @retry_on_error(max_retries=2, base_delay=1.0)
    def test_connection(self) -> bool:
        """
        API 연결 테스트

        Returns:
            bool: 연결 성공 여부
        """
        with error_context("G2B API 연결 테스트"):
            try:
                params = self._build_params(2024, 1, 1)
                params["numOfRows"] = 1

                operation = self.OPERATION_MAP["물품"]
                response = self._fetch_page(operation, params)

                root = self._parse_xml_response(response.text)
                self._check_api_error(root)

                log("✅ G2B API 연결 테스트 성공")
                return True

            except Exception as e:
                log(f"❌ G2B API 연결 테스트 실패: {e}")
                return False

    def reset_daily_limit(self):
        """일일 API 호출 카운터 리셋"""
        self.daily_api_calls = 0
        log("🔄 일일 API 호출 카운터 리셋")

    def get_api_usage(self) -> dict:
        """API 사용량 정보 반환"""
        return {
            "daily_calls": self.daily_api_calls,
            "daily_limit": self.daily_limit,
            "remaining": self.daily_limit - self.daily_api_calls,
            "usage_percent": (self.daily_api_calls / self.daily_limit) * 100
        }


# ============================================================
# 사용 예제
# ============================================================

if __name__ == "__main__":
    # 환경변수에서 API 키 로드
    api_key = os.getenv("API_KEY")

    if not api_key:
        print("❌ API_KEY 환경변수가 설정되지 않았습니다")
        exit(1)

    try:
        # 클라이언트 생성
        client = G2BClientImproved(api_key, max_retries=3)

        # 연결 테스트
        if client.test_connection():
            print("✅ API 연결 성공")

        # 데이터 수집
        xml_data, count, calls = client.fetch_data("물품", 2024, 1)

        print(f"\n수집 결과:")
        print(f"  - 수집 건수: {count:,}건")
        print(f"  - API 호출: {calls}회")

        # 사용량 확인
        usage = client.get_api_usage()
        print(f"\nAPI 사용량:")
        print(f"  - 사용: {usage['daily_calls']}/{usage['daily_limit']}회")
        print(f"  - 남은 호출: {usage['remaining']}회")
        print(f"  - 사용률: {usage['usage_percent']:.1f}%")

    except ValidationError as e:
        print(f"❌ 입력값 오류: {e}")
    except RateLimitError as e:
        print(f"❌ API 한도 초과: {e}")
    except APIResponseError as e:
        print(f"❌ API 에러: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

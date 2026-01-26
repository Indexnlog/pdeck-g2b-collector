"""
API 에러 핸들링 유틸리티
G2B API 호출 시 발생할 수 있는 다양한 에러를 체계적으로 처리
"""

import time
import requests
from enum import Enum
from typing import Optional, Callable, Any
from functools import wraps

try:
    from .logger import log
except ImportError:
    def log(msg):
        print(f"[LOG] {msg}")


# ============================================================
# 에러 타입 정의
# ============================================================

class APIErrorType(Enum):
    """API 에러 타입 분류"""
    NETWORK_ERROR = "네트워크 오류"
    TIMEOUT_ERROR = "타임아웃"
    HTTP_ERROR = "HTTP 상태 코드 오류"
    API_ERROR = "API 응답 오류"
    PARSE_ERROR = "파싱 오류"
    RATE_LIMIT_ERROR = "API 호출 한도 초과"
    AUTH_ERROR = "인증 오류"
    VALIDATION_ERROR = "입력값 검증 오류"
    UNKNOWN_ERROR = "알 수 없는 오류"


# ============================================================
# 커스텀 예외 클래스
# ============================================================

class APIException(Exception):
    """API 관련 기본 예외 클래스"""

    def __init__(
        self,
        message: str,
        error_type: APIErrorType,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.response_text = response_text
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        error_info = f"[{self.error_type.value}] {self.message}"
        if self.status_code:
            error_info += f" (HTTP {self.status_code})"
        return error_info


class NetworkError(APIException):
    """네트워크 연결 오류"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(
            message,
            APIErrorType.NETWORK_ERROR,
            original_error=original_error
        )


class TimeoutError(APIException):
    """요청 타임아웃"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(
            message,
            APIErrorType.TIMEOUT_ERROR,
            original_error=original_error
        )


class HTTPError(APIException):
    """HTTP 상태 코드 오류"""
    def __init__(self, message: str, status_code: int, response_text: str = None):
        super().__init__(
            message,
            APIErrorType.HTTP_ERROR,
            status_code=status_code,
            response_text=response_text
        )


class APIResponseError(APIException):
    """API 응답 내 에러 코드"""
    def __init__(self, error_code: str, error_message: str):
        super().__init__(
            f"API 에러 코드 {error_code}: {error_message}",
            APIErrorType.API_ERROR
        )
        self.error_code = error_code


class ParseError(APIException):
    """응답 파싱 오류"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(
            message,
            APIErrorType.PARSE_ERROR,
            original_error=original_error
        )


class RateLimitError(APIException):
    """API 호출 한도 초과"""
    def __init__(self, message: str):
        super().__init__(message, APIErrorType.RATE_LIMIT_ERROR)


class AuthenticationError(APIException):
    """인증 오류"""
    def __init__(self, message: str):
        super().__init__(message, APIErrorType.AUTH_ERROR)


class ValidationError(APIException):
    """입력값 검증 오류"""
    def __init__(self, message: str):
        super().__init__(message, APIErrorType.VALIDATION_ERROR)


# ============================================================
# 에러 핸들러
# ============================================================

class APIErrorHandler:
    """API 에러 처리 및 재시도 로직"""

    # 재시도 가능한 HTTP 상태 코드
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    # 재시도 가능한 에러 타입
    RETRYABLE_ERROR_TYPES = {
        APIErrorType.NETWORK_ERROR,
        APIErrorType.TIMEOUT_ERROR,
        APIErrorType.RATE_LIMIT_ERROR
    }

    @staticmethod
    def should_retry(error: Exception, attempt: int, max_retries: int) -> bool:
        """에러가 재시도 가능한지 판단"""
        if attempt >= max_retries:
            return False

        if isinstance(error, APIException):
            # HTTP 에러 재시도 판단
            if error.error_type == APIErrorType.HTTP_ERROR:
                return error.status_code in APIErrorHandler.RETRYABLE_STATUS_CODES

            # 에러 타입별 재시도 판단
            return error.error_type in APIErrorHandler.RETRYABLE_ERROR_TYPES

        # requests 라이브러리 예외 처리
        if isinstance(error, (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError
        )):
            return True

        return False

    @staticmethod
    def get_backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
        """지수 백오프 지연 시간 계산"""
        # 지수 백오프 + 지터(jitter)
        import random
        delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.1)  # 10% 지터
        return min(delay + jitter, 60.0)  # 최대 60초

    @staticmethod
    def handle_requests_error(error: Exception) -> APIException:
        """requests 라이브러리 에러를 커스텀 예외로 변환"""
        if isinstance(error, requests.exceptions.Timeout):
            return TimeoutError(
                "요청이 시간 초과되었습니다",
                original_error=error
            )

        elif isinstance(error, requests.exceptions.ConnectionError):
            return NetworkError(
                "서버에 연결할 수 없습니다",
                original_error=error
            )

        elif isinstance(error, requests.exceptions.HTTPError):
            response = error.response
            return HTTPError(
                f"HTTP 오류가 발생했습니다",
                status_code=response.status_code if response else 0,
                response_text=response.text if response else None
            )

        elif isinstance(error, requests.exceptions.RequestException):
            return NetworkError(
                f"요청 중 오류 발생: {str(error)}",
                original_error=error
            )

        else:
            return APIException(
                str(error),
                APIErrorType.UNKNOWN_ERROR,
                original_error=error
            )

    @staticmethod
    def handle_http_response(response: requests.Response) -> None:
        """HTTP 응답 상태 코드 검증"""
        if response.status_code == 401:
            raise AuthenticationError("API 인증에 실패했습니다. API 키를 확인해주세요")

        elif response.status_code == 403:
            raise AuthenticationError("API 접근 권한이 없습니다")

        elif response.status_code == 429:
            raise RateLimitError("API 호출 한도를 초과했습니다. 잠시 후 다시 시도해주세요")

        elif response.status_code >= 500:
            raise HTTPError(
                "서버 오류가 발생했습니다",
                status_code=response.status_code,
                response_text=response.text
            )

        elif response.status_code >= 400:
            raise HTTPError(
                f"클라이언트 요청 오류",
                status_code=response.status_code,
                response_text=response.text
            )


# ============================================================
# 데코레이터: 자동 재시도
# ============================================================

def retry_on_error(
    max_retries: int = 3,
    base_delay: float = 1.0,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    on_final_failure: Optional[Callable[[Exception], None]] = None
):
    """
    API 호출 함수에 자동 재시도 기능을 추가하는 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 기본 대기 시간 (초)
        on_retry: 재시도 시 실행할 콜백 함수
        on_final_failure: 최종 실패 시 실행할 콜백 함수

    Example:
        @retry_on_error(max_retries=3, base_delay=2.0)
        def fetch_data():
            # API 호출 로직
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_error = None

            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    # 재시도 가능 여부 확인
                    if not APIErrorHandler.should_retry(e, attempt, max_retries):
                        if on_final_failure:
                            on_final_failure(e)
                        raise

                    attempt += 1

                    if attempt <= max_retries:
                        delay = APIErrorHandler.get_backoff_delay(attempt - 1, base_delay)
                        log(f"⏳ 재시도 {attempt}/{max_retries} - {delay:.1f}초 후 재시도...")

                        if on_retry:
                            on_retry(e, attempt)

                        time.sleep(delay)

            # 최종 실패
            if on_final_failure:
                on_final_failure(last_error)

            raise last_error

        return wrapper
    return decorator


# ============================================================
# 컨텍스트 매니저: 에러 로깅
# ============================================================

class error_context:
    """
    에러 발생 시 자동으로 로깅하는 컨텍스트 매니저

    Example:
        with error_context("데이터 수집"):
            fetch_data()
    """
    def __init__(self, operation_name: str):
        self.operation_name = operation_name

    def __enter__(self):
        log(f"🚀 {self.operation_name} 시작")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            log(f"✅ {self.operation_name} 완료")
            return True

        if isinstance(exc_val, APIException):
            log(f"❌ {self.operation_name} 실패: {exc_val}")
        else:
            log(f"❌ {self.operation_name} 실패: {exc_type.__name__} - {exc_val}")

        # 예외를 다시 발생시킴
        return False


# ============================================================
# 유틸리티 함수
# ============================================================

def safe_api_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    default_value: Any = None,
    **kwargs
) -> Any:
    """
    안전하게 API를 호출하고, 실패 시 기본값 반환

    Args:
        func: 호출할 함수
        max_retries: 최대 재시도 횟수
        default_value: 실패 시 반환할 기본값
        *args, **kwargs: 함수에 전달할 인자

    Returns:
        함수 실행 결과 또는 기본값
    """
    @retry_on_error(max_retries=max_retries)
    def wrapped():
        return func(*args, **kwargs)

    try:
        return wrapped()
    except Exception as e:
        log(f"⚠️ API 호출 실패, 기본값 반환: {e}")
        return default_value


def validate_api_response(response: dict, required_fields: list) -> None:
    """
    API 응답에 필수 필드가 포함되어 있는지 검증

    Args:
        response: API 응답 딕셔너리
        required_fields: 필수 필드 리스트

    Raises:
        ValidationError: 필수 필드가 누락된 경우
    """
    missing_fields = [field for field in required_fields if field not in response]

    if missing_fields:
        raise ValidationError(
            f"API 응답에 필수 필드가 누락되었습니다: {', '.join(missing_fields)}"
        )

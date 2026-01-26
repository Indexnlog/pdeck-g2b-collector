"""
API 에러 핸들링 사용 예제
"""

import requests
import xml.etree.ElementTree as ET
from utils.api_error_handler import (
    retry_on_error,
    error_context,
    safe_api_call,
    APIErrorHandler,
    NetworkError,
    ParseError,
    APIResponseError,
    ValidationError,
    validate_api_response
)
from utils.logger import log


# ============================================================
# 예제 1: 데코레이터를 사용한 자동 재시도
# ============================================================

@retry_on_error(
    max_retries=3,
    base_delay=2.0,
    on_retry=lambda e, attempt: log(f"재시도 #{attempt}: {e}"),
    on_final_failure=lambda e: log(f"최종 실패: {e}")
)
def fetch_data_with_retry(url: str, params: dict):
    """자동 재시도가 적용된 데이터 fetch"""
    try:
        response = requests.get(url, params=params, timeout=30)

        # HTTP 상태 코드 검증
        APIErrorHandler.handle_http_response(response)

        return response

    except requests.exceptions.RequestException as e:
        # requests 에러를 커스텀 예외로 변환
        raise APIErrorHandler.handle_requests_error(e)


# ============================================================
# 예제 2: 컨텍스트 매니저를 사용한 에러 로깅
# ============================================================

def collect_g2b_data_with_context(api_key: str, year: int, month: int):
    """컨텍스트 매니저로 에러를 자동 로깅"""

    with error_context(f"G2B 데이터 수집 ({year}-{month:02d})"):
        # 입력값 검증
        if not api_key:
            raise ValidationError("API 키가 제공되지 않았습니다")

        if year < 2000 or year > 2030:
            raise ValidationError(f"유효하지 않은 연도: {year}")

        # API 호출
        url = "http://apis.data.go.kr/1230000/ao/CntrctInfoService/getCntrctInfoListThng"
        params = {
            "serviceKey": api_key,
            "numOfRows": 999,
            "pageNo": 1,
            "inqryDiv": "1",
            "inqryBgnDt": f"{year}{month:02d}010000",
            "inqryEndDt": f"{year}{month:02d}282359"
        }

        response = fetch_data_with_retry(url, params)

        # XML 파싱
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise ParseError(f"XML 파싱 실패: {e}", original_error=e)

        # API 에러 코드 확인
        result_code = root.find('.//resultCode')
        if result_code is not None and result_code.text != "00":
            result_msg = root.find('.//resultMsg')
            error_msg = result_msg.text if result_msg is not None else "Unknown error"
            raise APIResponseError(result_code.text, error_msg)

        # 데이터 추출
        items = root.findall('.//item')
        log(f"✅ {len(items)}건의 데이터 수집 완료")

        return items


# ============================================================
# 예제 3: safe_api_call을 사용한 안전한 호출
# ============================================================

def get_user_data_safely(user_id: int):
    """실패 시 기본값을 반환하는 안전한 API 호출"""

    def fetch_user():
        response = requests.get(
            f"https://api.example.com/users/{user_id}",
            timeout=10
        )
        APIErrorHandler.handle_http_response(response)
        return response.json()

    # 최대 3회 재시도, 실패 시 빈 딕셔너리 반환
    return safe_api_call(
        fetch_user,
        max_retries=3,
        default_value={}
    )


# ============================================================
# 예제 4: 응답 검증과 함께 사용
# ============================================================

@retry_on_error(max_retries=3)
def fetch_and_validate_data(api_key: str):
    """API 호출 후 응답 검증"""

    try:
        response = requests.get(
            "https://api.example.com/data",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )

        # HTTP 상태 검증
        APIErrorHandler.handle_http_response(response)

        # JSON 파싱
        data = response.json()

        # 필수 필드 검증
        validate_api_response(data, required_fields=["id", "name", "status"])

        log(f"✅ 데이터 검증 완료: {data['id']}")
        return data

    except requests.exceptions.RequestException as e:
        raise APIErrorHandler.handle_requests_error(e)

    except ValueError as e:
        raise ParseError(f"JSON 파싱 실패: {e}", original_error=e)


# ============================================================
# 예제 5: 수동으로 에러 처리 및 재시도
# ============================================================

def manual_retry_example(url: str, max_retries: int = 3):
    """수동으로 재시도 로직 구현"""

    attempt = 0
    last_error = None

    while attempt <= max_retries:
        try:
            log(f"📡 API 호출 시도 {attempt + 1}/{max_retries + 1}")

            response = requests.get(url, timeout=30)
            APIErrorHandler.handle_http_response(response)

            log("✅ 호출 성공")
            return response

        except Exception as e:
            last_error = e
            log(f"❌ 시도 실패: {e}")

            # 재시도 가능 여부 확인
            if not APIErrorHandler.should_retry(e, attempt, max_retries):
                log("⚠️ 재시도 불가능한 에러")
                raise

            attempt += 1

            if attempt <= max_retries:
                # 지수 백오프 계산
                delay = APIErrorHandler.get_backoff_delay(attempt - 1, base_delay=1.0)
                log(f"⏳ {delay:.1f}초 후 재시도...")
                import time
                time.sleep(delay)

    # 모든 재시도 실패
    log(f"❌ 모든 재시도 실패")
    raise last_error


# ============================================================
# 예제 6: 여러 API를 순차적으로 호출
# ============================================================

def fetch_multiple_apis_example():
    """여러 API를 순차적으로 호출하며 에러 처리"""

    results = []

    apis = [
        ("물품", "getCntrctInfoListThng"),
        ("공사", "getCntrctInfoListCnstwk"),
        ("용역", "getCntrctInfoListServc"),
        ("외자", "getCntrctInfoListFrgcpt")
    ]

    for job_type, operation in apis:
        with error_context(f"{job_type} 데이터 수집"):
            try:
                # API 호출
                result = safe_api_call(
                    fetch_data_with_retry,
                    url=f"http://apis.data.go.kr/1230000/ao/CntrctInfoService/{operation}",
                    params={
                        "serviceKey": "YOUR_API_KEY",
                        "numOfRows": 10,
                        "pageNo": 1
                    },
                    max_retries=2,
                    default_value=None
                )

                if result:
                    results.append((job_type, result))
                    log(f"✅ {job_type} 수집 성공")
                else:
                    log(f"⚠️ {job_type} 수집 실패 (기본값 사용)")

            except Exception as e:
                log(f"❌ {job_type} 수집 중 복구 불가능한 에러: {e}")
                # 하나의 API 실패가 전체를 중단시키지 않도록 continue
                continue

    return results


# ============================================================
# 예제 7: 배치 처리 시 에러 핸들링
# ============================================================

def batch_process_with_error_handling(items: list):
    """여러 아이템을 배치 처리하며 에러 처리"""

    successful = []
    failed = []

    for idx, item in enumerate(items, 1):
        try:
            log(f"처리 중: {idx}/{len(items)}")

            # 각 아이템 처리 (자동 재시도 적용)
            @retry_on_error(max_retries=2, base_delay=0.5)
            def process_item():
                # 실제 처리 로직
                if not item.get("id"):
                    raise ValidationError("아이템에 ID가 없습니다")

                # API 호출 등의 작업
                return {"id": item["id"], "status": "processed"}

            result = process_item()
            successful.append(result)

        except Exception as e:
            log(f"⚠️ 아이템 {item.get('id', 'unknown')} 처리 실패: {e}")
            failed.append({
                "item": item,
                "error": str(e)
            })
            # 다음 아이템 처리 계속
            continue

    log(f"배치 처리 완료: 성공 {len(successful)}개, 실패 {len(failed)}개")

    return {
        "successful": successful,
        "failed": failed
    }


# ============================================================
# 테스트 실행
# ============================================================

if __name__ == "__main__":
    # 예제 실행
    print("=" * 60)
    print("API 에러 핸들링 예제")
    print("=" * 60)

    # 예제 3: 안전한 호출
    print("\n[예제 3] 안전한 API 호출")
    user_data = get_user_data_safely(123)
    print(f"결과: {user_data}")

    # 예제 7: 배치 처리
    print("\n[예제 7] 배치 처리")
    test_items = [
        {"id": "001", "name": "Item 1"},
        {"id": "002", "name": "Item 2"},
        {"name": "Item 3"},  # ID 없음 - 에러 발생
        {"id": "004", "name": "Item 4"}
    ]
    batch_result = batch_process_with_error_handling(test_items)
    print(f"성공: {len(batch_result['successful'])}개")
    print(f"실패: {len(batch_result['failed'])}개")

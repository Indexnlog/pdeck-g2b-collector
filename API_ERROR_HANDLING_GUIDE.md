# API 에러 핸들링 가이드

Python API 에러 핸들링 시스템 사용 방법

## 📋 목차

1. [개요](#개요)
2. [주요 기능](#주요-기능)
3. [설치 및 설정](#설치-및-설정)
4. [기본 사용법](#기본-사용법)
5. [고급 사용법](#고급-사용법)
6. [에러 타입](#에러-타입)
7. [Best Practices](#best-practices)

---

## 개요

`utils/api_error_handler.py`는 API 호출 시 발생하는 다양한 에러를 체계적으로 처리하기 위한 모듈입니다.

### 주요 특징

- ✅ **자동 재시도**: 네트워크 오류, 타임아웃 등 재시도 가능한 에러 자동 처리
- ✅ **지수 백오프**: 재시도 시 지연 시간 자동 증가 (지터 포함)
- ✅ **커스텀 예외**: 에러 타입별 명확한 예외 클래스
- ✅ **로깅 자동화**: 컨텍스트 매니저를 통한 자동 에러 로깅
- ✅ **응답 검증**: HTTP 상태 코드 및 API 응답 자동 검증

---

## 주요 기능

### 1. 커스텀 예외 클래스

| 예외 클래스 | 설명 | 재시도 가능 |
|------------|------|-----------|
| `NetworkError` | 네트워크 연결 오류 | ✅ |
| `TimeoutError` | 요청 타임아웃 | ✅ |
| `HTTPError` | HTTP 상태 코드 오류 | 조건부 |
| `APIResponseError` | API 응답 에러 코드 | ❌ |
| `ParseError` | 응답 파싱 오류 | ❌ |
| `RateLimitError` | API 호출 한도 초과 | ✅ |
| `AuthenticationError` | 인증 오류 | ❌ |
| `ValidationError` | 입력값 검증 오류 | ❌ |

### 2. 데코레이터: `@retry_on_error`

함수에 자동 재시도 기능을 추가합니다.

```python
from utils.api_error_handler import retry_on_error

@retry_on_error(max_retries=3, base_delay=2.0)
def fetch_data():
    # API 호출 로직
    response = requests.get("https://api.example.com/data")
    return response.json()
```

### 3. 컨텍스트 매니저: `error_context`

에러 발생 시 자동으로 로깅합니다.

```python
from utils.api_error_handler import error_context

with error_context("데이터 수집"):
    data = fetch_data()
    process_data(data)
```

### 4. 안전한 호출: `safe_api_call`

실패 시 기본값을 반환합니다.

```python
from utils.api_error_handler import safe_api_call

result = safe_api_call(
    fetch_data,
    max_retries=3,
    default_value=[]
)
```

---

## 설치 및 설정

### 1. 파일 구조

```
pdeck-g2b-collector/
├── utils/
│   ├── api_error_handler.py       # 에러 핸들링 모듈
│   ├── api_error_examples.py      # 사용 예제
│   ├── g2b_client_improved.py     # 개선된 G2B 클라이언트
│   └── logger.py                  # 로거
└── API_ERROR_HANDLING_GUIDE.md    # 이 가이드
```

### 2. 의존성

이미 설치된 패키지만 사용합니다:
- `requests`
- `xml.etree.ElementTree` (표준 라이브러리)

---

## 기본 사용법

### 예제 1: 데코레이터를 사용한 자동 재시도

```python
from utils.api_error_handler import retry_on_error, APIErrorHandler
import requests

@retry_on_error(max_retries=3, base_delay=1.0)
def fetch_user_data(user_id):
    response = requests.get(
        f"https://api.example.com/users/{user_id}",
        timeout=30
    )

    # HTTP 상태 검증
    APIErrorHandler.handle_http_response(response)

    return response.json()

# 사용
try:
    data = fetch_user_data(123)
    print(data)
except Exception as e:
    print(f"에러 발생: {e}")
```

### 예제 2: 컨텍스트 매니저로 에러 로깅

```python
from utils.api_error_handler import error_context, ValidationError

def process_data(year, month):
    with error_context(f"데이터 처리 ({year}-{month})"):
        # 입력값 검증
        if year < 2000:
            raise ValidationError(f"유효하지 않은 연도: {year}")

        # 실제 처리 로직
        result = fetch_and_process(year, month)
        return result

# 사용
result = process_data(2024, 1)
```

### 예제 3: G2B API 클라이언트 사용

```python
import os
from utils.g2b_client_improved import G2BClientImproved

# API 키 로드
api_key = os.getenv("API_KEY")

# 클라이언트 생성
client = G2BClientImproved(api_key, max_retries=3)

# 연결 테스트
if client.test_connection():
    print("✅ API 연결 성공")

# 데이터 수집
try:
    xml_data, count, calls = client.fetch_data(
        job_type="물품",
        year=2024,
        month=1
    )

    print(f"수집 건수: {count:,}건")
    print(f"API 호출: {calls}회")

except ValidationError as e:
    print(f"입력값 오류: {e}")
except RateLimitError as e:
    print(f"API 한도 초과: {e}")
except Exception as e:
    print(f"오류 발생: {e}")
```

---

## 고급 사용법

### 1. 커스텀 재시도 콜백

```python
from utils.api_error_handler import retry_on_error

def on_retry_callback(error, attempt):
    print(f"⚠️ 재시도 #{attempt}: {error}")
    # Slack 알림, 로그 전송 등

def on_failure_callback(error):
    print(f"❌ 최종 실패: {error}")
    # 관리자에게 알림 전송

@retry_on_error(
    max_retries=5,
    base_delay=2.0,
    on_retry=on_retry_callback,
    on_final_failure=on_failure_callback
)
def critical_api_call():
    # 중요한 API 호출
    pass
```

### 2. 배치 처리 시 에러 핸들링

```python
from utils.api_error_handler import retry_on_error, error_context

def batch_process(items):
    successful = []
    failed = []

    for item in items:
        try:
            with error_context(f"아이템 {item['id']} 처리"):
                result = process_single_item(item)
                successful.append(result)

        except Exception as e:
            failed.append({
                "item": item,
                "error": str(e)
            })
            continue  # 다음 아이템 처리 계속

    return {
        "successful": successful,
        "failed": failed
    }

@retry_on_error(max_retries=2)
def process_single_item(item):
    # 개별 아이템 처리
    return {"id": item["id"], "status": "processed"}
```

### 3. 여러 API 순차 호출

```python
from utils.api_error_handler import safe_api_call, error_context

def fetch_multiple_sources():
    results = {}

    sources = [
        ("물품", "endpoint1"),
        ("공사", "endpoint2"),
        ("용역", "endpoint3")
    ]

    for name, endpoint in sources:
        with error_context(f"{name} 데이터 수집"):
            # 실패 시 None 반환, 다른 소스는 계속 처리
            data = safe_api_call(
                fetch_from_endpoint,
                endpoint,
                max_retries=2,
                default_value=None
            )

            if data:
                results[name] = data
            else:
                print(f"⚠️ {name} 수집 실패 (건너뜀)")

    return results
```

### 4. 수동 재시도 제어

```python
from utils.api_error_handler import APIErrorHandler
import time

def manual_retry_logic(url, max_retries=3):
    attempt = 0

    while attempt <= max_retries:
        try:
            response = requests.get(url, timeout=30)
            APIErrorHandler.handle_http_response(response)
            return response

        except Exception as e:
            # 재시도 가능 여부 확인
            if not APIErrorHandler.should_retry(e, attempt, max_retries):
                raise

            attempt += 1

            # 지수 백오프 계산
            delay = APIErrorHandler.get_backoff_delay(attempt - 1)
            print(f"⏳ {delay:.1f}초 후 재시도...")
            time.sleep(delay)

    raise Exception("모든 재시도 실패")
```

---

## 에러 타입

### 재시도 가능한 에러

다음 에러들은 자동으로 재시도됩니다:

| 에러 타입 | HTTP 상태 코드 | 설명 |
|----------|--------------|------|
| NetworkError | - | 네트워크 연결 실패 |
| TimeoutError | 408 | 요청 타임아웃 |
| RateLimitError | 429 | API 호출 한도 초과 |
| HTTPError | 500, 502, 503, 504 | 서버 오류 |

### 재시도 불가능한 에러

다음 에러들은 재시도하지 않고 즉시 중단됩니다:

| 에러 타입 | HTTP 상태 코드 | 설명 |
|----------|--------------|------|
| AuthenticationError | 401, 403 | 인증/권한 오류 |
| ValidationError | 400 | 입력값 검증 실패 |
| ParseError | - | 응답 파싱 실패 |
| APIResponseError | 200 | API 응답 내 에러 코드 |

---

## Best Practices

### ✅ DO

1. **입력값을 먼저 검증하세요**
   ```python
   if not api_key:
       raise ValidationError("API 키가 없습니다")
   ```

2. **적절한 재시도 횟수 설정**
   - 일반 API: 3회
   - 중요한 API: 5회
   - 빠른 응답 필요: 1-2회

3. **타임아웃 설정**
   ```python
   response = requests.get(url, timeout=30)
   ```

4. **에러별로 다르게 처리**
   ```python
   try:
       data = fetch_data()
   except ValidationError:
       # 사용자에게 입력 요청
       pass
   except RateLimitError:
       # 나중에 재시도
       pass
   except NetworkError:
       # 관리자에게 알림
       pass
   ```

5. **로깅 활용**
   ```python
   with error_context("작업명"):
       # 자동으로 시작/완료/실패 로깅
       pass
   ```

### ❌ DON'T

1. **모든 에러를 무시하지 마세요**
   ```python
   # 나쁨
   try:
       fetch_data()
   except:
       pass  # 에러 무시
   ```

2. **무한 재시도 방지**
   ```python
   # 나쁨
   while True:
       try:
           fetch_data()
           break
       except:
           continue  # 무한 루프
   ```

3. **너무 많은 재시도 횟수**
   ```python
   # 나쁨
   @retry_on_error(max_retries=100)  # 너무 많음
   def fetch_data():
       pass
   ```

4. **재시도 불가능한 에러를 재시도하지 마세요**
   ```python
   # 나쁨 - ValidationError는 재시도해도 같은 결과
   @retry_on_error(max_retries=5)
   def validate_and_fetch(year):
       if year < 2000:
           raise ValidationError("Invalid year")
   ```

---

## 에러 플로우 차트

```
API 호출
   ↓
입력값 검증 (ValidationError?)
   ↓
API 요청
   ↓
네트워크 오류? → NetworkError → 재시도
   ↓
타임아웃? → TimeoutError → 재시도
   ↓
HTTP 4xx/5xx? → HTTPError → 조건부 재시도
   ↓
응답 파싱
   ↓
파싱 오류? → ParseError → 실패
   ↓
API 에러 코드 확인
   ↓
에러 코드 != 00? → APIResponseError → 실패
   ↓
성공 ✅
```

---

## 추가 리소스

- [api_error_handler.py](utils/api_error_handler.py) - 에러 핸들러 모듈
- [api_error_examples.py](utils/api_error_examples.py) - 다양한 사용 예제
- [g2b_client_improved.py](utils/g2b_client_improved.py) - 실제 적용 예제

---

## 문의

문제가 있거나 개선 제안이 있으면 이슈를 등록해주세요.

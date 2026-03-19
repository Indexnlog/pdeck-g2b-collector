# ⚠️ 현재 기준 아님

이 문서는 GitHub Actions와 Google Drive 중심 운영 당시의 트러블슈팅 문서다.

현재 운영 기준은 아래 문서를 먼저 본다.
- [OPERATIONS.md](OPERATIONS.md)
- [OBSIDIAN_G2B_OPERATIONS.md](OBSIDIAN_G2B_OPERATIONS.md)

# 🔧 문제 해결 가이드

GitHub Actions에서 발생하는 오류를 해결하는 방법

## 📋 목차

1. [일반적인 오류](#일반적인-오류)
2. [API 오류](#api-오류)
3. [네트워크 오류](#네트워크-오류)
4. [Google Drive 오류](#google-drive-오류)
5. [디버깅 방법](#디버깅-방법)

---

## 일반적인 오류

### ❌ ImportError: No module named 'utils'

**증상:**
```
ImportError: No module named 'utils.drive'
```

**원인:**
- PYTHONPATH가 올바르게 설정되지 않음
- 프로젝트 구조가 변경됨

**해결방법:**

1. GitHub Actions 워크플로우 확인:
   ```yaml
   env:
     PYTHONPATH: ${{ github.workspace }}
   ```

2. 로컬에서 테스트:
   ```bash
   export PYTHONPATH=$(pwd)
   python collectors/g2b/collect_all.py
   ```

3. `utils/__init__.py` 파일 확인:
   ```bash
   ls utils/__init__.py
   ```

---

### ❌ API_KEY 환경변수 없음

**증상:**
```
ValidationError: API_KEY가 설정되지 않았습니다
```

**원인:**
- GitHub Secrets에 API_KEY가 설정되지 않음
- Secrets 이름 오타

**해결방법:**

1. GitHub Repository → Settings → Secrets and variables → Actions
2. `API_KEY` Secret 확인
3. 값이 없으면 추가:
   - Name: `API_KEY`
   - Secret: [나라장터 API 키]

---

### ❌ service_account.json 생성 실패

**증상:**
```
❌ service_account.json 생성 실패
```

**원인:**
- GOOGLE_CREDENTIALS가 base64로 인코딩되지 않음
- Secret 값이 잘못됨

**해결방법:**

1. 로컬에서 올바른 base64 인코딩 확인:
   ```bash
   # Linux/Mac
   base64 -i service_account.json | tr -d '\n' > encoded.txt

   # Windows PowerShell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("service_account.json")) > encoded.txt
   ```

2. encoded.txt 내용을 GitHub Secrets에 저장:
   - Name: `GOOGLE_CREDENTIALS`
   - Secret: [encoded.txt의 내용]

---

## API 오류

### ❌ G2B API 연결 실패

**증상:**
```
❌ G2B API 연결 실패: 401
❌ G2B API 연결 실패: 403
```

**원인:**
- API 키가 만료됨
- API 키가 잘못됨
- API 사용 권한 없음

**해결방법:**

1. 나라장터 Open API 포털 확인:
   - https://www.g2b.go.kr/index.jsp
   - 로그인 → 마이페이지 → API 키 관리

2. API 키 재발급:
   - 기존 키 삭제
   - 새 키 발급
   - GitHub Secrets 업데이트

3. 수동 테스트:
   ```bash
   curl "http://apis.data.go.kr/1230000/ao/CntrctInfoService/getCntrctInfoListThng?serviceKey=YOUR_KEY&numOfRows=1&pageNo=1&inqryDiv=1&inqryBgnDt=202401010000&inqryEndDt=202401012359"
   ```

---

### ❌ G2B API 429 Too Many Requests (일일 한도 초과)

**증상:**
```
❌ G2B API 연결 실패: Max retries exceeded with url: ...
   (Caused by ResponseError('too many 429 error responses'))
```

**원인:**
- G2B API 일일 호출 한도 초과
- 하루 3회 실행 × 1000회 = 3000회 호출 시도 → 한도 초과 (2026-02-25 발견)

**현재 동작 (2026-02-26 수정 후):**
- `daily_api_calls` 카운터를 날짜가 바뀔 때만 리셋 (기존: 매 실행마다 리셋)
- 당일 이미 한도(1000회) 소진 시 Slack 알림 후 **정상 종료** (실패 처리 아님)
- Connection Tests에서 G2B API 429 발생 시 경고만 출력하고 수집 계속 진행

**progress.json에서 오늘 사용량 확인:**
- Google Drive에서 파일 열기
- `daily_api_calls`: 오늘 누적 호출 횟수
- `last_run_date`: 마지막 실행 날짜 (이 날짜가 오늘이면 카운터 유지)

**수동으로 카운터 리셋이 필요한 경우 (주의!):**
- GitHub Actions → Run workflow
- `force_api_reset` 옵션 체크 후 실행

---

### ❌ XML 파싱 오류

**증상:**
```
ParseError: XML 파싱 실패
```

**원인:**
- API 응답이 XML이 아님
- 응답이 비어있음
- 인코딩 문제

**해결방법:**

1. 로그에서 실제 응답 확인:
   ```python
   log(f"API 응답: {response.text[:500]}")
   ```

2. API 응답 포맷 확인:
   - 브라우저에서 API URL 직접 접속
   - 응답이 올바른 XML인지 확인

3. 재시도 메커니즘이 작동하는지 확인:
   - 자동으로 3회까지 재시도됨

---

## 네트워크 오류

### ❌ 연결 타임아웃

**증상:**
```
NetworkError: 요청이 시간 초과되었습니다
TimeoutError: Connect timeout
```

**원인:**
- 네트워크 불안정
- 서버 응답 지연
- GitHub Actions 네트워크 제한

**해결방법:**

1. 자동 재시도 확인:
   - 기본적으로 3회 재시도
   - 지수 백오프 적용됨

2. 타임아웃 시간 조정:
   ```python
   # utils/g2b_client.py
   response = self.session.get(url, params=params, timeout=60)  # 30 → 60초
   ```

3. 워크플로우 재실행:
   - GitHub Actions → Re-run failed jobs

---

### ❌ Connection Reset

**증상:**
```
ConnectionResetError: [Errno 104] Connection reset by peer
```

**원인:**
- 서버가 연결을 강제로 끊음
- 네트워크 중간 장비 문제

**해결방법:**

1. 재시도 전략 확인:
   ```python
   # utils/g2b_client.py
   retry_strategy = Retry(
       total=3,
       status_forcelist=[429, 500, 502, 503, 504, 408],
       backoff_factor=2
   )
   ```

2. 요청 간격 늘리기:
   ```python
   time.sleep(0.5)  # 0.1 → 0.5초
   ```

---

## Google Drive 오류

### ❌ Drive 연결 실패

**증상:**
```
NetworkError: Google Drive 연결에 실패했습니다
```

**원인:**
- service_account.json 오류
- Drive API 권한 부족
- 파일 ID 잘못됨

**해결방법:**

1. Service Account 권한 확인:
   - Google Cloud Console
   - IAM & Admin → Service Accounts
   - 해당 계정에 Drive API 권한 부여

2. 파일 공유 설정:
   - Google Drive에서 progress.json 찾기
   - 우클릭 → 공유
   - Service Account 이메일 추가 (편집 권한)

3. 파일 ID 확인:
   ```python
   # collectors/g2b/collect_all.py
   PROGRESS_FILE_ID = "1_AKg04eOjQy3KBcjhp2xkkm1jzBcAjn-"
   ```
   - Drive URL: `https://drive.google.com/file/d/FILE_ID/view`

---

### ❌ 파일 업로드 실패

**증상:**
```
❌ 업로드 실패: HttpError 403
```

**원인:**
- Shared Drive 권한 부족
- 저장 용량 부족
- Drive ID 잘못됨

**해결방법:**

1. Shared Drive 권한 확인:
   - Shared Drive 설정
   - Service Account가 `콘텐츠 관리자` 이상 권한

2. 저장 용량 확인:
   - Shared Drive는 무제한 (조직 계정)
   - 일반 Drive는 15GB 제한

3. Drive ID 확인:
   ```python
   # collectors/g2b/collect_all.py
   SHARED_DRIVE_ID = "0AOi7Y50vK8xiUk9PVA"
   ```

---

## 디버깅 방법

### 1. 로그 확인

**GitHub Actions 로그:**
1. Repository → Actions
2. 실패한 워크플로우 클릭
3. 각 Step 클릭하여 로그 확인

**다운로드 가능한 로그:**
1. Artifacts 섹션
2. `execution-logs` 다운로드
3. `collection.log` 확인

---

### 2. 로컬에서 재현

```bash
# 1. 환경변수 설정
export API_KEY="your_api_key"
export GOOGLE_CREDENTIALS="base64_encoded_credentials"
export SLACK_TOKEN="your_slack_token"
export SLACK_CHANNEL_ID="your_channel_id"
export PYTHONPATH=$(pwd)

# 2. service_account.json 생성
echo "$GOOGLE_CREDENTIALS" | base64 -d > service_account.json

# 3. 수집기 실행
python collectors/g2b/collect_all.py

# 4. 헬스체크 실행
python monitor_health.py
```

---

### 3. 단계별 디버깅

**1단계: 환경 확인**
```python
import os
print("API_KEY:", "✅" if os.getenv("API_KEY") else "❌")
print("GOOGLE_CREDENTIALS:", "✅" if os.getenv("GOOGLE_CREDENTIALS") else "❌")
```

**2단계: Import 확인**
```python
import sys
print("sys.path:", sys.path)

try:
    from utils.drive import test_drive_connection
    print("✅ utils.drive import 성공")
except ImportError as e:
    print(f"❌ Import 실패: {e}")
```

**3단계: 연결 테스트**
```python
from utils.drive import test_drive_connection
from utils.g2b_client import G2BClient

# Drive 테스트
if test_drive_connection():
    print("✅ Drive 연결 성공")
else:
    print("❌ Drive 연결 실패")

# API 테스트
client = G2BClient(os.getenv("API_KEY"))
if client.test_connection():
    print("✅ API 연결 성공")
else:
    print("❌ API 연결 실패")
```

---

### 4. 헬스체크 실행

```bash
# 헬스체크로 모든 시스템 확인
python monitor_health.py

# Slack 알림 포함
export SEND_SLACK_NOTIFICATION=true
python monitor_health.py
```

---

### 5. 수동 워크플로우 실행

1. GitHub Repository → Actions
2. "G2B Auto Collector" 선택
3. "Run workflow" 클릭
4. 옵션 선택:
   - `skip_connection_test`: 연결 테스트 건너뛰기
   - `force_api_reset`: API 카운터 강제 리셋
5. "Run workflow" 버튼 클릭

---

## 📞 추가 지원

### 유용한 명령어

```bash
# 로그 실시간 확인 (로컬)
tail -f collection.log

# GitHub CLI로 워크플로우 확인
gh run list --limit 10
gh run view <run_id>
gh run watch <run_id>

# 환경변수 확인
printenv | grep -E "(API_KEY|GOOGLE|SLACK)"
```

### 참고 문서

- [API 에러 핸들링 가이드](API_ERROR_HANDLING_GUIDE.md)
- [G2B Open API 문서](https://www.g2b.go.kr/index.jsp)
- [Google Drive API](https://developers.google.com/drive/api/v3/about-sdk)
- [GitHub Actions 문서](https://docs.github.com/en/actions)

---

## 🆘 긴급 상황 대응

### 시스템이 완전히 멈췄을 때

1. **진행 상태 백업:**
   - Google Drive에서 `progress.json` 다운로드
   - 로컬에 백업 저장

2. **워크플로우 비활성화:**
   - `.github/workflows/g2b.yml` 수정
   - cron 스케줄 주석 처리

3. **수동 복구:**
   ```bash
   # 로컬에서 수동 실행
   python collectors/g2b/collect_all.py

   # progress.json 수동 업로드
   python collectors/g2b/upload_progress.py
   ```

4. **워크플로우 재활성화:**
   - cron 스케줄 주석 해제
   - 커밋 및 푸시

---

## ✅ 체크리스트

문제 발생 시 확인할 사항:

- [ ] GitHub Secrets 모두 설정됨
- [ ] service_account.json 올바르게 인코딩됨
- [ ] API 키가 유효함
- [ ] Google Drive 파일 공유 설정됨
- [ ] Shared Drive 권한 있음
- [ ] 워크플로우 파일 문법 오류 없음
- [ ] Python 패키지 모두 설치됨
- [ ] 네트워크 연결 정상
- [ ] 로그에서 실제 에러 메시지 확인

---

이 가이드로 해결되지 않는 문제가 있다면 GitHub Issues에 등록해주세요.

# G2B Collector Operations

이 문서는 `pdeck-g2b-collector`의 현재 운영 기준 문서다.

## 현재 운영 원칙

- 자동 실행 주체는 GitHub Actions가 아니라 로컬 PC다.
- GitHub Actions 워크플로우는 저장소에 남아 있지만 정기 `schedule` 트리거는 제거했다.
- GitHub Actions는 필요할 때만 수동 실행한다.
- 일일 수집은 로컬에서 `run_collector.bat` 또는 같은 명령으로 실행한다.

## 운영 변경 히스토리

### 1. 초기 단계: GitHub Actions 중심 운영

- 처음 자동화는 GitHub Actions를 중심으로 붙었다.
- 수집 결과와 진행 상태도 초기에 `progress.json`, Google Drive 동기화, GitHub workflow artifacts 같은 방식이 섞여 있었다.
- 이 시기에는 “클라우드에서 정기 실행”이 핵심 목표였고, 관련 커밋도 대부분 workflow 수정이었다.

### 2. 중간 단계: 저장소/진행 상태 구조 개편

- 이후 데이터 저장은 CockroachDB 중심으로 이동했다.
- 진행 상태도 점차 Google Drive 파일보다 DB `progress` 테이블과 로컬 `progress_backup.json` 쪽으로 옮겨 갔다.
- 다만 운영 주체는 한동안 그대로 GitHub Actions로 남아 있었고, 문서와 설정도 그 상태를 오래 끌고 갔다.

### 3. 전환 단계: 로컬 실행 도입

- `2026-03-12` 전후로 로컬 실행 전환 시도가 들어갔다.
- 이때 현재 저장소의 [run_collector.bat](run_collector.bat) 와 Windows 작업 스케줄러 기반 실행이 추가됐다.
- 하지만 기존 GitHub Actions 정기 실행이 완전히 제거되지는 않았고, 예전 로컬 작업도 같이 남아 있었다.
- 그래서 “로컬로 바꿨다”는 기억은 맞지만, 실제 설정은 혼합 상태였다.

### 4. 현재 결론: 로컬 단일 운영

- `2026-03-19` 기준으로 정리 완료.
- GitHub Actions 정기 `schedule` 제거.
- 로컬 작업 스케줄러는 `pdeck-g2b-collector` 하나만 남김.
- 기준 문서는 이 파일과 Obsidian 운영 노트로 통일.

## 왜 로컬 작업이 2개였나

- 실제로 작업 스케줄러에 두 작업이 있었다.
- `pdeck-g2b-collector`: 현재 저장소를 가리키는 작업. 매일 `09:00`.
- `G2B Auto Collector`: 예전 저장소 경로를 가리키는 오래된 작업. 매일 `10:00`.

원인:
- 로컬 전환을 하면서 새 작업은 만들었지만, 예전 작업을 같이 지우거나 비활성화하지 않았다.
- 즉 “교체”가 아니라 “추가”만 된 상태였다.
- 게다가 GitHub Actions 정기 실행도 별도로 살아 있어서, 한동안 자동화 주체가 세 갈래처럼 보였다.

현재 상태:
- 오래된 `G2B Auto Collector`는 제거됨.
- 현재 유효한 자동 실행은 `pdeck-g2b-collector` 하나다.

## 단일 진실 원천

- 운영 기준 문서는 이 파일을 기준으로 본다.
- Obsidian에는 이 파일과 같은 내용을 더 짧게 정리한 `OBSIDIAN_G2B_OPERATIONS.md`를 둔다.
- 예전 문서에서 이 파일과 충돌하는 내용이 있으면 이 파일이 우선이다.

## 현재 실행 방식

### 로컬 실행

실행 파일:
- [run_collector.bat](run_collector.bat)
- [scripts/register_task.ps1](scripts/register_task.ps1)
- [scripts/status.ps1](scripts/status.ps1)
- [scripts/reset_progress.ps1](scripts/reset_progress.ps1)

현재 배치 내용:
```bat
@echo off
cd /d "c:\Users\ekapr\Documents\GitHub\pdeck-g2b-collector"
set PYTHONUTF8=1
if not exist logs mkdir logs
".conda\python.exe" -u collectors\g2b\collect_all.py >> logs\collector.log 2>&1
```

직접 실행 명령:
```powershell
& .\.conda\python.exe -u collectors\g2b\collect_all.py
```

### GitHub Actions

현재 상태:
- [g2b.yml](.github/workflows/g2b.yml): 수동 실행만 가능
- [health-check.yml](.github/workflows/health-check.yml): 수동 실행만 가능
- 정기 `schedule`: 없음

의미:
- GitHub Actions 실패 알림이 다시 쌓이기 시작하면, 누군가 워크플로우 스케줄을 다시 추가했는지 먼저 확인한다.

## 오늘 기준 확인된 상태

- 진행 위치: `공사 2025년 6월`
- 누적 수집량: `618,516건`
- 진행 백업 파일: [progress_backup.json](progress_backup.json)
- 로컬 로그:
  - [collector.log](logs/collector.log)
  - [collector.lock](collector.lock) (실행 중일 때만 존재)

## 운영 도구

### 상태 확인

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1
```

### 작업 스케줄러 재등록

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
```

### progress 위치 수동 재설정

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_progress.ps1 -Job 공사 -Year 2025 -Month 6
```

## 운영 체크리스트

### 매일 확인할 것

- 로컬 PC가 켜져 있는지
- 네트워크가 연결돼 있는지
- `.env`가 유지되고 있는지
- 최근 로그에 API 호출과 insert가 계속 찍히는지

### 실행 전 확인

- `API_KEY` 설정됨
- `DATABASE_URL` 설정됨
- `SLACK_TOKEN` 설정됨
- `SLACK_CHANNEL_ID` 설정됨
- `.conda\python.exe` 실행 가능

### 실행 후 확인

- 로그에 `G2B 수집 시작` 출력
- DB 테이블 생성 또는 progress 로드 성공
- 현재 작업과 API 호출 로그 출력
- Slack 시작 알림 또는 종료 알림 전송

## 장애 대응

### 1. GitHub Actions가 또 자동 실행될 때

- [.github/workflows/g2b.yml](.github/workflows/g2b.yml) 에 `schedule:` 블록이 생겼는지 확인
- [.github/workflows/health-check.yml](.github/workflows/health-check.yml) 에 `schedule:` 블록이 생겼는지 확인
- 다시 제거 후 커밋/푸시

### 2. 로컬 배치가 안 돌 때

- [run_collector.bat](run_collector.bat) 가 `.conda\python.exe` 를 쓰는지 확인
- `python` 대신 `.conda\python.exe` 로 직접 실행해본다
- `.env` 누락 여부 확인

### 3. DB 연결 실패

- `DATABASE_URL` 확인
- 로컬 네트워크/방화벽 확인
- CockroachDB 연결 가능 여부 확인

### 4. Slack 알림 실패

- `SLACK_TOKEN`, `SLACK_CHANNEL_ID` 확인
- 네트워크 차단 여부 확인

## 변경 원칙

- 자동 실행 주체를 바꾸면 반드시 이 파일부터 수정한다.
- GitHub Actions 설정을 건드리면 README와 Obsidian 노트도 함께 수정한다.
- “로컬 실행 가능”과 “로컬 자동화 운영”은 다르다.
  현재 운영은 후자이며, GitHub Actions는 주 운영 경로가 아니다.

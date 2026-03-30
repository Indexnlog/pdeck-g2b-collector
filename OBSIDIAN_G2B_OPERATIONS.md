# G2B 운영 메모

## 수집 목표

- 계약월 **2026년 3월**까지 (네 종류). `collect_all`은 실행 월의 **전달**까지라 **2026년 4월** 이후 실행분부터 상한이 2026-03이 됨. 자세한 건 저장소 `OPERATIONS_WORKFLOW.md`.

## 현재 기준

- 자동화 주체는 GitHub Actions가 아니라 로컬 PC
- GitHub Actions는 수동 실행만 사용
- 정기 스케줄은 꺼둠 (G2B **일일 API 한도**·중복 실행 이슈는 `TROUBLESHOOTING.md` 429 절)
- 실행 파일은 `run_collector.bat`
- 실제 파이썬은 `.conda\python.exe`

## 헷갈리지 말 것

- “로컬 실행 스크립트가 있다”와 “자동 운영이 로컬이다”는 다름
- 지금은 둘 다 로컬 기준으로 맞춤
- GitHub Actions 실패가 다시 보이면 스케줄이 되살아났는지 먼저 확인

## 어떻게 바뀌었는지

1. 처음에는 GitHub Actions 중심으로 자동화를 돌림
2. 중간에 CockroachDB, DB progress 중심으로 구조가 바뀜
3. 이후 로컬 실행으로 옮기기 시작했지만, GitHub Actions와 예전 로컬 작업이 같이 남음
4. 지금은 GitHub Actions 정기 실행 제거, 로컬 작업 스케줄러 1개만 사용

## 왜 로컬 작업이 2개였나

- 옛 작업 `G2B Auto Collector`가 예전 저장소 경로를 계속 가리키고 있었음
- 새 작업 `pdeck-g2b-collector`를 추가했지만 옛 작업을 같이 안 지웠음
- 그래서 한동안 로컬 작업이 2개였음

현재는 `pdeck-g2b-collector`만 남음

## 작업 스케줄러 등록 (`register_task.ps1`)

- `2026-03-23` 기준: [register_task.ps1](scripts/register_task.ps1)가 작업 **작업 디렉터리 = 프로젝트 루트**, **실행 시간 제한 없음**을 넣도록 맞춰 둠(장시간 수집이 작업 기본 시간 한도로 끊기지 않게).
- PC 옮기거나 작업을 다시 만들 때는 `powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1` 한 번.

## 현재 시작 위치

- **단일 기준:** DB `progress` + 로컬 [progress_backup.json](progress_backup.json) (저장소에 커밋된 JSON은 참고용·쉽게 낡음)
- 매일 아침: `scripts\status.ps1` → Progress + 로그 tail + 스케줄 `NextRunTime`

## 로그 위치

- `logs/collector.log`
- `collector.lock` (실행 중일 때만 존재해야 함). PID가 이미 죽었는데 lock만 남은 경우, `collect_all.py`는 다음 실행 시 PID를 보고 **고아 락을 지우고** 진행한다.

## 실행 명령

```powershell
& .\.conda\python.exe -u collectors\g2b\collect_all.py
```

## 운영 도구

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reset_progress.ps1 -Job 공사 -Year 2025 -Month 6

# 누락 구간 감지
.conda\python.exe scripts\find_gaps.py

# 누락 구간 감지 + 첫 번째 갭으로 progress 리셋
.conda\python.exe scripts\find_gaps.py --backfill
```

## Slack이 매일 안 올 때

- **GitHub Actions 정기 실행은 없음** → 클라우드에서 매일 돌지 않음 → 그 경로로는 Slack이 안 감
- **Slack은 `collect_all.py`가 실제로 돌 때만** (시작·완료·한도 소진·에러 등)
- 메시지가 없으면: PC 꺼짐/절전, 작업 스케줄러 `pdeck-g2b-collector` 비활성·실패, `.env`의 `SLACK_TOKEN`·`SLACK_CHANNEL_ID` 누락, 배치가 시작 전에 죽음 → **`logs\collector.log`와 `status.ps1`로 먼저 확인**

## 체크 순서

1. `.env` 확인
2. `.conda\python.exe` 실행 확인
3. 작업 스케줄러 `pdeck-g2b-collector` 상태·LastRunTime (`status.ps1`)
4. 로그에 `G2B 수집 시작` 확인
5. progress 로드 확인
6. API 호출 로그 확인

## 2026-03-26 트러블슈팅 기록

### 증상
- 어제(3/25) Slack에 "G2B 수집 시작 현재 위치: 외자 2025년 6월 API: 0/1000" 메시지 하나만 오고 끝남
- API 호출을 거의 안 했는데 수집 완료 처리됨

### 근본 원인
1. `except Exception` 블록에 `break`가 없어서 에러 후에도 루프가 계속 돌았음
2. 에러 발생해도 progress가 다음 구간으로 전진 → 빠르게 모든 구간 스킵 → limit 도달 → "완료"
3. 결과적으로 API 1000회 안 채우고 progress만 끝까지 감

### 수정 내용
- `period_success` 플래그: 에러 시 progress 전진 방지
- `except Exception`에 `break` 추가: 에러 시 즉시 중단 + Slack 알림
- `find_collection_gaps()`: DB 실제 데이터 vs 기대 구간 비교로 누락 자동 감지
- `fill_gaps.py`: `fetch_data()` → `fetch_pages()` (MemoryError 방지)
- 수집 완료 시 자동 갭 감지 결과를 Slack 알림에 포함

### 재수집 결과
- `fill_gaps.py` 실행: 7개 구간 채움, 36,064건 insert
- 공사/용역 2023-06~07에서 MemoryError → fetch_pages 방식으로 수정 완료
- 공사/용역 2023-07에서 CockroachDB RU 월간 한도 도달 → DB 접속 불가

### 현재 상태 (3/26~3/31)
- **작업 스케줄러 `pdeck-g2b-collector`: Disabled** (DB 막혀서 에러만 나니까 중단)
- CockroachDB 월간 RU 리셋 대기 (4/1)
- 4/1 09:30 예약 태스크 설정됨 → `fill_gaps.py` 자동 실행 → 나머지 누락분 채움
- 4/1 이후 `Enable-ScheduledTask -TaskName 'pdeck-g2b-collector'`로 자동 수집 재개

## 장애 대응 요약 (2026-03-25 추가)

| 증상 | 원인 | 대응 |
|------|------|------|
| 시작 메시지만 오고 끝 | fetch_pages 에러 삼킴 | 코드 수정 완료 (raise로 변경) |
| API 안 채우고 완료 | 에러 시 progress 스킵 | 코드 수정 완료 (에러 시 break + progress 유지) |
| 과거 누락 구간 | 위 버그로 스킵된 구간 | `find_gaps.py --backfill` 후 재수집 |

상세: `OPERATIONS.md` 장애 대응 #7~#9 참조

## 문서 기준

- 저장소 기준 문서: `OPERATIONS.md`
- **운영 워크플로**(매일·종료 직후 체크): 저장소 `OPERATIONS_WORKFLOW.md` — Obsidian Second Brain에는 동명 요약 노트 `운영 워크플로.md`를 둠
- 이 노트는 Obsidian용 요약본
- 충돌 시 `OPERATIONS.md` 우선

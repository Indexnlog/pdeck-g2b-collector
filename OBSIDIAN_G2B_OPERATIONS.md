# G2B 운영 메모

## 현재 기준

- 자동화 주체는 GitHub Actions가 아니라 로컬 PC
- GitHub Actions는 수동 실행만 사용
- 정기 스케줄은 꺼둠
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

## 현재 시작 위치

- DB `progress` 테이블 기준 (실시간)
- 로컬 백업: `progress_backup.json`

## 로그 위치

- `logs/collector.log`
- `collector.lock` (실행 중일 때만 존재)

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

## 체크 순서

1. `.env` 확인
2. `.conda\python.exe` 실행 확인
3. 로그에 `G2B 수집 시작` 확인
4. progress 로드 확인
5. API 호출 로그 확인

## 장애 대응 요약 (2026-03-25 추가)

| 증상 | 원인 | 대응 |
|------|------|------|
| 시작 메시지만 오고 끝 | fetch_pages 에러 삼킴 | 코드 수정 완료 (raise로 변경) |
| API 안 채우고 완료 | 에러 시 progress 스킵 | 코드 수정 완료 (에러 시 break + progress 유지) |
| 과거 누락 구간 | 위 버그로 스킵된 구간 | `find_gaps.py --backfill` 후 재수집 |

상세: `OPERATIONS.md` 장애 대응 #5~#7 참조

## 문서 기준

- 저장소 기준 문서: `OPERATIONS.md`
- 이 노트는 Obsidian용 요약본
- 충돌 시 `OPERATIONS.md` 우선

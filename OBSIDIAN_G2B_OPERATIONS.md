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

- `progress_backup.json` 기준 (저장소에 커밋된 스냅샷과 동기화)
- 예: `용역 2025년 2월`, 누적 `1,169,696건`, 마지막 실행일 `2026-03-19`
- 매일 아침 확인: `scripts\status.ps1` → Progress + 로그 tail

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

## 문서 기준

- 저장소 기준 문서: `OPERATIONS.md`
- 이 노트는 Obsidian용 요약본
- 충돌 시 `OPERATIONS.md` 우선

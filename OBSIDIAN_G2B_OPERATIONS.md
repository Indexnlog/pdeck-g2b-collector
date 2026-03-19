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

## 현재 시작 위치

- `공사 2025년 6월`
- 누적 `618,516건`
- 기준 파일: `progress_backup.json`

## 로그 위치

- `logs/collector.log`
- `logs/collector-local.log`
- `logs/collector-local.err`

## 실행 명령

```powershell
& .\.conda\python.exe -u collectors\g2b\collect_all.py
```

## 체크 순서

1. `.env` 확인
2. `.conda\python.exe` 실행 확인
3. 로그에 `G2B 수집 시작` 확인
4. progress 로드 확인
5. API 호출 로그 확인

## 문서 기준

- 저장소 기준 문서: `OPERATIONS.md`
- 이 노트는 Obsidian용 요약본
- 충돌 시 `OPERATIONS.md` 우선

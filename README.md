# pdeck-g2b-collector

나라장터(G2B) 계약정보 수집기입니다.

현재 운영 기준은 GitHub Actions 자동 실행이 아니라 로컬 실행입니다.

운영 문서:
- [OPERATIONS.md](OPERATIONS.md) - GitHub 저장소 기준 운영 문서
- [OPERATIONS_WORKFLOW.md](OPERATIONS_WORKFLOW.md) - 매일·수집 완료 후 사람이 할 일 (체크리스트·다이어그램)
- [OBSIDIAN_G2B_OPERATIONS.md](OBSIDIAN_G2B_OPERATIONS.md) - Obsidian에 옮겨 적기 쉬운 요약 노트

현재 기준 요약:
- 자동 실행 주체: 로컬 PC
- GitHub Actions: 수동 실행만 가능, 정기 스케줄 없음
- 로컬 실행 엔트리: [run_collector.bat](run_collector.bat)
- 실제 Python 경로: `.conda\python.exe`
- 운영 로그: `logs/collector.log`
- 상태 확인: `powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1`

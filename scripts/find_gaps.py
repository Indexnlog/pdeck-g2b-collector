#!/usr/bin/env python3
"""
누락 구간 감지 스크립트.

DB에 수집된 구간과 있어야 할 전체 구간(2016-02 ~ 전달)을 비교해서
빠진 (job, year, month) 조합을 출력합니다.

사용법:
    .conda\python.exe scripts\find_gaps.py
    .conda\python.exe scripts\find_gaps.py --backfill   # 감지 후 즉시 재수집
"""
import os
import sys
import argparse

# 프로젝트 루트 설정
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

from utils.db import find_collection_gaps, load_progress, save_progress
from utils.logger import log


def main():
    parser = argparse.ArgumentParser(description="G2B 누락 구간 감지 및 재수집")
    parser.add_argument("--backfill", action="store_true",
                        help="누락 감지 후 즉시 재수집 (progress를 첫 번째 갭 위치로 리셋)")
    parser.add_argument("--json", action="store_true",
                        help="JSON 형식으로 출력")
    args = parser.parse_args()

    log("🔍 누락 구간 감지 시작...")
    gaps = find_collection_gaps()

    if not gaps:
        log("✅ 누락 구간 없음 — 모든 구간이 수집되어 있습니다.")
        return

    # 요약 출력
    log(f"\n⚠️ 총 {len(gaps)}개 누락 구간 발견:\n")

    if args.json:
        import json
        print(json.dumps(gaps, ensure_ascii=False, indent=2))
    else:
        # job별로 그룹핑해서 보기 좋게 출력
        current_job = None
        for gap in gaps:
            if gap["job"] != current_job:
                current_job = gap["job"]
                log(f"\n  [{current_job}]")
            log(f"    {gap['year']}-{gap['month']:02d}")

    if args.backfill:
        first_gap = gaps[0]
        log(f"\n🔄 progress를 첫 번째 누락 위치로 리셋:")
        log(f"   → {first_gap['job']} {first_gap['year']}년 {first_gap['month']}월")

        progress = load_progress()
        progress["current_job"] = first_gap["job"]
        progress["current_year"] = first_gap["year"]
        progress["current_month"] = first_gap["month"]
        progress["daily_api_calls"] = 0
        progress["last_run_date"] = ""
        save_progress(progress)
        log("✅ progress 리셋 완료. run_collector.bat 실행하면 누락분부터 수집합니다.")

    log(f"\n💡 수동 리셋: scripts\\reset_progress.ps1 -Job <job> -Year <year> -Month <month>")


if __name__ == "__main__":
    main()

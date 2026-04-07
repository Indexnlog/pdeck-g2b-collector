#!/usr/bin/env python3
"""
누락 구간 재수집 스크립트.
DB에서 데이터가 0건인 (종류, 연도, 월) 구간을 찾아 재수집한다.
"""
import os
import sys
import time
import traceback

# 프로젝트 루트 설정
current_file_path = os.path.abspath(__file__)
g2b_dir = os.path.dirname(current_file_path)
collectors_dir = os.path.dirname(g2b_dir)
project_root = os.path.dirname(collectors_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

from utils.db import find_collection_gaps, insert_contracts, mark_period_collected
from utils.g2b_client import G2BClient
from utils.logger import log
from utils.slack import send_slack_message

API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 1000


def fill_gaps():
    """누락 구간을 재수집."""
    log("🔍 누락 구간 탐색 시작...")
    gaps = find_collection_gaps()

    if not gaps:
        msg = "✅ 누락 구간 없음! 모든 (종류, 연도, 월) 구간에 데이터가 있습니다."
        log(msg)
        send_slack_message(msg)
        return True

    log(f"⚠️ 누락 구간 {len(gaps)}개 발견:")
    for g in gaps:
        log(f"   - {g['job']} {g['year']}년 {g['month']}월")

    # 재수집
    client = G2BClient(API_KEY)
    api_calls = 0
    total_inserted = 0
    filled = []
    errors = []

    send_slack_message(
        f"🔧 누락 구간 재수집 시작\n"
        f"대상: {len(gaps)}개 구간"
    )

    from collectors.g2b.collect_all import parse_xml_elements

    MAX_GAP_RETRIES = 2          # 구간별 최대 재시도 횟수
    CONSECUTIVE_FAIL_LIMIT = 3   # 연속 실패 시 대기 트리거
    CONSECUTIVE_FAIL_WAIT = 60   # 연속 실패 시 대기 시간(초)

    consecutive_network_errors = 0

    for gap in gaps:
        job, year, month = gap["job"], gap["year"], gap["month"]

        if api_calls >= MAX_API_CALLS:
            log(f"⛔ API 한도 도달 ({api_calls}/{MAX_API_CALLS}). 나머지는 다음 실행에서.")
            break

        success = False
        for attempt in range(1, MAX_GAP_RETRIES + 1):
            try:
                log(f"📡 재수집: {job} {year}년 {month}월" + (f" (재시도 {attempt}/{MAX_GAP_RETRIES})" if attempt > 1 else ""))
                month_inserted = 0

                for xml_items, page_calls in client.fetch_pages(job, year, month):
                    api_calls += page_calls
                    rows = parse_xml_elements(xml_items, year, month)
                    inserted = insert_contracts(rows)
                    month_inserted += inserted
                    del rows

                # 성공적으로 fetch 완료 → 수집 완료로 기록 (0건이어도)
                mark_period_collected(job, year, month)
                consecutive_network_errors = 0

                if month_inserted > 0:
                    filled.append(f"{job} {year}-{month:02d} ({month_inserted}건)")
                    total_inserted += month_inserted
                    log(f"✅ {job} {year}-{month:02d}: {month_inserted}건 insert")
                else:
                    log(f"ℹ️ {job} {year}-{month:02d}: 데이터 없음 또는 이미 수집됨")

                success = True
                break  # 성공 시 재시도 루프 탈출

            except Exception as e:
                err_type = type(e).__name__
                log(f"❌ {job} {year}-{month:02d} 실패 (시도 {attempt}/{MAX_GAP_RETRIES}): {err_type}: {e}")

                is_network = err_type in ("NetworkError", "ConnectionError", "Timeout")

                if is_network and attempt < MAX_GAP_RETRIES:
                    backoff = 2 ** attempt * 5  # 10초, 20초
                    log(f"⏳ {backoff}초 후 재시도...")
                    time.sleep(backoff)
                    continue

                # 최종 실패
                errors.append({"period": f"{job} {year}-{month:02d}", "type": err_type})

                if is_network:
                    consecutive_network_errors += 1
                    if consecutive_network_errors >= CONSECUTIVE_FAIL_LIMIT:
                        log(f"⏳ 연속 네트워크 에러 {consecutive_network_errors}회, {CONSECUTIVE_FAIL_WAIT}초 대기 후 계속...")
                        time.sleep(CONSECUTIVE_FAIL_WAIT)
                        consecutive_network_errors = 0
                break  # 재시도 불필요한 에러 또는 최종 실패

    # 결과 알림
    status = "🎯" if not errors else "⚠️"
    error_summary = ""
    if errors:
        # Slack에는 구간 + 에러 종류만 (상세 URL 제외)
        from collections import Counter
        err_by_type = Counter(e["type"] for e in errors)
        err_periods = [e["period"] for e in errors]
        type_summary = ", ".join(f"{t} {c}건" for t, c in err_by_type.items())
        error_summary = f"\n\n❌ 에러 ({len(errors)}개, {type_summary}):\n" + "\n".join(f"  • {p}" for p in err_periods[:10])

    msg = f"""{status} 누락 구간 재수집 완료
채운 구간: {len(filled)}개
신규 insert: {total_inserted:,}건
API 사용: {api_calls}/{MAX_API_CALLS}{error_summary}
"""
    log(msg)
    send_slack_message(msg)
    return True


if __name__ == "__main__":
    sys.exit(0 if fill_gaps() else 1)

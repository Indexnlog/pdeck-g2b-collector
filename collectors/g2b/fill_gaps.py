#!/usr/bin/env python3
"""
누락 구간 재수집 스크립트.
DB에서 데이터가 0건인 (연도, 월, 종류) 구간을 찾아 재수집한다.
전체 수집 완료 후 실행할 것.
"""
import os
import sys
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

from utils.db import get_connection, insert_contracts
from utils.g2b_client import G2BClient
from utils.logger import log
from utils.slack import send_slack_message

# 수집 대상 범위
START_YEAR = 2016
START_MONTH = 2
END_YEAR = 2026
END_MONTH = 3  # 운영 목표: 2026-03 계약월까지 (collect_all 상한은 실행 월의 전달까지이므로 4월 이후 실행과 맞춤)

# 종류별 bsns_div_nm 매핑 (DB에 저장된 값 기준)
JOB_TO_DIV = {
    "물품": "물품",
    "공사": "공사",
    "용역": "용역",
    "외자": "외자",
}

API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 1000


def find_gaps():
    """DB에서 데이터가 있는 (연도, 월) 구간을 조회하고, 빈 구간 반환."""
    # DB에서 종류별 존재하는 (연도, 월) 조합 조회
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT collected_year, collected_month, COUNT(*)
                FROM contracts
                GROUP BY collected_year, collected_month
                ORDER BY collected_year, collected_month
            """)
            existing = {}
            for row in cur.fetchall():
                key = (row[0], row[1])
                existing[key] = row[2]

    # 전체 예상 구간 생성
    gaps = []
    year, month = START_YEAR, START_MONTH
    while year < END_YEAR or (year == END_YEAR and month <= END_MONTH):
        key = (year, month)
        count = existing.get(key, 0)
        # 데이터가 비정상적으로 적은 구간도 포함 (0건 = 확실한 누락)
        if count == 0:
            gaps.append((year, month))

        # 다음 월로 이동
        if month < 12:
            month += 1
        else:
            year += 1
            month = 1

    return gaps, existing


def fill_gaps():
    """누락 구간을 재수집."""
    log("🔍 누락 구간 탐색 시작...")
    gaps, existing = find_gaps()

    if not gaps:
        msg = "✅ 누락 구간 없음! 모든 (연도, 월) 구간에 데이터가 있습니다."
        log(msg)
        send_slack_message(msg)
        return True

    log(f"⚠️ 누락 구간 {len(gaps)}개 발견:")
    for y, m in gaps:
        log(f"   - {y}년 {m}월")

    # 재수집
    client = G2BClient(API_KEY)
    jobs = ["물품", "공사", "용역", "외자"]
    api_calls = 0
    total_inserted = 0
    filled = []
    errors = []

    send_slack_message(
        f"🔧 누락 구간 재수집 시작\n"
        f"대상: {len(gaps)}개 월 × 4종 = 최대 {len(gaps) * 4}개 구간"
    )

    from collectors.g2b.collect_all import parse_xml_elements

    for year, month in gaps:
        for job in jobs:
            if api_calls >= MAX_API_CALLS:
                log(f"⛔ API 한도 도달 ({api_calls}/{MAX_API_CALLS}). 나머지는 다음 실행에서.")
                break

            try:
                log(f"📡 재수집: {job} {year}년 {month}월")
                month_inserted = 0

                # fetch_pages()로 페이지 단위 수집 + 즉시 DB insert (메모리 효율적)
                for xml_items, page_calls in client.fetch_pages(job, year, month):
                    api_calls += page_calls
                    rows = parse_xml_elements(xml_items, year, month)
                    inserted = insert_contracts(rows)
                    month_inserted += inserted
                    del rows  # 즉시 메모리 해제

                if month_inserted > 0:
                    filled.append(f"{job} {year}-{month:02d} ({month_inserted}건)")
                    total_inserted += month_inserted
                    log(f"✅ {job} {year}-{month:02d}: {month_inserted}건 insert")
                else:
                    log(f"ℹ️ {job} {year}-{month:02d}: 데이터 없음 또는 이미 수집됨")

            except Exception as e:
                err = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                log(f"❌ {job} {year}-{month:02d} 실패: {err}")
                errors.append(f"{job} {year}-{month:02d}: {err}")

        if api_calls >= MAX_API_CALLS:
            break

    # 결과 알림
    status = "🎯" if not errors else "⚠️"
    error_summary = ""
    if errors:
        error_summary = f"\n\n❌ 에러 ({len(errors)}개):\n" + "\n".join(f"  • {e}" for e in errors[:5])

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

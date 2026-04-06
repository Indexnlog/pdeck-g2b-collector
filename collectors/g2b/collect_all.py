#!/usr/bin/env python3
import json
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
import ctypes
import pytz

# -----------------------------------------------------------
# 프로젝트 루트 계산 (collectors/g2b 기준)
# -----------------------------------------------------------
current_file_path = os.path.abspath(__file__)
g2b_dir = os.path.dirname(current_file_path)
collectors_dir = os.path.dirname(g2b_dir)
project_root = os.path.dirname(collectors_dir)

# GitHub Actions / 로컬 공통 대응
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 로컬 .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

print(f"✅ 프로젝트 루트: {project_root}")
print(f"📂 루트 내용물: {os.listdir(project_root)}")

# -----------------------------------------------------------
# imports
# -----------------------------------------------------------
try:
    from utils.db import create_table, insert_contracts, load_progress, save_progress, save_run_history, find_collection_gaps, mark_period_collected
    from utils.g2b_client import G2BClient
    from utils.logger import log
    from utils.slack import send_slack_message

    from utils.api_error_handler import (
        error_context,
        APIException,
        NetworkError,
        RateLimitError,
        ValidationError,
    )

except ImportError as e:
    print(f"\n🚫 Import 실패: {e}")
    print(f"sys.path = {sys.path}")
    traceback.print_exc()
    sys.exit(1)

# -----------------------------------------------------------
# 설정값
# -----------------------------------------------------------
API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 1000
LOCK_FILE = os.path.join(project_root, "collector.lock")


def is_pid_running(pid: int) -> bool:
    """Windows에서 PID가 살아있는지 확인."""
    if pid <= 0:
        return False

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    if not handle:
        return False

    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def acquire_lock() -> tuple[bool, str | None]:
    """중복 실행 방지를 위한 락파일 생성."""
    now = datetime.now().isoformat(timespec="seconds")
    current = {"pid": os.getpid(), "started_at": now}

    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

        existing_pid = int(existing.get("pid", 0) or 0)
        existing_started = existing.get("started_at", "알 수 없음")

        if is_pid_running(existing_pid):
            return False, (
                f"이미 수집기가 실행 중입니다. "
                f"PID={existing_pid}, started_at={existing_started}"
            )

        # 죽은 프로세스의 락파일은 자동 정리
        try:
            os.remove(LOCK_FILE)
        except OSError:
            return False, "이전 락파일을 정리하지 못했습니다"

    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return True, None


def release_lock():
    """수집 종료 시 락파일 제거."""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


# -----------------------------------------------------------
# XML 문자열 → DB row 리스트 변환
# -----------------------------------------------------------
def parse_items_to_rows(xml_content: str, year: int, month: int) -> list:
    """XML 문자열 → DB row 리스트 (하위 호환용, 소량 데이터에만 사용)"""
    try:
        root = ET.fromstring(f"<root>{xml_content}</root>")
    except ET.ParseError as e:
        log(f"⚠️ XML 파싱 실패: {e}")
        return []
    return parse_xml_elements(root.findall("item"), year, month)


def parse_xml_elements(items: list, year: int, month: int) -> list:
    """XML Element 리스트 → DB row 리스트 (메모리 효율적: 페이지 단위로 호출)"""
    rows = []
    for item in items:
        def g(tag):
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else None

        def to_int(tag):
            v = g(tag)
            try:
                return int(v) if v else None
            except (ValueError, TypeError):
                return None

        def to_date(tag):
            v = g(tag)
            if v and len(v) == 10 and v[4] == "-":
                return v
            return None

        row = {
            "unty_cntrct_no":               g("untyCntrctNo"),
            "bsns_div_nm":                  g("bsnsDivNm"),
            "cntrct_nm":                    g("cntrctNm"),
            "cntrct_cncls_date":            to_date("cntrctCnclsDate"),
            "cntrct_prd":                   g("cntrctPrd"),
            "tot_cntrct_amt":               to_int("totCntrctAmt"),
            "thtm_cntrct_amt":              to_int("thtmCntrctAmt"),
            "cntrct_instt_cd":              g("cntrctInsttCd"),
            "cntrct_instt_nm":              g("cntrctInsttNm"),
            "cntrct_instt_jrsdctn_div_nm":  g("cntrctInsttJrsdctnDivNm"),
            "cntrct_cncls_mthd_nm":         g("cntrctCnclsMthdNm"),
            "pay_div_nm":                   g("payDivNm"),
            "ntce_no":                      g("ntceNo"),
            "corp_list":                    g("corpList"),
            "lngtrm_ctnu_div_nm":           g("lngtrmCtnuDivNm"),
            "cmmn_cntrct_yn":               g("cmmnCntrctYn"),
            "rgst_dt":                      g("rgstDt"),
            "collected_year":               year,
            "collected_month":              month,
        }
        if row["unty_cntrct_no"]:
            rows.append(row)

    return rows


# -----------------------------------------------------------
# 다음 수집 구간 계산
# -----------------------------------------------------------
def get_next_period(job, year, month):
    jobs = ["물품", "공사", "용역", "외자"]

    if month < 12:
        return job, year, month + 1

    idx = jobs.index(job)
    if idx < len(jobs) - 1:
        return jobs[idx + 1], year, 1
    else:
        return jobs[0], year + 1, 1


# -----------------------------------------------------------
# 메인 로직
# -----------------------------------------------------------
def main():
    progress = None
    total_new = 0
    saved = []
    errors = []

    try:
        log("🚀 G2B 수집 시작")

        # 1. 입력값 검증
        if not API_KEY:
            raise ValidationError("API_KEY 환경변수가 설정되지 않았습니다")

        # 2. DB 테이블 준비
        with error_context("DB 테이블 생성"):
            create_table()

        # 3. progress 로드
        with error_context("progress 로드"):
            progress = load_progress()
            log(f"📊 현재 진행 위치: {progress['current_job']} {progress['current_year']}년 {progress['current_month']}월")
            log(f"📊 누적 수집: {progress['total_collected']:,}건")

        # 4. API 카운터 리셋 (날짜가 바뀐 경우만 리셋) — Slack 알림보다 먼저!
        tz = pytz.timezone("Asia/Seoul")
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        last_run = progress.get("last_run_date", "")

        if last_run != today:
            progress["daily_api_calls"] = 0
            log(f"🔄 API 카운터 리셋 (새 날짜: {today})")
        else:
            used_today = progress.get("daily_api_calls", 0)
            log(f"📊 오늘 이미 사용한 API 호출: {used_today}/{MAX_API_CALLS}")
            if used_today >= MAX_API_CALLS:
                msg = (
                    f"⛔ G2B API 일일 한도 소진 ({used_today}/{MAX_API_CALLS}회)\n"
                    f"내일 이어서 수집합니다.\n"
                    f"현재 위치: {progress.get('current_job')} "
                    f"{progress.get('current_year')}년 {progress.get('current_month')}월"
                )
                log(msg)
                send_slack_message(msg)
                return True  # 정상 종료 (실패 아님)

        # 5. 수집 시작 Slack 알림 (리셋 후 정확한 값 표시)
        send_slack_message(
            f"🚀 G2B 수집 시작\n"
            f"현재 위치: {progress['current_job']} {progress['current_year']}년 {progress['current_month']}월\n"
            f"API: {progress.get('daily_api_calls', 0)}/{MAX_API_CALLS}"
        )

        # 6. G2B 클라이언트 생성
        client = G2BClient(API_KEY)

        # 7. 수집 종료 기준: 현재 달의 전달까지 (매월 자동 갱신)
        if now.month == 1:
            limit_year, limit_month = now.year - 1, 12
        else:
            limit_year, limit_month = now.year, now.month - 1
        log(f"📅 수집 범위: ~ {limit_year}년 {limit_month}월")

        # 8. 데이터 수집 루프
        consecutive_zero_inserts = 0  # 연속 0건 insert 카운터 (progress 이상 감지용)
        ZERO_INSERT_ALARM = 50        # 이 이상 연속 0건이면 Slack 경고

        while progress["daily_api_calls"] < MAX_API_CALLS:
            job = progress["current_job"]
            year = progress["current_year"]
            month = progress["current_month"]

            log(f"\n{'='*60}")
            log(f"📍 현재 작업: {job} {year}년 {month}월")
            log(f"📊 API 사용량: {progress['daily_api_calls']}/{MAX_API_CALLS}")
            log(f"{'='*60}")

            # 수집 종료 조건: 전달까지만 (루프 상단에서 체크)
            if year > limit_year or (year == limit_year and month > limit_month):
                log(f"📅 {limit_year}년 {limit_month}월까지 모든 데이터 수집 완료")
                break

            period_success = False  # 이 구간 수집 성공 여부

            try:
                # 페이지 단위로 수집 + 즉시 DB insert (메모리 절약)
                month_total = 0
                month_inserted = 0
                for xml_items, page_calls in client.fetch_pages(job, year, month):
                    progress["daily_api_calls"] += page_calls
                    rows = parse_xml_elements(xml_items, year, month)
                    month_total += len(rows)
                    inserted = insert_contracts(rows)
                    month_inserted += inserted
                    del rows  # 즉시 메모리 해제

                if month_total > 0:
                    label = f"{job}_{year}_{month:02d} ({month_inserted:,}건 insert)"
                    saved.append(label)
                    total_new += month_inserted
                    progress["total_collected"] += month_inserted
                    log(f"✅ DB insert 완료: {label} (총 {month_total:,}건 중)")

                    if month_inserted > 0:
                        consecutive_zero_inserts = 0
                    else:
                        consecutive_zero_inserts += 1
                        log(f"⚠️ 중복 구간 (이미 수집됨): {consecutive_zero_inserts}회 연속")
                else:
                    log(f"ℹ️ {job} {year}년 {month}월 - 데이터 없음")

                period_success = True  # 에러 없이 수집 완료
                mark_period_collected(job, year, month)

            except RateLimitError as e:
                log(f"⚠️ API 한도 도달: {e}")
                errors.append(f"API 한도 도달: {job} {year}-{month}")
                break

            except APIException as e:
                log(f"⚠️ API 에러 ({job} {year}-{month}): {e}")
                errors.append(f"API 에러: {job} {year}-{month} - {e}")
                # progress 전진하지 않고 중단 — 다음 실행에서 같은 구간 재시도
                break

            except Exception as e:
                err_detail = f"{type(e).__name__}: {e}" if str(e) else f"{type(e).__name__} (메시지 없음)"
                log(f"❌ 예상치 못한 에러 ({job} {year}-{month}): {err_detail}")
                log(f"   traceback: {traceback.format_exc()}")
                errors.append(f"예상치 못한 에러: {job} {year}-{month} - {err_detail}")
                # progress 전진하지 않고 중단 — 다음 실행에서 같은 구간 재시도
                break

            # 성공한 경우에만 다음 구간으로 이동
            if period_success:
                next_job, next_year, next_month = get_next_period(job, year, month)
                progress.update({
                    "current_job": next_job,
                    "current_year": next_year,
                    "current_month": next_month,
                })

            # 타임아웃 대비: 매 구간마다 DB에 progress 저장
            try:
                save_progress(progress)
            except Exception:
                pass

            # 연속 0건 insert가 너무 많으면 progress 이상 경고 후 중단
            if consecutive_zero_inserts >= ZERO_INSERT_ALARM:
                warn_msg = (
                    f"⚠️ progress 위치 이상 감지\n"
                    f"{consecutive_zero_inserts}개 구간 연속 0건 insert.\n"
                    f"현재 위치: {job} {year}년 {month}월\n"
                    f"이미 수집된 구간을 헛돌고 있을 수 있습니다.\n"
                    f"scripts\\reset_progress.ps1 로 로컬 progress 위치를 재설정하세요."
                )
                log(warn_msg)
                send_slack_message(warn_msg)
                errors.append("progress 위치 이상 - 수집 중단")
                break

        # 8. 진행 상황 저장 (DB)
        progress["last_run_date"] = today
        with error_context("progress DB 저장"):
            try:
                save_progress(progress)
                log("✅ progress DB 저장 완료")
            except Exception as e:
                log(f"⚠️ progress DB 저장 실패: {e}")
                errors.append(f"progress DB 저장 실패: {e}")

        # 9. 실행 이력 저장
        try:
            save_run_history(
                run_date=today,
                collected=total_new,
                api_calls=progress["daily_api_calls"],
                end_job=progress["current_job"],
                end_year=progress["current_year"],
                end_month=progress["current_month"],
            )
            log("✅ 실행 이력 저장 완료")
        except Exception as e:
            log(f"⚠️ 실행 이력 저장 실패: {e}")

        # 10. 누락 구간 감지
        gap_summary = ""
        try:
            gaps = find_collection_gaps()
            if gaps:
                gap_count = len(gaps)
                # job별 갯수 요약
                from collections import Counter
                job_counts = Counter(g["job"] for g in gaps)
                job_detail = ", ".join(f"{j} {c}개" for j, c in job_counts.items())
                gap_summary = f"\n\n🔍 누락 구간 {gap_count}개 감지: {job_detail}"
                gap_summary += f"\n   첫 누락: {gaps[0]['job']} {gaps[0]['year']}-{gaps[0]['month']:02d}"
                gap_summary += f"\n   💡 scripts\\find_gaps.py --backfill 로 재수집 가능"
                log(f"🔍 누락 구간 {gap_count}개 감지됨")
            else:
                log("✅ 누락 구간 없음")
        except Exception as e:
            log(f"⚠️ 누락 구간 감지 실패 (치명적이지 않음): {e}")

        # 11. 결과 알림
        status_emoji = "🎯" if not errors else "⚠️"
        error_summary = ""
        if errors:
            error_summary = f"\n\n❌ 발생한 에러 ({len(errors)}개):\n" + "\n".join(f"  • {e}" for e in errors[:5])
            if len(errors) > 5:
                error_summary += f"\n  • ... 외 {len(errors) - 5}개"

        message = f"""{status_emoji} G2B 수집 완료
오늘 수집: {total_new:,}건 → SQLite insert
API 호출: {progress['daily_api_calls']}/{MAX_API_CALLS} (오늘 누적)
처리 구간: {len(saved)}개
총 누적: {progress.get('total_collected', 0):,}건{error_summary}{gap_summary}
"""
        send_slack_message(message)
        log("🎉 작업 완료")
        return True

    except ValidationError as e:
        msg = f"❌ 입력값 검증 실패: {e}"
        log(msg)
        send_slack_message(msg)
        return False

    except NetworkError as e:
        msg = f"❌ 네트워크 연결 실패: {e}\n재시도했지만 연결할 수 없습니다."
        log(msg)
        send_slack_message(msg)
        return False

    except APIException as e:
        msg = f"❌ API 에러: {e}\n상세: {traceback.format_exc()}"
        log(msg)
        send_slack_message(msg)
        return False

    except Exception as e:
        msg = f"❌ 치명적 오류 발생: {e}\n```{traceback.format_exc()}```"
        log(msg)
        send_slack_message(msg)
        return False

    finally:
        if progress:
            try:
                import json
                with open("progress_backup.json", "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                log("📁 로컬 백업 저장 완료: progress_backup.json")
            except Exception:
                pass


if __name__ == "__main__":
    locked, lock_error = acquire_lock()
    if not locked:
        print(f"⛔ {lock_error}")
        sys.exit(0)

    try:
        sys.exit(0 if main() else 1)
    finally:
        release_lock()

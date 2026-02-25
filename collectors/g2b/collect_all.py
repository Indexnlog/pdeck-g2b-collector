#!/usr/bin/env python3
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
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

print(f"✅ 프로젝트 루트: {project_root}")
print(f"📂 루트 내용물: {os.listdir(project_root)}")

# -----------------------------------------------------------
# imports
# -----------------------------------------------------------
try:
    from utils.drive import (
        download_progress_json,
        upload_progress_json,
        test_drive_connection,
    )
    from utils.db import create_table, insert_contracts
    from utils.g2b_client import G2BClient
    from utils.logger import log
    from utils.slack import send_slack_message

    from utils.api_error_handler import (
        error_context,
        safe_api_call,
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
PROGRESS_FILE_ID = "1_AKg04eOjQy3KBcjhp2xkkm1jzBcAjn-"
API_KEY = os.getenv("API_KEY")
MAX_API_CALLS = 1000


# -----------------------------------------------------------
# XML 문자열 → DB row 리스트 변환
# -----------------------------------------------------------
def parse_items_to_rows(xml_content: str, year: int, month: int) -> list:
    try:
        root = ET.fromstring(f"<root>{xml_content}</root>")
    except ET.ParseError as e:
        log(f"⚠️ XML 파싱 실패: {e}")
        return []

    rows = []
    for item in root.findall("item"):
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
            # YYYY-MM-DD 형식만 허용
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
        if row["unty_cntrct_no"]:  # PK 없는 행 제외
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

        # 3. Drive 연결 테스트 (progress.json용)
        with error_context("Google Drive 연결 확인"):
            connection_test = safe_api_call(
                test_drive_connection,
                max_retries=3,
                default_value=False
            )
            if not connection_test:
                raise NetworkError("Google Drive 연결에 실패했습니다")

        # 4. progress.json 다운로드
        with error_context("progress.json 다운로드"):
            progress = safe_api_call(
                download_progress_json,
                PROGRESS_FILE_ID,
                max_retries=3,
                default_value=None
            )
            if not progress:
                raise Exception("progress.json 로드 실패 - Drive에서 파일을 가져올 수 없습니다")

        # 5. API 카운터 리셋
        tz = pytz.timezone("Asia/Seoul")
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        progress["daily_api_calls"] = 0
        log(f"🔄 API 카운터 리셋 (실행 시각: {now.strftime('%Y-%m-%d %H:%M:%S')})")

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

            try:
                xml, count, used = client.fetch_data(job, year, month)
                progress["daily_api_calls"] += used

                if count > 0:
                    rows = parse_items_to_rows(xml, year, month)
                    inserted = insert_contracts(rows)
                    label = f"{job}_{year}_{month:02d} ({inserted:,}건 insert)"
                    saved.append(label)
                    total_new += inserted
                    progress["total_collected"] += inserted
                    log(f"✅ DB insert 완료: {label}")

                    if inserted > 0:
                        consecutive_zero_inserts = 0
                    else:
                        consecutive_zero_inserts += 1
                        log(f"⚠️ 중복 구간 (이미 수집됨): {consecutive_zero_inserts}회 연속")
                else:
                    log(f"ℹ️ {job} {year}년 {month}월 - 데이터 없음")

            except RateLimitError as e:
                log(f"⚠️ API 한도 도달: {e}")
                errors.append(f"API 한도 도달: {job} {year}-{month}")
                break

            except APIException as e:
                log(f"⚠️ API 에러 ({job} {year}-{month}): {e}")
                errors.append(f"API 에러: {job} {year}-{month} - {e}")

            except Exception as e:
                log(f"❌ 예상치 못한 에러 ({job} {year}-{month}): {e}")
                errors.append(f"예상치 못한 에러: {job} {year}-{month} - {e}")

            # 다음 구간으로 이동
            next_job, next_year, next_month = get_next_period(job, year, month)
            progress.update({
                "current_job": next_job,
                "current_year": next_year,
                "current_month": next_month,
            })

            # 타임아웃 대비: 매 구간마다 로컬 파일에 progress 저장
            # (upload_progress.py step이 이 파일을 Drive에 올림)
            try:
                import json as _json
                with open("progress.json", "w", encoding="utf-8") as _f:
                    _json.dump(progress, _f, ensure_ascii=False)
            except Exception:
                pass

            # 연속 0건 insert가 너무 많으면 progress 이상 경고 후 중단
            if consecutive_zero_inserts >= ZERO_INSERT_ALARM:
                warn_msg = (
                    f"⚠️ progress 위치 이상 감지\n"
                    f"{consecutive_zero_inserts}개 구간 연속 0건 insert.\n"
                    f"현재 위치: {job} {year}년 {month}월\n"
                    f"이미 수집된 구간을 헛돌고 있을 수 있습니다.\n"
                    f"GitHub Actions > G2B > Reset Progress Position 으로 위치를 재설정하세요."
                )
                log(warn_msg)
                send_slack_message(warn_msg)
                errors.append("progress 위치 이상 - 수집 중단")
                break

            # 수집 종료 조건: 전달까지만
            if next_year > limit_year or (next_year == limit_year and next_month > limit_month):
                log(f"📅 {limit_year}년 {limit_month}월까지 모든 데이터 수집 완료")
                break

        # 8. 진행 상황 저장 (Drive)
        progress["last_run_date"] = today
        with error_context("progress.json 업로드"):
            try:
                upload_progress_json(progress, PROGRESS_FILE_ID)
                log("✅ progress.json 업로드 완료")
            except Exception as e:
                log(f"⚠️ progress.json 업로드 실패: {e}")
                errors.append(f"progress.json 업로드 실패: {e}")

        # 9. 결과 알림
        status_emoji = "🎯" if not errors else "⚠️"
        error_summary = ""
        if errors:
            error_summary = f"\n\n❌ 발생한 에러 ({len(errors)}개):\n" + "\n".join(f"  • {e}" for e in errors[:5])
            if len(errors) > 5:
                error_summary += f"\n  • ... 외 {len(errors) - 5}개"

        message = f"""{status_emoji} G2B 수집 완료
오늘 수집: {total_new:,}건 → CockroachDB insert
API 호출: {progress['daily_api_calls']}/{MAX_API_CALLS}
처리 구간: {len(saved)}개
총 누적: {progress.get('total_collected', 0):,}건{error_summary}
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
    sys.exit(0 if main() else 1)

#!/usr/bin/env python3
"""
시스템 상태 모니터링 스크립트
GitHub Actions에서 실행하여 시스템 헬스체크 수행
"""

import os
import sys
import traceback
from datetime import datetime
import pytz

# 프로젝트 루트 설정
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from utils.drive import test_drive_connection, download_progress_json
    from utils.g2b_client import G2BClient
    from utils.slack import send_slack_message
    from utils.logger import log
except ImportError as e:
    print(f"❌ Import 실패: {e}")
    sys.exit(1)


def check_environment_variables():
    """환경변수 확인"""
    required_vars = [
        "API_KEY",
        "GOOGLE_CREDENTIALS",
        "SLACK_TOKEN",
        "SLACK_CHANNEL_ID"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        log(f"❌ 누락된 환경변수: {', '.join(missing)}")
        return False, missing

    log(f"✅ 모든 환경변수 설정됨 ({len(required_vars)}개)")
    return True, []


def check_drive_connection():
    """Google Drive 연결 확인"""
    try:
        if test_drive_connection():
            log("✅ Google Drive 연결 성공")
            return True, None
        else:
            log("❌ Google Drive 연결 실패")
            return False, "연결 테스트 실패"
    except Exception as e:
        log(f"❌ Google Drive 연결 오류: {e}")
        return False, str(e)


def check_g2b_api():
    """G2B API 연결 확인"""
    try:
        api_key = os.getenv("API_KEY")
        if not api_key:
            return False, "API_KEY 없음"

        client = G2BClient(api_key)
        if client.test_connection():
            log("✅ G2B API 연결 성공")
            return True, None
        else:
            log("❌ G2B API 연결 실패")
            return False, "연결 테스트 실패"

    except Exception as e:
        log(f"❌ G2B API 연결 오류: {e}")
        return False, str(e)


def check_progress_status():
    """progress.json 상태 확인"""
    try:
        progress_file_id = "1_AKg04eOjQy3KBcjhp2xkkm1jzBcAjn-"
        progress = download_progress_json(progress_file_id)

        if not progress:
            return False, "progress.json을 불러올 수 없음", {}

        # 중요 정보 추출
        info = {
            "current_job": progress.get("current_job", "알 수 없음"),
            "current_year": progress.get("current_year", "알 수 없음"),
            "current_month": progress.get("current_month", "알 수 없음"),
            "daily_api_calls": progress.get("daily_api_calls", 0),
            "total_collected": progress.get("total_collected", 0),
            "last_run_date": progress.get("last_run_date", "없음"),
            "last_api_reset_date": progress.get("last_api_reset_date", "없음")
        }

        log(f"✅ 진행 상태: {info['current_job']} {info['current_year']}-{info['current_month']}")
        log(f"   API 사용: {info['daily_api_calls']}/500회")
        log(f"   총 수집: {info['total_collected']:,}건")
        log(f"   마지막 실행: {info['last_run_date']}")

        return True, None, info

    except Exception as e:
        log(f"❌ 진행 상태 확인 오류: {e}")
        return False, str(e), {}


def check_last_run_status():
    """마지막 실행 상태 확인"""
    try:
        tz = pytz.timezone("Asia/Seoul")
        today = datetime.now(tz).strftime("%Y-%m-%d")

        _, _, info = check_progress_status()

        if not info:
            return False, "진행 상태 정보 없음"

        last_run = info.get("last_run_date", "")

        if last_run == today:
            log(f"✅ 오늘 실행됨 ({last_run})")
            return True, None
        elif last_run:
            log(f"⚠️ 마지막 실행: {last_run} (오늘 아님)")
            return True, f"마지막 실행: {last_run}"
        else:
            log("⚠️ 실행 기록 없음")
            return False, "실행 기록 없음"

    except Exception as e:
        log(f"❌ 실행 상태 확인 오류: {e}")
        return False, str(e)


def run_health_check():
    """전체 헬스체크 실행"""
    print("="*60)
    print("🏥 시스템 헬스체크 시작")
    print("="*60)

    results = {}
    errors = []

    # 1. 환경변수 확인
    print("\n[1/5] 환경변수 확인...")
    success, missing = check_environment_variables()
    results["환경변수"] = "✅" if success else "❌"
    if not success:
        errors.append(f"환경변수 누락: {', '.join(missing)}")

    # 2. Google Drive 연결
    print("\n[2/5] Google Drive 연결 확인...")
    success, error = check_drive_connection()
    results["Google Drive"] = "✅" if success else "❌"
    if not success:
        errors.append(f"Drive 연결 실패: {error}")

    # 3. G2B API 연결
    print("\n[3/5] G2B API 연결 확인...")
    success, error = check_g2b_api()
    results["G2B API"] = "✅" if success else "❌"
    if not success:
        errors.append(f"G2B API 실패: {error}")

    # 4. progress.json 상태
    print("\n[4/5] 진행 상태 확인...")
    success, error, info = check_progress_status()
    results["진행 상태"] = "✅" if success else "❌"
    if not success:
        errors.append(f"진행 상태 확인 실패: {error}")

    # 5. 마지막 실행 확인
    print("\n[5/5] 마지막 실행 확인...")
    success, warning = check_last_run_status()
    results["마지막 실행"] = "✅" if success and not warning else "⚠️"
    if warning:
        errors.append(f"실행 주의: {warning}")

    # 결과 요약
    print("\n" + "="*60)
    print("📊 헬스체크 결과")
    print("="*60)

    for check_name, status in results.items():
        print(f"{status} {check_name}")

    if errors:
        print(f"\n❌ 발견된 문제 ({len(errors)}개):")
        for error in errors:
            print(f"  • {error}")
    else:
        print("\n✅ 모든 시스템 정상")

    # Slack 알림 (선택사항)
    if os.getenv("SEND_SLACK_NOTIFICATION") == "true":
        try:
            status_emoji = "✅" if not errors else "⚠️"
            tz = pytz.timezone("Asia/Seoul")
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S KST")

            message = f"{status_emoji} 시스템 헬스체크\n\n"
            message += f"⏰ {timestamp}\n\n"

            for check_name, status in results.items():
                message += f"{status} {check_name}\n"

            if errors:
                message += f"\n⚠️ 발견된 문제 ({len(errors)}개):\n"
                for error in errors[:3]:  # 최대 3개만
                    message += f"• {error}\n"
                if len(errors) > 3:
                    message += f"• ... 외 {len(errors) - 3}개\n"

            send_slack_message(message)
            print("\n📤 Slack 알림 전송 완료")

        except Exception as e:
            print(f"\n⚠️ Slack 알림 실패: {e}")

    print("="*60)

    # 중대한 문제가 있으면 실패로 종료
    critical_errors = [e for e in errors if "환경변수" in e or "Drive 연결" in e]
    if critical_errors:
        print("\n❌ 중대한 문제 발견, 종료 코드 1")
        return False

    return True


if __name__ == "__main__":
    try:
        success = run_health_check()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 치명적 오류: {e}")
        print(traceback.format_exc())
        sys.exit(1)

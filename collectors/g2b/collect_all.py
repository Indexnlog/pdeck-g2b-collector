import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from utils.logger import log
from utils.slack import send_slack_message
from utils.g2b_client import fetch_raw_data, append_to_year_file
from utils.drive import (
    download_progress_json, 
    upload_progress_json, 
    test_drive_connection
)

# 환경변수에서 가져오기
GDRIVE_PROGRESS_FILE_ID = os.getenv("GDRIVE_PROGRESS_FILE_ID")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")


def get_korea_date():
    """한국 시간 기준 현재 날짜 반환"""
    korea_tz = pytz.timezone('Asia/Seoul')
    korea_now = datetime.now(korea_tz)
    return korea_now.strftime('%Y-%m-%d')


def check_and_reset_daily_api_count(progress):
    """
    날짜 체크 및 API 카운트 자동 리셋
    한국 시간 기준으로 날짜 변경 감지
    
    Returns:
        bool: 리셋이 수행되었는지 여부
    """
    today_korea = get_korea_date()
    last_date = progress.get('last_run_date', '')
    
    log(f"🗓️ 날짜 체크: 오늘 {today_korea}, 마지막 실행 {last_date}")
    
    if last_date != today_korea:
        old_count = progress.get('daily_api_calls', 0)
        progress['daily_api_calls'] = 0
        progress['last_run_date'] = today_korea
        
        log(f"🔄 날짜 변경 감지: {last_date} → {today_korea}")
        log(f"   └─ API 카운트 리셋: {old_count} → 0")
        
        return True
    
    log(f"ℹ️ 같은 날짜 계속 진행 (API: {progress.get('daily_api_calls', 0)}/500)")
    return False


def test_actual_api_limit():
    """
    실제 나라장터 API 한도를 간단히 테스트
    간단한 API 호출로 서버 응답 확인
    
    Returns:
        bool: API 호출이 가능한지 여부
    """
    try:
        from utils.g2b_client import G2BClient
        
        api_key = os.getenv("API_KEY")
        if not api_key:
            log("⚠ API 키가 없어 실제 한도 테스트 불가")
            return False
            
        client = G2BClient(api_key)
        
        # 아주 작은 데이터로 테스트 (2024년 12월 - 데이터가 없을 가능성 높음)
        log("🧪 실제 API 한도 테스트 중...")
        result = client.fetch_raw_data("물품", 2024, 12)
        
        if result['success'] or result['item_count'] == 0:  # 성공이거나 데이터 없음(정상)
            log("✅ 실제 API 한도 여유 있음")
            return True
        else:
            log(f"❌ 실제 API 한도 도달: {result['error_message']}")
            return False
            
    except Exception as e:
        log(f"⚠ API 한도 테스트 중 오류: {e}")
        return False


def should_continue_collection(progress, force_continue=False):
    """
    수집 계속 여부 판단 (개선된 버전)
    
    Args:
        progress: progress 데이터
        force_continue: 강제 진행 플래그
        
    Returns:
        tuple: (계속 여부, 중단 이유)
    """
    daily_limit = 500
    current_calls = progress.get("daily_api_calls", 0)
    
    # 1. 년도 범위 체크 (2024년까지)
    current_year = progress.get("current_year", 0)
    if current_year > 2024:
        return False, f"수집 완료: {current_year}년은 목표 범위 초과"
    
    # 2. API 한도 체크
    if current_calls >= daily_limit:
        if force_continue:
            log("🔧 강제 진행 모드: API 한도 무시")
            return True, ""
            
        log(f"⚠ Progress에서 API 한도 도달: {current_calls}/{daily_limit}")
        
        # 실제 API 테스트해보기
        if test_actual_api_limit():
            log("🔄 실제로는 API 사용 가능 - Progress 리셋")
            progress["daily_api_calls"] = 0
            return True, ""
        else:
            return False, f"일일 API 한도 도달 ({current_calls}/{daily_limit})"
    
    return True, ""


def count_items_in_xml(xml_text):
    """XML에서 실제 아이템 개수 세기"""
    try:
        root = ET.fromstring(xml_text)
        items = root.findall('.//item')
        
        # 빈 아이템 필터링
        valid_items = []
        for item in items:
            if len(list(item)) > 0:  # 실제 데이터가 있는 아이템만
                valid_items.append(item)
                
        return len(valid_items)
        
    except ET.ParseError as e:
        log(f"⚠ XML 파싱 실패, 개수 확인 불가: {e}")
        return 0
    except Exception as e:
        log(f"⚠ 아이템 개수 확인 중 오류: {e}")
        return 0


def increment_month(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


if __name__ == "__main__":
    log("🚀 G2B 자동 수집 시작")
    
    # 1. Drive 연결 테스트 (선택사항)
    if not test_drive_connection():
        log("❌ Google Drive 연결 실패, 수집 중단")
        send_slack_message(
            "```\n"
            "❌ G2B 수집 실패\n"
            "• 사유: Google Drive 연결 실패\n"
            "• 조치: 서비스 계정 키 및 권한 확인 필요\n"
            "```"
        )
        exit(1)

    # 2. Progress 다운로드
    if not GDRIVE_PROGRESS_FILE_ID:
        log("❌ GDRIVE_PROGRESS_FILE_ID 환경변수가 설정되지 않음")
        exit(1)
        
    progress = download_progress_json(GDRIVE_PROGRESS_FILE_ID)
    if progress is None:
        log("❌ Progress 데이터를 불러올 수 없음")
        exit(1)
    
    # 3. 날짜 체크 및 API 카운트 리셋
    progress_updated = False
    if check_and_reset_daily_api_count(progress):
        progress_updated = True
        log("📤 날짜 변경으로 인한 Progress 업로드...")
        upload_success = upload_progress_json(progress, GDRIVE_PROGRESS_FILE_ID)
        if upload_success:
            log("✅ Progress 업데이트 완료")
        else:
            log("⚠ Progress 업로드 실패, 하지만 로컬에서 계속 진행")
    
    job = progress["current_job"]
    year = progress["current_year"]
    month = progress["current_month"]
    
    # 4. 수집 계속 여부 확인
    can_continue, stop_reason = should_continue_collection(progress)
    if not can_continue:
        log(f"🛑 수집 중단: {stop_reason}")
        send_slack_message(
            f"```\n"
            f"🛑 G2B 수집 중단\n"
            f"• 사유: {stop_reason}\n"
            f"• 현재 위치: {job} {year}년 {month}월\n"
            f"• 누적: {progress['total_collected']:,}건\n"
            f"• 한국 시간: {get_korea_date()}\n"
            f"```"
        )
        exit(0)

    # 5. Slack 시작 메시지
    send_slack_message(
        f"```\n"
        f"🚀 G2B 수집 시작\n"
        f"• 진행: {job} {year}년 {month}월\n"
        f"• API 사용: {progress['daily_api_calls']}/500\n"
        f"• 누적: {progress['total_collected']:,}건\n"
        f"• 한국 시간: {get_korea_date()}\n"
        f"```"
    )

    # 6. API 호출 및 결과 검증
    collection_success = False
    collected_count = 0
    error_message = ""
    
    try:
        xml_text, item_count = fetch_raw_data(job, year, month)
        
        # XML 데이터 검증
        if xml_text and item_count >= 0:
            # 연단위 파일에 저장
            filename = append_to_year_file(job, year, xml_text)
            
            # 실제 수집된 건수 계산
            collected_count = count_items_in_xml(xml_text)
            collection_success = True
            
            log(f"✅ 수집 및 저장 완료: {collected_count:,}건")
            
        else:
            error_message = "API 응답은 받았지만 유효한 데이터가 없음"
            log(f"⚠ {error_message}")
            
    except Exception as e:
        error_message = str(e)
        log(f"❌ 수집 오류: {e}")

    # 7. 성공한 경우에만 progress 업데이트
    if collection_success:
        # Progress 데이터 업데이트
        progress["total_collected"] += collected_count
        progress["daily_api_calls"] += 1
        progress["last_run_date"] = get_korea_date()  # 한국 시간으로 업데이트
        
        # 다음 월로 이동 (성공한 경우에만!)
        next_year, next_month = increment_month(year, month)
        progress["current_year"] = next_year
        progress["current_month"] = next_month
        
        # Progress를 Google Drive에 업로드
        upload_success = upload_progress_json(progress, GDRIVE_PROGRESS_FILE_ID)
        
        if not upload_success:
            log("⚠ Progress 업로드 실패, 하지만 수집은 완료됨")
            upload_warning = "\n⚠ Progress 업로드 실패 - 수동 확인 필요"
        else:
            upload_warning = ""
        
        # 성공 Slack 메시지
        send_slack_message(
            f"```\n"
            f"✅ G2B 수집 완료\n"
            f"• 진행: {job} {year}년 {month}월\n"
            f"• 오늘 수집: {collected_count:,}건\n"
            f"• API 호출: {progress['daily_api_calls']}/500\n"
            f"• 누적: {progress['total_collected']:,}건\n"
            f"• 다음: {job} {next_year}년 {next_month}월\n"
            f"• 한국 시간: {get_korea_date()}\n"
            f"```{upload_warning}"
        )
        
        log("✅ 전체 프로세스 완료 - Progress 업데이트됨")
        
    else:
        # 실패한 경우 Progress 유지, API 호출 수만 증가
        progress["daily_api_calls"] += 1
        progress["last_run_date"] = get_korea_date()
        
        # Progress 업로드 (API 호출 카운트만 업데이트)
        upload_success = upload_progress_json(progress, GDRIVE_PROGRESS_FILE_ID)
        
        if not upload_success:
            log("⚠ Progress 업로드도 실패")
            upload_warning = "\n⚠ Progress 업로드도 실패 - 수동 확인 필요"
        else:
            upload_warning = ""
        
        # 실패 Slack 메시지
        send_slack_message(
            f"```\n"
            f"❌ G2B 수집 실패\n"
            f"• 진행: {job} {year}년 {month}월\n"
            f"• 오류: {error_message}\n"
            f"• API 호출: {progress['daily_api_calls']}/500\n"
            f"• 누적: {progress['total_collected']:,}건\n"
            f"• 한국 시간: {get_korea_date()}\n"
            f"⚠ Progress 유지됨 - 다음 실행에서 재시도\n"
            f"```{upload_warning}"
        )
        
        log("⚠ 프로세스 완료 - Progress 유지됨 (재시도 준비)")
        exit(0)
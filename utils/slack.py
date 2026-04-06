import os
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils.logger import log

_SENSITIVE_PATTERN = re.compile(r'serviceKey=[^&\s)]+')


def _mask(text: str) -> str:
    """민감 정보(serviceKey 등)를 마스킹."""
    return _SENSITIVE_PATTERN.sub('serviceKey=***', text)

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")


class SlackNotifier:
    def __init__(self, token: str = None, channel_id: str = None):
        """
        Slack 알림 클라이언트 초기화
        
        Args:
            token: Slack Bot Token (xoxb-로 시작) 또는 User Token (xoxp-로 시작)
            channel_id: 채널 ID (C로 시작) 또는 채널명 (#general)
        """
        self.token = token or SLACK_TOKEN
        self.channel_id = channel_id or SLACK_CHANNEL_ID
        self.client = None
        
        if self.token and self.channel_id:
            self.client = WebClient(token=self.token)
            log(f"✅ Slack 클라이언트 초기화 완료 (채널: {self.channel_id})")
        else:
            log("⚠ Slack 설정 없음 - 메시지 전송이 비활성화됩니다")
    
    def is_enabled(self) -> bool:
        """Slack 알림 활성화 여부"""
        return self.client is not None
    
    def test_connection(self) -> bool:
        """
        🔧 새로 추가: Slack 연결 테스트
        """
        if not self.is_enabled():
            log("⚠ Slack 설정이 없어 연결 테스트를 건너뜁니다")
            return False
            
        try:
            # Bot 정보 확인
            auth_response = self.client.auth_test()
            bot_name = auth_response.get("user", "Unknown Bot")
            team_name = auth_response.get("team", "Unknown Team")
            
            log(f"✅ Slack 연결 테스트 성공")
            log(f"   └─ Bot: {bot_name}")
            log(f"   └─ Team: {team_name}")
            log(f"   └─ 채널: {self.channel_id}")
            
            # 간단한 테스트 메시지 (선택사항)
            # self.send_message("🧪 G2B 자동화 시스템 연결 테스트")
            
            return True
            
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown_error")
            
            if error_code == "invalid_auth":
                log("❌ Slack Token이 잘못되었습니다")
                log("   → SLACK_TOKEN 환경변수 확인")
            elif error_code == "account_inactive":
                log("❌ Slack 계정이 비활성화되었습니다")
            else:
                log(f"❌ Slack API 오류: {error_code}")
                
            return False
            
        except Exception as e:
            log(f"❌ Slack 연결 테스트 실패: {e}")
            return False
    
    def send_message(self, text: str, blocks: Optional[list] = None, 
                    thread_ts: Optional[str] = None) -> bool:
        """
        Slack 메시지 전송 (개선된 버전)
        
        Args:
            text: 메시지 텍스트 (fallback용)
            blocks: Slack Block Kit 블록들 (선택사항)
            thread_ts: 스레드 타임스탬프 (답글용, 선택사항)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.is_enabled():
            log("⚠ Slack 설정 없음 → 메시지 전송 생략")
            log(f"📝 전송할 메시지: {text[:100]}...")
            return False
        
        try:
            # 🔧 개선: 메시지 길이 제한 (40,000자)
            if len(text) > 40000:
                text = text[:39950] + "\n... (메시지가 잘렸습니다)"
                log("⚠ 메시지가 40,000자를 초과하여 잘렸습니다")
            
            # 민감 정보 마스킹 후 전송
            text = _mask(text)

            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts,
                unfurl_links=False,  # 링크 미리보기 비활성화
                unfurl_media=False   # 미디어 미리보기 비활성화
            )
            
            message_ts = response.get("ts")
            log(f"📨 Slack 메시지 전송 완료 (ts: {message_ts})")
            return True
            
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown_error")
            
            # 🔧 개선: 에러별 상세 처리
            if error_code == "channel_not_found":
                log(f"❌ Slack 채널을 찾을 수 없음: {self.channel_id}")
                log("   → 채널 ID 확인 또는 봇을 채널에 초대")
            elif error_code == "not_in_channel":
                log(f"❌ 봇이 채널에 없음: {self.channel_id}")
                log("   → 봇을 해당 채널에 초대 필요")
            elif error_code == "rate_limited":
                log("❌ Slack API 속도 제한")
                log("   → 잠시 후 다시 시도")
            elif error_code == "invalid_auth":
                log("❌ Slack Token 인증 실패")
                log("   → SLACK_TOKEN 환경변수 확인")
            else:
                log(f"❌ Slack API 오류: {error_code}")
            
            return False
            
        except Exception as e:
            log(f"❌ 예상치 못한 Slack 오류: {e}")
            return False
    
    def send_collection_result(self, result: Dict[str, Any]) -> bool:
        """
        🔧 새로 추가: G2B 수집 결과 전용 메시지 (개선된 포맷)
        """
        category = result['category']
        year = result['year']
        month = result['month']
        collected = result['collected_today']
        api_calls = result['api_calls']
        daily_limit = result['daily_limit']
        total = result['total_accumulated']
        success = result['success']
        error_msg = result.get('error_message', '')
        progress_updated = result.get('progress_updated', False)
        
        # 상태별 이모지 및 색상
        if success:
            emoji = "✅"
            status_text = "수집 성공"
        else:
            emoji = "❌"
            status_text = "수집 실패"
        
        # 메인 메시지 구성 (Markdown 형식)
        message_lines = [
            f"{emoji} **G2B 데이터 {status_text}**",
            f"",
            f"```",
            f"• 진행: {category} {year}년 {month}월",
            f"• 오늘 수집: {collected:,}건",
            f"• API 호출: {api_calls}/{daily_limit}",
            f"• 누적: {total:,}건",
            f"```"
        ]
        
        # 실패 시 추가 정보
        if not success:
            if not progress_updated:
                message_lines.append("⚠️ **Progress 유지됨** - 다음 실행에서 재시도")
            if error_msg:
                message_lines.append(f"🔍 **오류 내용**: {error_msg}")
        
        # 타임스탬프 추가
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        message_lines.append(f"🕐 {timestamp}")
        
        message_text = "\n".join(message_lines)
        
        return self.send_message(message_text)
    
    def send_system_alert(self, title: str, message: str, level: str = "info") -> bool:
        """
        🔧 새로 추가: 시스템 알림 전송
        """
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "success": "✅"
        }
        
        emoji = emoji_map.get(level, "ℹ️")
        
        alert_text = f"{emoji} **{title}**\n\n{message}"
        
        return self.send_message(alert_text)
    
    def send_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """
        🔧 새로 추가: 일일 수집 요약
        """
        total_collected = summary_data.get('total_collected', 0)
        total_api_calls = summary_data.get('total_api_calls', 0)
        categories = summary_data.get('categories', [])
        errors = summary_data.get('errors', [])
        
        emoji = "📊" if not errors else "⚠️"
        
        summary_lines = [
            f"{emoji} **G2B 일일 수집 요약**",
            f"",
            f"```",
            f"• 수집 카테고리: {', '.join(categories) if categories else '없음'}",
            f"• 총 수집 건수: {total_collected:,}건",
            f"• 총 API 호출: {total_api_calls}/500",
            f"```"
        ]
        
        if errors:
            summary_lines.append(f"\n🚨 **발생한 오류** ({len(errors)}건):")
            for i, error in enumerate(errors[:3], 1):  # 최대 3개만
                summary_lines.append(f"{i}. {error}")
            if len(errors) > 3:
                summary_lines.append(f"... 외 {len(errors) - 3}건 더")
        
        summary_text = "\n".join(summary_lines)
        
        return self.send_message(summary_text)


# 🔧 기존 함수도 유지 (호환성)
def send_slack_message(text: str):
    """
    기존 함수 (호환성 유지)
    개선된 SlackNotifier를 내부적으로 사용
    """
    notifier = SlackNotifier()
    
    if not notifier.is_enabled():
        log("⚠️ Slack 설정 없음 → 메시지 전송 생략")
        log(f"📝 전송할 메시지: {text[:100]}...")
        return False
    
    return notifier.send_message(text)


# 🔧 편의 함수들
def send_success_message(category: str, year: int, month: int, 
                        collected: int, total: int, api_calls: int) -> bool:
    """G2B 수집 성공 메시지 전송"""
    result = {
        'category': category,
        'year': year, 
        'month': month,
        'collected_today': collected,
        'api_calls': api_calls,
        'daily_limit': 500,
        'total_accumulated': total,
        'success': True,
        'progress_updated': True
    }
    
    notifier = SlackNotifier()
    return notifier.send_collection_result(result)


def send_error_message(category: str, year: int, month: int,
                      error: str, api_calls: int, total: int) -> bool:
    """G2B 수집 실패 메시지 전송"""  
    result = {
        'category': category,
        'year': year,
        'month': month, 
        'collected_today': 0,
        'api_calls': api_calls,
        'daily_limit': 500,
        'total_accumulated': total,
        'success': False,
        'error_message': error,
        'progress_updated': False
    }
    
    notifier = SlackNotifier()
    return notifier.send_collection_result(result)


def test_slack_setup() -> bool:
    """Slack 설정 테스트"""
    notifier = SlackNotifier()
    return notifier.test_connection()


if __name__ == "__main__":
    # 테스트 실행
    log("🧪 Slack 설정 테스트 시작")
    
    if test_slack_setup():
        log("✅ Slack 테스트 완료")
        
        # 테스트 메시지 전송 (선택사항)
        test_result = send_slack_message("🧪 G2B 자동화 시스템 테스트 메시지")
        if test_result:
            log("✅ 테스트 메시지 전송 성공")
        else:
            log("❌ 테스트 메시지 전송 실패")
    else:
        log("❌ Slack 테스트 실패")
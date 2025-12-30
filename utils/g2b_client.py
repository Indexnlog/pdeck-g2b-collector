import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from utils.logger import log

class G2BClient:
    def __init__(self, api_key):
        self.api_key = api_key
        # ✅ 올바른 기본 URL
        self.base_url = "http://apis.data.go.kr/1230000/ao/CntrctInfoService"
        self.session = requests.Session()
        
    def fetch_paginated_data(self, job, year, month, max_pages=50):
        """
        페이지네이션을 통한 전체 데이터 수집 (API 카운트 정확 추적)
        
        Returns:
            tuple: (combined_xml_data, total_items, api_calls_used)
        """
        log(f"📞 API 호출 시작: {job} {year}-{month:02d}")
        
        # 올바른 메소드 매핑
        method_map = {
            "물품": "getCntrctInfoListThng",
            "공사": "getCntrctInfoListCnstwk", 
            "용역": "getCntrctInfoListServc",
            "외자": "getCntrctInfoListFrgcpt"
        }
        
        if job not in method_map:
            raise ValueError(f"지원하지 않는 업무구분: {job}")
            
        method = method_map[job]
        url = f"{self.base_url}/{method}"
        
        # 월 시작일과 종료일 계산
        start_date = f"{year}{month:02d}010000"  # YYYYMMDDHHMM
        
        # 월 마지막 날 계산
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}{month:02d}{last_day}2359"
        
        all_items = []
        total_count = 0
        api_calls_used = 0
        page = 1
        
        while page <= max_pages:
            params = {
                "serviceKey": self.api_key,
                "numOfRows": 100,  # 페이지당 100건
                "pageNo": page,
                "inqryDiv": 1,  # 등록일시 기준 조회
                "inqryBgnDt": start_date,
                "inqryEndDt": end_date,
                "type": "xml"
            }
            
            try:
                log(f"🔄 페이지 {page} 호출 시도 1/5")
                
                response = self.session.get(
                    url, 
                    params=params,
                    timeout=30,
                    headers={'User-Agent': 'G2B-Collector/1.0'}
                )
                
                # ✅ API 호출 카운트 증가
                api_calls_used += 1
                
                if response.status_code == 200:
                    # XML 응답 파싱
                    try:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.text)
                        
                        # 결과 코드 확인
                        result_code = root.find('.//resultCode')
                        result_msg = root.find('.//resultMsg')
                        error_code = result_code.text if result_code is not None else "99"
                        error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                        
                        if error_code == "00":
                            # 성공적인 응답
                            total_count_elem = root.find('.//totalCount')
                            page_total = int(total_count_elem.text) if total_count_elem is not None else 0
                            
                            # 첫 페이지에서 전체 건수 확인
                            if page == 1:
                                total_count = page_total
                                log(f"📊 전체 데이터: {total_count:,}건 발견")
                            
                            # 이 페이지의 아이템들 추출
                            items = root.findall('.//item')
                            current_page_items = len(items)
                            
                            log(f"✅ 페이지 {page}: {current_page_items}건 수집 (전체: {total_count:,}건)")
                            
                            if current_page_items == 0:
                                log(f"ℹ️ 페이지 {page}: 데이터 없음 - 수집 완료")
                                break
                            
                            # 아이템들을 리스트에 추가
                            for item in items:
                                all_items.append(ET.tostring(item, encoding='unicode'))
                            
                            # 다음 페이지로
                            page += 1
                            
                            # Rate limiting
                            time.sleep(0.5)
                            
                        elif error_code == "03":
                            # 데이터 없음
                            log(f"📭 데이터 없음: {job} {year}-{month:02d}")
                            break
                            
                        else:
                            # 기타 에러
                            log(f"❌ API 에러 [{error_code}]: {error_msg}")
                            break
                            
                    except ET.ParseError as e:
                        log(f"❌ XML 파싱 오류: {e}")
                        break
                        
                else:
                    log(f"❌ HTTP 오류 {response.status_code}")
                    break
                    
            except Exception as e:
                log(f"❌ 페이지 {page} 호출 실패: {e}")
                break
        
        if all_items:
            # 전체 XML 조합
            log(f"🎉 전체 수집 완료: {len(all_items):,}건")
            
            combined_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<response>
    <header>
        <resultCode>00</resultCode>
        <resultMsg>정상</resultMsg>
    </header>
    <body>
        <items>
{"".join(all_items)}
        </items>
        <numOfRows>{len(all_items)}</numOfRows>
        <pageNo>1</pageNo>
        <totalCount>{len(all_items)}</totalCount>
    </body>
</response>"""
            
            return combined_xml, len(all_items), api_calls_used
        else:
            return None, 0, api_calls_used
        """
        나라장터 계약정보 API 호출 (수정된 버전)
        
        Args:
            job: 업무구분 (물품, 공사, 용역, 외자)
            year: 조회 년도
            month: 조회 월
            
        Returns:
            tuple: (xml_text, item_count)
        """
        # ✅ 올바른 메소드 매핑
        method_map = {
            "물품": "getCntrctInfoListThng",
            "공사": "getCntrctInfoListCnstwk", 
            "용역": "getCntrctInfoListServc",
            "외자": "getCntrctInfoListFrgcpt"
        }
        
        if job not in method_map:
            raise ValueError(f"지원하지 않는 업무구분: {job}")
            
        method = method_map[job]
        url = f"{self.base_url}/{method}"
        
        # 월 시작일과 종료일 계산
        start_date = f"{year}{month:02d}010000"  # YYYYMMDDHHMM
        
        # 월 마지막 날 계산
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
            
        # 다음 월 1일에서 1일 빼기 = 이번 월 마지막 날
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}{month:02d}{last_day}2359"
        
        # ✅ 올바른 파라미터 형식
        params = {
            "serviceKey": self.api_key,
            "numOfRows": 1000,  # 최대한 많이 가져오기
            "pageNo": 1,
            "inqryDiv": 1,  # 등록일시 기준 조회
            "inqryBgnDt": start_date,
            "inqryEndDt": end_date,
            "type": "xml"  # XML 응답 요청
        }
        
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                log(f"📡 API 호출 시도 {attempt}/{max_retries}: {job} {year}년 {month}월")
                log(f"   └─ URL: {url}")
                log(f"   └─ 기간: {start_date} ~ {end_date}")
                
                response = self.session.get(
                    url, 
                    params=params,
                    timeout=30,
                    headers={'User-Agent': 'G2B-Collector/1.0'}
                )
                
                if response.status_code == 200:
                    # XML 응답 파싱
                    try:
                        root = ET.fromstring(response.text)
                        
                        # 결과 코드 확인
                        result_code = root.find('.//resultCode')
                        result_msg = root.find('.//resultMsg')
                        error_code = result_code.text if result_code is not None else "99"
                        error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                        
                        if error_code == "00":
                            # 성공적인 응답
                            total_count = root.find('.//totalCount')
                            if total_count is not None:
                                item_count = int(total_count.text)
                                log(f"✅ API 성공: {item_count:,}건 발견")
                                return response.text, item_count
                            else:
                                log("⚠ totalCount 필드가 없음")
                                return response.text, 0
                        else:
                            # 에러코드별 정확한 처리
                            log(f"❌ API 에러코드 {error_code}: {error_msg}")
                            
                            # 즉시 중단해야 하는 에러들
                            if error_code in ["20", "30", "31", "32"]:
                                # 서비스 접근 거부, 서비스 키 문제
                                raise Exception(f"서비스 키/접근 오류 [{error_code}]: {error_msg}")
                                
                            elif error_code == "22":
                                # 일일 트래픽 한도 초과
                                raise Exception(f"일일 API 한도 초과 [{error_code}]: {error_msg}")
                                
                            elif error_code in ["06", "08", "11"]:
                                # 파라미터 오류 (코드 수정 필요)
                                raise Exception(f"파라미터 오류 [{error_code}]: {error_msg}")
                                
                            elif error_code == "03":
                                # 데이터 없음 (정상 케이스)
                                log(f"📭 데이터 없음: {job} {year}-{month}")
                                return f"<response><header><resultCode>00</resultCode><resultMsg>정상</resultMsg></header><body><items></items><totalCount>0</totalCount></body></response>", 0
                                
                            elif error_code in ["01", "02", "04", "05", "12"]:
                                # 서버 오류 (재시도 가능)
                                log(f"⚠ 서버 오류 [{error_code}]: {error_msg} → 재시도")
                                if attempt < max_retries:
                                    wait_time = min(5 + attempt * 2, 15)  # 5, 7, 9, 11초
                                    log(f"⏳ {wait_time}초 대기 후 재시도...")
                                    time.sleep(wait_time)
                                    continue
                                else:
                                    raise Exception(f"반복 서버 오류 [{error_code}]: {error_msg}")
                            else:
                                # 기타 오류
                                raise Exception(f"API 오류 [{error_code}]: {error_msg}")
                                
                    except ET.ParseError as e:
                        log(f"❌ XML 파싱 오류: {e}")
                        log(f"   └─ 응답 내용: {response.text[:500]}...")
                        raise Exception(f"XML 파싱 오류: {e}")
                        
                elif response.status_code == 500:
                    log(f"⚠ API 오류 {response.status_code} → 재시도 {attempt}/{max_retries}")
                    if attempt < max_retries:
                        wait_time = min(3 + attempt, 8)  # 3, 4, 5, 6초 대기
                        log(f"⏳ {wait_time}초 대기 후 재시도...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"HTTP {response.status_code} 오류")
                        
                else:
                    log(f"❌ HTTP 오류 {response.status_code}")
                    log(f"   └─ 응답: {response.text[:200]}...")
                    raise Exception(f"HTTP {response.status_code} 오류")
                    
            except requests.exceptions.Timeout:
                log(f"⏰ 타임아웃 발생 → 재시도 {attempt}/{max_retries}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                else:
                    raise Exception("API 호출 타임아웃")
                    
            except requests.exceptions.RequestException as e:
                log(f"🌐 네트워크 오류: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                else:
                    raise Exception(f"네트워크 오류: {e}")
                    
        raise Exception(f"API 반복 오류 발생: {job} {year}-{month}")


def append_to_year_file(job, year, xml_text):
    """
    연단위 XML 파일에 데이터 추가
    
    Args:
        job: 업무구분
        year: 년도
        xml_text: XML 데이터
        
    Returns:
        str: 저장된 파일명
    """
    import os
    
    # 파일명 생성
    filename = f"g2b_{job}_{year}.xml"
    filepath = os.path.join("/home/claude", filename)
    
    try:
        # 기존 파일이 있는지 확인
        if os.path.exists(filepath):
            # 기존 파일에 추가
            log(f"📁 기존 파일에 추가: {filename}")
            
            # 간단히 XML 내용만 추가 (헤더 제외)
            with open(filepath, 'a', encoding='utf-8') as f:
                # 새로운 월 데이터를 구분하기 위한 주석 추가
                f.write(f"\n<!-- {year}년 추가 데이터 -->\n")
                f.write(xml_text)
                f.write("\n")
        else:
            # 새 파일 생성
            log(f"📁 새 파일 생성: {filename}")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_text)
                
        file_size = os.path.getsize(filepath)
        log(f"💾 파일 저장 완료: {filename} ({file_size:,} bytes)")
        
        return filename
        
    except Exception as e:
        log(f"❌ 파일 저장 오류: {e}")
        raise Exception(f"파일 저장 실패: {e}")


# 테스트용 함수
def test_api_call():
    """API 호출 테스트"""
    import os
    
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("❌ API_KEY 환경변수가 설정되지 않음")
        return
        
    client = G2BClient(api_key)
    
    try:
        # 2024년 12월 데이터로 테스트 (최근 데이터)
        xml_text, item_count = client.fetch_raw_data("물품", 2024, 12)
        print(f"✅ 테스트 성공: {item_count}건")
        print(f"📄 XML 길이: {len(xml_text)} 글자")
        
        # 샘플 저장
        if xml_text:
            filename = append_to_year_file("물품", 2024, xml_text)
            print(f"💾 샘플 파일 저장: {filename}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")


if __name__ == "__main__":
    test_api_call()
#!/usr/bin/env python3
import sys
import re
import warnings

# SSL 경고 무시 (필요시)
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("Error: 라이브러리를 찾을 수 없습니다.")
    sys.exit(1)

def extract_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'(?:be\/)([0-9A-Za-z_-]{11}).*']
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

def get_transcript(video_id):
    try:
        # 1.2.4 버전 방식: 인스턴스 생성 후 fetch() 사용
        api = YouTubeTranscriptApi()
        
        # 한국어(ko) 우선, 없으면 영어(en) 자막을 가져옴
        # .to_raw_data()를 호출해야 리스트 형태의 자막 데이터를 반환함
        transcript_data = api.fetch(video_id, languages=['ko', 'en']).to_raw_data()
        
        return " ".join([item['text'] for item in transcript_data])
    except Exception as e:
        return f"Error: 자막 추출 실패. ({str(e)})"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 get_youtube_transcript.py <url>")
        sys.exit(1)
    
    vid = extract_video_id(sys.argv[1])
    if vid:
        print(get_transcript(vid))
    else:
        print("Error: 유효한 유튜브 URL이 아닙니다.")

#!/usr/bin/env python3
import sys
import re
import json
import subprocess
import warnings

# SSL 경고 무시 (필요시)
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print(json.dumps({"error": "youtube_transcript_api 라이브러리를 찾을 수 없습니다."}))
    sys.exit(1)

def extract_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'(?:be\/)([0-9A-Za-z_-]{11}).*']
    for p in patterns:
        match = re.search(p, url)
        if match: return match.group(1)
    return None

def get_video_metadata(url):
    """yt-dlp으로 영상 제목과 채널명 추출. 실패 시 None 반환."""
    try:
        result = subprocess.run(
            ['yt-dlp', '--print', '%(title)s\n%(channel)s', '--no-playlist', url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            title = lines[0] if len(lines) > 0 else None
            channel = lines[1] if len(lines) > 1 else None
            return title, channel
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None, None

def get_transcript(video_id):
    try:
        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id, languages=['ko', 'en']).to_raw_data()
        return " ".join([item['text'] for item in transcript_data])
    except Exception as e:
        return None, str(e)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python3 get_youtube_transcript.py <url>"}))
        sys.exit(1)

    url = sys.argv[1]
    video_id = extract_video_id(url)
    if not video_id:
        print(json.dumps({"error": "유효한 유튜브 URL이 아닙니다."}))
        sys.exit(1)

    title, channel = get_video_metadata(url)

    transcript = get_transcript(video_id)
    if isinstance(transcript, tuple):
        # 에러 케이스
        print(json.dumps({"error": transcript[1]}))
        sys.exit(1)

    result = {
        "title": title,
        "channel": channel,
        "video_id": video_id,
        "transcript": transcript
    }
    print(json.dumps(result, ensure_ascii=False))

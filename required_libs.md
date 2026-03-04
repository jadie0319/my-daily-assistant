# Required Libraries

`summarize_youtube` 커맨드 실행에 필요한 외부 라이브러리 목록입니다.

## Python 패키지

| 패키지 | 버전 | 용도 | 설치 명령 |
|--------|------|------|-----------|
| `youtube-transcript-api` | >= 1.2.4 | YouTube 자막/트랜스크립트 추출 | `pip3 install youtube-transcript-api` |
| `yt-dlp` | >= 2026.3.3 | 영상 제목 및 채널명 메타데이터 추출 | `pip3 install yt-dlp` |

## 한 번에 설치

```bash
pip3 install youtube-transcript-api yt-dlp
```

> macOS 시스템 Python을 사용하는 경우 `--break-system-packages` 플래그가 필요할 수 있습니다:
> ```bash
> pip3 install --break-system-packages youtube-transcript-api yt-dlp
> ```

## 사용처

- `get_youtube_transcript.py` — YouTube URL을 받아 트랜스크립트와 메타데이터(제목, 채널명)를 JSON으로 출력
- `.claude/commands/obsidian/summarize_youtube.md` — 위 스크립트를 호출하여 Obsidian 노트 생성

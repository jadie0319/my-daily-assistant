# My Daily Service Commands

## YouTube 요약 서비스

### 개요
YouTube 영상의 자막을 추출하고 번역/정리하여 Obsidian 볼트에 자동으로 저장하는 서비스입니다.

### 사용 방법

Claude Code에서 다음 명령어를 실행:

```
/obsidian:summarize_youtube
```

또는 Skill 도구를 통해 실행:
```
skill: "obsidian:summarize_youtube"
```

Codex에서 실행:

```bash
# 백그라운드 실행 (기본)
./.codex/bin/summarize-youtube kr "https://www.youtube.com/watch?v=VIDEO_ID"

# 동기 실행 (완료까지 대기)
./.codex/bin/summarize-youtube --sync en "https://www.youtube.com/watch?v=VIDEO_ID"

# 진행 상태 확인
./.codex/bin/youtube-progress
```

Codex는 첫 번째 인자로 언어 옵션(`kr` 또는 `en`)을 받을 수 있으며, 생략 시 `kr`로 처리됩니다.

### 동작 방식

1. YouTube URL을 입력받습니다
2. 백그라운드에서 자막을 추출하고 번역/정리합니다
3. 결과를 Obsidian 볼트의 `02.Zattelkasten/001_Inbox/` 디렉터리에 저장합니다

### 예시

```bash
# Claude Code에서 실행
/obsidian:summarize_youtube

# 프롬프트가 나타나면 YouTube URL 입력
https://www.youtube.com/watch?v=VIDEO_ID
```

### 출력 위치

- **저장 경로**: `{OBSIDIAN_VAULT}/02.Zattelkasten/001_Inbox/`
- **파일 형식**: Markdown (`.md`)
- 파일명은 영상 제목과 타임스탬프를 기반으로 자동 생성됩니다

### 지원 형식

- 전체 YouTube URL: `https://www.youtube.com/watch?v=VIDEO_ID`
- 단축 URL: `https://youtu.be/VIDEO_ID`
- 타임스탬프 포함 URL: `https://www.youtube.com/watch?v=VIDEO_ID&t=123s`

### 자막 언어 우선순위

1. 한국어 (ko) - 우선
2. 영어 (en) - 대체
3. 기타 사용 가능한 언어

### 주의사항

- YouTube 영상에 자막이 없으면 실행이 실패할 수 있습니다
- 백그라운드에서 실행되므로 완료까지 시간이 걸릴 수 있습니다
- `env.config`의 `OBSIDIAN_VAULT` 경로가 올바르게 설정되어 있어야 합니다

### 관련 파일

- `env.config`: Obsidian 볼트 경로 설정
- `.codex/bin/summarize-youtube`: Codex 실행 엔트리포인트
- `.codex/bin/youtube-progress`: Codex 진행 상태 확인
- `.codex/skills/obsidian-youtube-summarize/scripts/get_youtube_transcript.py`: YouTube 자막 추출 스크립트
- `.codex/skills/obsidian-youtube-summarize/scripts/summarize_youtube.py`: 요약/저장 워커
- `DIRECTORY_RULES.md`: 디렉터리 접근 규칙

## Article 요약 서비스

### 개요
기술 문서 URL 본문을 추출하고 번역/요약하여 Obsidian 노트로 저장하는 서비스입니다.

### 사용 방법

Codex에서 실행:

```bash
# 백그라운드 실행 (기본)
./.codex/bin/summarize-article kr "https://example.com/article"

# 동기 실행 (완료까지 대기)
./.codex/bin/summarize-article --sync en "https://example.com/article"

# 진행 상태 확인
./.codex/bin/article-progress
```

첫 번째 인자로 언어 옵션(`kr` 또는 `en`)을 받을 수 있으며, 생략 시 `kr`로 처리됩니다.

### 동작 방식

1. URL에서 title/author/content/images를 추출합니다.
2. 내용을 번역/요약해 Obsidian 문서를 생성합니다.
3. 문서는 `ARTICLE_DIR`, 이미지는 `ATTACHMENT_DIR`에 저장합니다.

### 출력 위치

- **문서 경로**: `{OBSIDIAN_VAULT}{ARTICLE_DIR}/`
- **첨부 경로**: `{OBSIDIAN_VAULT}{ATTACHMENT_DIR}/`
- **파일 형식**: Markdown (`.md`)
- 파일명은 `YYYY-MM-DD 제목 (codex).md` 형식입니다.

### 관련 파일

- `.codex/bin/summarize-article`: Codex article 실행 엔트리포인트
- `.codex/bin/article-progress`: Codex article 진행 상태 확인
- `.codex/skills/obsidian-article-summarize/scripts/extract_article.py`: URL 콘텐츠 추출 스크립트
- `.codex/skills/obsidian-article-summarize/scripts/summarize_article.py`: article 요약/저장 워커

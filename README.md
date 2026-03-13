참고 : https://github.com/msbaek/dotfiles

# My Daily Assistant

개인 일상 업무를 자동화하는 스크립트 모음. URL 요약, YouTube 정리, 노트 태깅 등 반복적인 작업을 줄이고 결과를 Obsidian 볼트에 저장합니다.

---

## AI 코딩 툴 구조

이 프로젝트는 **Claude Code**와 **Codex** 두 AI 툴을 함께 사용합니다. 각 툴은 독립적인 디렉터리를 소유하며, 서로의 영역을 침범하지 않습니다.

| 툴 | 전용 디렉터리 | 역할 |
|----|--------------|------|
| **Claude Code** | `.claude/` | 슬래시 커맨드, 인터랙티브 워크플로우 |
| **Codex** | `.codex/` | 백그라운드 스크립트, 자동화 파이프라인 |

두 툴 모두 루트 파일(`CLAUDE.md`, `AGENTS.md`, `env.config` 등)은 읽고 수정할 수 있습니다.

---

## 디렉터리 규칙 (DIRECTORY_RULES.md)

**절대 규칙** — 위반 시 즉시 수정 필요:

- Claude Code는 `.codex/` 디렉터리를 **수정 불가** (읽기만 허용)
- Codex는 `.claude/` 디렉터리를 **수정 불가** (읽기만 허용)
- 루트 레벨 파일은 양쪽 모두 수정 가능

자세한 내용은 [`DIRECTORY_RULES.md`](./DIRECTORY_RULES.md) 참조.

---

## 프로젝트 구조

```
my-daily-assistant/
├── .claude/
│   ├── commands/obsidian/      # Claude Code 슬래시 커맨드
│   ├── skills/                 # Claude Code 자동 적용 스킬
│   └── article-progress/       # Claude Code 작업 진행 상태
├── .codex/
│   ├── bin/                    # Codex 실행 래퍼
│   ├── skills/                 # Codex 스킬 및 Python 스크립트
│   └── article-progress/       # Codex 작업 진행 상태
├── env.config                  # 경로 설정 (Obsidian 볼트 등)
├── required_libs.md            # 필요 외부 라이브러리 목록
├── my-daily-service-commands.md # 서비스별 실행 커맨드 가이드
├── CLAUDE.md                   # Claude Code 지침
├── AGENTS.md                   # Codex 지침
└── DIRECTORY_RULES.md          # 디렉터리 접근 규칙
```

---

## 설정 (env.config)

프로젝트 루트의 `env.config`에 환경 경로를 설정합니다:

```bash
OBSIDIAN_VAULT=/path/to/your/obsidian/vault/
YOUTUBE_DIR=/02.Zattelkasten/001_Inbox
```

파일시스템이나 외부 서비스와 상호작용하는 모든 스크립트는 이 파일을 먼저 읽습니다.

---

## 필요 라이브러리 (required_libs.md)

```bash
pip3 install youtube-transcript-api yt-dlp
```

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `youtube-transcript-api` | >= 1.2.4 | YouTube 자막 추출 |
| `yt-dlp` | >= 2026.3.3 | 영상 메타데이터(제목, 채널명) 추출 |

macOS 시스템 Python 사용 시 `--break-system-packages` 플래그가 필요할 수 있습니다.

---

## 서비스 커맨드 (my-daily-service-commands.md)

각 기능의 실행 방법을 정리한 문서입니다. Claude Code와 Codex 각각의 실행 방식이 기술되어 있습니다.

### 현재 구현된 기능

#### YouTube 요약

YouTube 영상의 자막을 추출·번역하여 Obsidian 노트로 저장합니다.

**Claude Code:**
```
/obsidian:summarize_youtube
```

**Codex:**
```bash
./.codex/bin/summarize-youtube kr "https://www.youtube.com/watch?v=VIDEO_ID"
./.codex/bin/youtube-progress   # 진행 상태 확인
```

출력 위치: `{OBSIDIAN_VAULT}/02.Zattelkasten/001_Inbox/`

---

#### 기술 문서 요약 (Article Summarize)

기술 문서 URL 또는 텍스트를 번역/정리하여 Obsidian 노트로 저장합니다.

**Claude Code:**
```
/obsidian:summarize_article https://example.com/post
/obsidian:summarize_article # 제목\n\n본문 텍스트...
```

- URL(`http://`, `https://`로 시작)과 **텍스트 직접 입력** 두 가지 모드 지원
- 텍스트 모드: 200자 미만이면 경고 출력 후 계속 처리
- 직접 호출 시 백그라운드 실행, subagent 내부 호출 시 동기 실행

**Codex:**
```bash
./.codex/bin/summarize-article kr "https://example.com/post"
./.codex/bin/summarize-article kr "# 제목\n\n본문..."
./.codex/bin/article-progress   # 진행 상태 확인
```

출력 위치: `{OBSIDIAN_VAULT}/{ARTICLE_DIR}/`

---

#### Daily Work Logger

특정 날짜의 작업 내역을 정리해서 Daily Note를 업데이트하고, 해당 날짜의 `Tomorrow` 항목을 다음 날짜 `Today`로 이월합니다.

**Claude Code:**

`daily-work-logger` skill이 자동 적용됩니다. 대화에서 자연어로 요청합니다.

```text
어제 작업 정리해줘
daily-work-logger 2026-03-12
```

서브 에이전트 기반 병렬 처리(5개 동시 실행):
- **SubAgent 1**: Vault 파일 분석 (수정된 .md 파일 추출)
- **SubAgent 2**: Claude 세션 분석 (`~/.claude/projects/`)
- **SubAgent 3**: 미팅 노트 분석
- **SubAgent 4**: 학습 내용 추출 (TIL)
- **SubAgent 5**: Codex 세션 분석 (`~/.codex/sessions/`)

**Codex:**
Codex 대화에서 skill 이름으로 실행합니다.

```text
daily-work-logger
daily-work-logger 2026-03-12
```

공통 동작:
- 인수가 없으면 어제 날짜를 `TARGET_DATE`로 사용합니다.
- `{TARGET_DATE}.md` Daily Note에 작업 요약을 반영합니다.
- `## Company TODO > ### Tomorrow`, `## Private TODO > ### Tomorrow` 항목을 `{NEXT_DATE}` Daily Note의 `### Today`로 이월합니다.

---

## Claude Code Skills (`.claude/skills/`)

대화 중 자동으로 트리거되는 skill 모음입니다. 별도 명령 없이 자연어 요청으로 실행됩니다.

| Skill | 트리거 키워드 | 설명 |
|-------|------------|------|
| `daily-work-logger` | "어제 작업 정리해줘", "daily log", "업무 내역 정리" | 어제 작업 내역을 5개 서브 에이전트로 병렬 분석하여 Daily Note 반영 |
| `learning-tracker` | "학습 정리", "TIL", "오늘 배운 것", "learning" | 세션에서 새 기술/개념 학습 내용을 추출하여 TIL 문서 생성 |
| `weekly-claude-analytics` | "주간 분석", "Claude 사용 통계", "weekly analytics" | 주간 Claude Code 세션 로그를 분석하여 프로젝트별 시간 분포 리포트 생성 |
| `weekly-newsletter` | "뉴스레터 만들어줘", "이번 주 글 정리해줘", "weekly digest" | 이번 주(토~금) Vault 글들을 모아 외부 공유용 뉴스레터 생성 |
| `obsidian-vault` | Obsidian vault 관련 작업 | LSP 기반 효율적인 검색, 백링크 탐색, 태그 관리 |

### Skill 연계 구조

```
daily-work-logger
  └── SubAgent 4 (Learning Extractor) → learning-tracker 로직 활용

weekly-claude-analytics
  └── Claude 세션 로그 분석 → 프로젝트별 통계

weekly-newsletter
  └── Vault 파일 분석 → 외부 공유 뉴스레터
```

---

## 기여 / 확장

새 기능(스크립트)을 추가할 때:

- Claude Code용 커맨드 → `.claude/commands/<category>/`
- Claude Code용 skill → `.claude/skills/<skill-name>/SKILL.md`
- Codex용 스크립트 → `.codex/skills/<skill-name>/scripts/`
- 공통 설정 변경 → 루트 파일(`env.config` 등)
- 실행 가이드 → `my-daily-service-commands.md`에 섹션 추가
- 외부 라이브러리 추가 시 → `required_libs.md` 업데이트

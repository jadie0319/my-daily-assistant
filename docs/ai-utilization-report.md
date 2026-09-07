# AI 활용 보고서: My Daily Assistant

**작성일**: 2026-04-17  
**작성자**: Jadie  
**프로젝트**: my-daily-assistant  
**대상 독자**: 개발팀장, 임원

---

## 1. 프로젝트 개요 및 개발 배경

### 1.1 프로젝트 소개

`my-daily-assistant`는 개인 일상 업무 반복 작업을 AI 기반으로 자동화하는 스크립트 및 스킬 모음입니다. YouTube 영상 정리, 기술 문서 번역 요약, Daily Note 작성, 주간 뉴스레터 생성, Confluence 게시 등 매일 수작업으로 반복하던 업무를 Claude Code와 Codex 양쪽에서 처리할 수 있도록 구성했습니다.

모든 출력물은 **Obsidian 볼트**에 마크다운 노트로 저장되며, 사내 Confluence 위키와도 직접 연동됩니다.

### 1.2 개발 배경

| 문제 상황 | 해결 방향 |
|-----------|-----------|
| YouTube 기술 영상 정리에 매번 30분 이상 소요 | 자막 추출 + AI 번역·요약 자동화 |
| 기술 아티클 읽고 정리하는 작업의 반복 | URL/PDF → Obsidian 노트 자동 변환 |
| Daily Note에 하루 작업 내역 수동 기록 | 멀티 에이전트 병렬 분석으로 자동 반영 |
| 주간 성과를 외부 공유용으로 재가공하는 부담 | 뉴스레터 자동 생성 |
| Obsidian 노트를 Confluence에 수동으로 복사·붙여넣기 | Claude는 Playwright, Codex는 Confluence API 기반 자동 게시 |

### 1.3 핵심 철학

- **컨텍스트 효율**: 메인 에이전트 컨텍스트를 최소화하고, 서브 에이전트를 병렬 실행하여 처리 속도와 품질 확보
- **Obsidian 중심**: 모든 결과물은 Obsidian 볼트 내 마크다운으로 통합 관리
- **멀티 AI 협업**: Claude Code와 Codex를 병행 운용하되, 런타임 위임 없이 각자 독립 구현 유지
- **디렉터리 분리**: `.claude`와 `.codex`를 분리하고 서로의 런타임 구현에 의존하지 않음

---

## 2. 개발 과정

### 2.1 주요 마일스톤

| 커밋 | 내용 |
|------|------|
| `add rule` | 코딩 규칙 및 기본 프로젝트 구조 설정 |
| `add summarize article` | 기술 문서 URL 요약 기능 최초 구현 |
| `add weekly-newsletters, update README` | 주간 뉴스레터 자동 생성 기능 추가 |
| `add summarize pdf` | PDF 파일 요약 지원 추가 (PyMuPDF 연동) |
| `add handling image` | PDF 내 이미지 추출 및 노트 임베드 처리 |
| `apply changes from Claude to Codex` | Claude Code 스킬을 Codex로 이식하여 백그라운드 자동화 확장 |
| `add codex analyzer, daily-work-logger` | 멀티 에이전트 기반 Daily Work Logger 구현 |
| `fix skills by claude` | 스킬 구조 안정화 및 버그 수정 |
| `add obsidian-document-writer` | Playwright MCP로 Confluence 자동 게시 기능 추가 |
| `commands -> skills` | 슬래시 커맨드 체계에서 스킬(Skill) 기반 구조로 전환 |
| `2026-04-17 Codex native clone` | learning-tracker, weekly-codex-analytics, obsidian-document-writer, obsidian-vault를 Codex 전용으로 복제 구현 |

### 2.2 주요 기술적 선택

#### AI 툴 이중화 구조

두 AI 툴을 역할에 따라 분리하여 운용합니다:

- **Claude Code** (`.claude/`): 인터랙티브 대화, 기존 Playwright 기반 워크플로우
- **Codex** (`.codex/`): 스크립트 실행, 배치 처리, Codex 전용 skill/wrapper 기반 자동화

이 구조는 디렉터리 소유권 규칙(`DIRECTORY_RULES.md`)으로 강제하여, 두 툴이 서로의 설정을 수정하지 않도록 격리합니다. 최근에는 Claude 기능을 Codex에서 직접 수행할 수 있도록 `.codex` 아래에 동일 기능을 별도 구현하는 방향으로 정리했습니다.

#### 스킬(Skill) 기반 아키텍처로의 전환

초기에는 슬래시 커맨드(`/commands/`) 방식을 사용했으나, 자연어 키워드만으로도 자동 트리거되는 **스킬(Skill)** 체계로 전환했습니다. 이를 통해 사용자는 명령어를 기억하지 않고 자연어로 작업을 요청할 수 있습니다.

#### 독립 복제 방식

Codex에서 Claude 기능을 사용할 때 `.claude` 스크립트나 프롬프트를 호출하는 위임 방식은 사용하지 않습니다. 대신 Claude 기능 명세를 참고해 `.codex/skills/`와 `.codex/bin/` 아래에 동일 목적의 구현을 별도로 유지합니다.

#### 서브 에이전트 병렬 처리

`daily-work-logger`와 `weekly-newsletter`에서 메인 에이전트가 직접 모든 파일을 분석하는 대신, 분야별 서브 에이전트를 최대 5개까지 병렬 실행하여 분석합니다. 이는 대용량 Vault 처리 시 메인 컨텍스트 한계를 극복하기 위한 설계입니다.

---

## 3. 핵심 기능 목록

| 기능 | 분류 | 트리거 방식 | 출력 |
|------|------|------------|------|
| YouTube 영상 요약 | 콘텐츠 소화 | `summarize-youtube`, `obsidian-youtube-summarize`, 또는 자연어 | Python 스크립트(`summarize_youtube.py`, `get_youtube_transcript.py`) 기반으로 Obsidian 노트 생성 |
| 기술 문서 요약 (URL/PDF/텍스트) | 콘텐츠 소화 | `summarize-article`, `obsidian-article-summarize`, 또는 자연어 | Obsidian 노트 (`YYYY-MM-DD 제목 (codex).md`) |
| Daily Work Logger | 업무 자동화 | "어제 작업 정리해줘", "daily log" | Daily Note 업데이트 |
| Learning Tracker (TIL) | 학습 관리 | "학습 정리", "TIL", "오늘 배운 것" | Daily Note 학습 섹션 추가 |
| Weekly Newsletter | 지식 공유 | "뉴스레터 만들어줘", "weekly digest" | 뉴스레터 마크다운 (`YYYY-WNN-newsletter.md`) |
| Weekly Codex Analytics | 생산성 분석 | "주간 분석", "Codex 사용 통계" | 분석 리포트 (`analytics/codex-weekly/`) |
| Confluence 자동 게시 | 문서 배포 | `obsidian-document-writer <파일>` 또는 자연어 | Confluence 페이지 생성 |
| Obsidian Vault 탐색 | 지식 관리 | 볼트 관련 작업 요청 | `rg` 기반 검색·태그·백링크 결과 |

---

## 4. 주요 스킬 구조

### 4.1 스킬 목록 및 역할

아래 구조에서 `.claude/skills/`는 Claude Code용 기존 구현이고, `.codex/skills/`는 동일한 목적의 기능을 Codex에서 직접 수행할 수 있도록 별도로 복제한 독립 구현입니다.

```text
.codex/skills/
├── daily-work-logger/            # 어제 작업 자동 분석 및 Daily Note 반영
├── learning-tracker/             # Codex 세션 로그 기반 TIL 추출
├── obsidian-article-summarize/   # URL/PDF/텍스트 → Obsidian 노트
├── obsidian-document-writer/     # Confluence REST API 게시
├── obsidian-vault/               # Vault 검색 및 태그/백링크 작업 가이드
├── obsidian-youtube-summarize/   # YouTube URL → Obsidian 노트
├── weekly-codex-analytics/       # 주간 Codex 사용 통계 분석
└── weekly-newsletter/            # 주간 외부 공유용 뉴스레터 생성
```

```text
.claude/skills/
├── daily-work-logger/            # 어제 작업 자동 분석 및 Daily Note 반영
├── learning-tracker/             # Claude 세션 로그 기반 TIL 추출
├── obsidian-document-writer/     # Playwright MCP 기반 Confluence 게시
├── obsidian-summarize-article/   # URL/PDF/텍스트 → Obsidian 노트
├── obsidian-summarize-youtube/   # YouTube URL → Obsidian 노트
├── obsidian-vault/               # LSP 기반 Vault 검색 및 탐색
├── weekly-claude-analytics/      # 주간 Claude 사용 통계 분석
└── weekly-newsletter/            # 주간 외부 공유용 뉴스레터 생성
```

```text
.codex/bin/
├── summarize-youtube
├── summarize-article
├── learning-tracker
├── weekly-codex-analytics
├── obsidian-document-writer
└── weekly-newsletter
```

### 4.2 Daily Work Logger 스킬 아키텍처

매일 아침 어제 작업 내역을 자동으로 Daily Note에 반영하는 핵심 스킬입니다. 현재 Codex 쪽 구현은 Claude 세션 의존 없이 동작하도록 정리되어 있으며, 필요 시 Codex 세션과 Vault 파일을 중심으로 분석합니다.

```
Main Agent (Orchestrator)
  ├── Vault 파일 분석 (어제 수정된 .md 파일 목록 추출)
  ├── 미팅 노트 분석 (YYYY-MM-DD-*.md 패턴)
  ├── Codex 세션 분석 (~/.codex/sessions/)
  ├── 학습 내용 추출 → learning-tracker 활용
  └── Tomorrow 항목 이월
                    ↓
          Daily Note에 통합 반영
```

**Tomorrow 이월 기능**: 오늘 Daily Note의 `### Tomorrow` 항목을 다음 날 Daily Note의 `### Today`로 자동 이월합니다.

### 4.3 문서 요약 스킬 처리 흐름

```
입력 판별
  ├── http:// 또는 https:// → URL 모드 (추출 스크립트로 본문 수집)
  ├── .pdf 또는 file://    → PDF 모드 (`pdfplumber`로 텍스트 추출)
  └── 그 외                → 텍스트 모드 (직접 입력 처리)
                ↓
  실행 모드 판단
  ├── 직접 호출 → 백그라운드 모드 (Progress 파일 생성 후 비동기 처리)
  └── SubAgent 내 호출 → 동기 모드
                ↓
  AI 번역·요약 처리
                ↓
  YAML frontmatter 포함 Obsidian 노트 저장
  (파일명: YYYY-MM-DD {제목} (codex).md)
```

### 4.4 Confluence 자동 게시 흐름

```
입력 판별
  ├── .md 파일 경로 → 파일 모드
  │     ├── YAML frontmatter 제거
  │     ├── Obsidian 이미지 임베드 제거
  │     └── Obsidian 백링크 → 일반 텍스트 변환
  └── --title/--body → 직접 입력 모드
                ↓
  마크다운 → Confluence storage HTML 변환
                ↓
  Confluence REST API 호출
                ↓
  부모 페이지 하위에 새 페이지 생성
                ↓
  생성된 페이지 URL 출력
```

### 4.5 스킬 연계 구조

```
daily-work-logger
  └── learning-tracker 와 결합하여 Daily Note 학습 섹션 강화

weekly-codex-analytics
  └── ~/.codex/sessions/ 세션 로그 분석 → 프로젝트별 통계

weekly-newsletter
  └── Daily Notes + 주간 문서 분석
      → 외부 공유 가능 기술·리더십 인사이트 추출 → 뉴스레터
```

---

## 5. AI 활용 방식 및 효과

### 5.1 활용 방식

#### 자연어 기반 인터페이스

사용자는 복잡한 명령어 없이 자연어만으로 기능을 실행합니다. 스킬 트리거 키워드를 대화 중에 감지하여 자동으로 해당 워크플로우가 시작됩니다.

| 자연어 입력 예시 | 자동 실행 스킬 |
|----------------|---------------|
| "어제 작업 정리해줘" | daily-work-logger |
| "이 PDF 요약해줘" | obsidian-article-summarize |
| "유튜브 영상 정리해줘" | obsidian-youtube-summarize |
| "오늘 배운 것 정리해줘" | learning-tracker |
| "뉴스레터 만들어줘" | weekly-newsletter |
| "이번 주 Codex 사용 통계 보여줘" | weekly-codex-analytics |
| "이 노트 컨플루언스에 올려줘" | obsidian-document-writer |

#### API 및 스크립트 기반 실행

Codex 쪽은 브라우저 자동화 위임 없이 Python 스크립트와 `codex exec`를 조합해 기능을 수행합니다. Confluence 게시도 Codex에서는 REST API 호출 방식으로 처리합니다.

#### 멀티 에이전트 병렬 처리

단일 LLM 호출로 처리하기 어려운 대용량 Vault 분석을 서브 에이전트 병렬 실행으로 처리합니다. 이를 통해 메인 컨텍스트 소모를 최소화하면서 분석 깊이를 유지합니다.

#### 이중 AI 엔진 운용

- **Claude Code**: 대화형, 실시간 피드백이 필요한 작업
- **Codex**: 장시간 실행, 백그라운드 배치 처리가 필요한 작업

동일 목적의 기능을 양쪽 엔진에서 실행할 수 있도록 설계하되, 실제 구현은 각 엔진 디렉터리 안에 독립적으로 유지합니다.

### 5.2 기대 효과 및 생산성 향상

| 작업 | 도입 전 소요 시간 | 도입 후 소요 시간 | 절감률 |
|------|-----------------|-----------------|--------|
| YouTube 영상 1편 정리 | ~30분 | ~3분 (명령 후 대기) | ~90% |
| 기술 문서 URL 번역·요약 | ~20분 | ~2분 | ~90% |
| Daily Note 작업 내역 정리 | ~15분 | ~1분 | ~93% |
| 주간 뉴스레터 작성 | ~60분 | ~5분 | ~92% |
| Confluence 게시 (복사·붙여넣기) | ~10분 | ~1분 | ~90% |

### 5.3 기술 스택 요약

| 영역 | 기술 |
|------|------|
| AI 엔진 | Claude Code, Codex CLI |
| 자동화 방식 | Skill + wrapper + Python script |
| YouTube 처리 | `youtube-transcript-api`, `yt-dlp`, `summarize_youtube.py`, `get_youtube_transcript.py` |
| PDF 처리 | `pdfplumber` |
| 지식 관리 | Obsidian (마크다운 볼트) |
| 사내 위키 | Confluence REST API |
| 환경 설정 | `env.config` (단일 설정 파일) |
| 실행 환경 | macOS, Python 3, Zsh |

### 5.4 운용상 특이사항

- **보안**: Confluence 인증 정보는 `env.config`에 저장되며, `.gitignore`로 추적 제외됨
- **확장성**: 새 기능 추가 시 `.codex/skills/<skill-name>/`와 `.codex/bin/` 기준으로 독립 구현 가능
- **이식성**: Claude와 Codex가 같은 목적의 기능을 가지되, 서로의 런타임 구현에 의존하지 않음
- **관찰 가능성**: `.codex/article-progress/`, `.codex/newsletter-progress/`에 JSON 진행 파일을 생성하여 상태 추적 가능

---

*본 문서는 `my-daily-assistant` 프로젝트의 AI 활용 현황을 정리한 내부 보고서입니다.*

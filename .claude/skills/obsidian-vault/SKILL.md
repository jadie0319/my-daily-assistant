---
name: obsidian-vault
description: 
  Obsidian vault 작업 시 LSP 기반 효율적인 검색, 백링크 탐색, 태그 관리를 제공하는 스킬
---

# obsidian-vault

> Obsidian vault 작업 시 LSP 기반 효율적인 검색, 백링크 탐색, 태그 관리를 제공하는 스킬

## 만든 배경

CLAUDE.md에 포함되어 있던 Obsidian vault 작업 가이드(경로, 태그 체계)를 독립 스킬로 추출하여 중앙 집중식 관리 및 재사용성을 높이기 위해 2026-01-06 생성. Obsidian, 마크다운, 노트 정리, Zettelkasten 관련 키워드 사용 시 자동 적용됨.

## 사용법

### 호출 방법

```bash
/obsidian-vault
```

또는 Obsidian, vault, 마크다운, 태그, 백링크, wiki-link, PKM 등의 키워드를 포함한 질문 시 자동 적용.

### 예시

```
# LSP 기반 백링크 검색
"TDD 노트를 참조하는 모든 노트 찾아줘"

# 태그 검색
"#project/active 태그가 있는 노트들 목록 보여줘"

# 깨진 링크 확인
"vault에서 깨진 링크가 있는 노트 확인해줘"
```

## 주요 기능

### 1. markdown-oxide LSP 우선 활용
- **Go to Definition**: `[[링크]]` → 해당 파일 이동
- **Find References**: 백링크 검색 (특정 노트를 참조하는 모든 노트)
- **Tag Search**: `#태그` 위치 검색
- **Diagnostics**: 깨진 링크/존재하지 않는 노트 감지
- **Completion**: 링크, 태그, 프로퍼티 자동완성

검색 우선순위: `markdown-oxide LSP` →  `ripgrep` (단순 텍스트)

### 2. 태그·origin·related (2026-09-07 규칙)
- 태그는 vault의 **`95.Vault/태그 어휘.md`** 에 있는 값만 쓴다(최상위 `ai/ dev/ invest/ self/ productivity/ business/ source/`, 노트당 3~5개). 옛 `#topic/…`, `#type/…`, `#status/…` 체계는 폐기됨. 새 태그가 필요하면 어휘표에 먼저 추가한다.
- `origin: mine | library` — 내가 쓴 것 / 가져온 것·AI 요약. 인용할 때 어느 쪽인지 밝힌다.
- `related:` — `"[[제목]]"` 목록. `inbox-link` 스킬(vault의 `.claude/skills/inbox-link/`)이 채운다. 검색은 이 필드와 본문 `## 관련 노트`를 먼저 따라간다.
- 전체 규칙: `/Users/jdragon/my-daily-assistant/obsidian-note-rules.md`, vault의 `CLAUDE.md`.

### 3. Zettelkasten 폴더 구조

| 폴더 | 용도 | 스킬 작업 권한 |
| --- | --- | --- |
| `$INBOX_DIR` (`/02.Zettelkasten/001_Inbox`) | 미검토 요약 캡처 (`origin: library`) | 읽기/쓰기 |
| `$LIBRARY_DIR` (`/02.Zettelkasten/004_Library`) | 검토 끝난 외부 자료 원문 | 읽기만 (승격은 사용자) |
| `$NOTES_DIR` (`/02.Zettelkasten/002_Notes`) | 사용자가 직접 쓴 영구 노트 (`origin: mine`) | 읽기만 |
| `$MOC_DIR` (`/02.Zettelkasten/003_MOC`) | 개념 지도 | 읽기만 |
| `$ATTACHMENT_DIR` (`/99.Attachments`) | 이미지 전용 | 쓰기(이미지만) |

흐름: Inbox → (검토) Library → (내 말로 다시 쓰기) Notes → MOC.

### 3-1. 검색 도구 순서
1. **Obsidian CLI** (`obsidian search query=… path=…`, `read file=…`, `links`, `backlinks`, `tag name=…`) — Obsidian 실행 중일 때. 입구를 잡고 위키링크를 한두 홉 따라간다.
2. markdown-oxide LSP (백링크·태그·진단)
3. ripgrep (단순 텍스트)

### 4. 토큰 최적화 전략

**작업 원칙**
1. 한 번에 10개 이하 파일 처리
2. `archive`, `.obsidian` 폴더 무시
3. MOC 노트 먼저 읽고 관련 노트만 선택적 로드
4. 20회 반복 후 `/compact` 또는 `/clear`

**효율적인 요청 패턴**
```
# ❌ 비효율적
"vault의 모든 파일을 분석해줘"

# ✅ 효율적
"002-Notes 에서 'kubernetes' 태그가 있는 노트 목록만 보여줘"
```

**컨텍스트 관리**

| 명령어 | 용도 | 시점 |
|--------|------|------|
| `/compact` | 히스토리 압축 | 70% 사용 시 |
| `/clear` | 초기화 | 새 작업 시작 |
| `/cost` | 토큰 확인 | 수시 |

**제외 대상**: `.obsidian/`, `archive/`, `.canvas`, 이미지 파일

## 의존성

| 도구/서비스             | 용도                           |
| ------------------ | ---------------------------- |
| markdown-oxide LSP | 백링크, 태그, 링크 검색 및 진단          |
| ripgrep            | 단순 텍스트 매칭 폴백                 |
| `$OBSIDIAN_VAULT`  | env.config에서 정의된 vault 루트 경로 |
| `$DAILY_NOTE_DIR`  | env.config에서 정의된 daily notes 디렉토리 |
| `$INBOX_DIR`       | env.config에서 정의된 수집함 경로      |
| `$NOTES_DIR`       | env.config에서 정의된 내 노트 경로 (읽기만) |
| `$LIBRARY_DIR`, `$MOC_DIR` | env.config에서 정의된 Library·MOC 경로 (읽기만) |

> **주의**: markdown-oxide LSP가 설정되어 있지 않으면 LSP 기능이 동작하지 않습니다.
> 설치 확인: Claude Code에서 LSP 도구 사용 시 오류가 없는지 확인하세요.

## 참고

- 검색 도구 선택: LSP (백링크/태그) → ripgrep (키워드)

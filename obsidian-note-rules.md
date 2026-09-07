# Obsidian 노트 생성 규칙 (my-daily-assistant 공용)

> Claude 스킬(`.claude/skills/obsidian-*`)과 Codex 스킬(`.codex/skills/obsidian-*`)이 vault에 노트를 만들 때 **공통으로 따르는 규칙**. vault 쪽 기준 문서는 `{OBSIDIAN_VAULT}/CLAUDE.md`, `{OBSIDIAN_VAULT}/파라, 제텔카스텐 개요 및 정리 v2.md`. 이 파일이 그 문서와 어긋나면 vault 문서가 우선이다. (2026-09-07 작성)

## 1. 경로 (`env.config`)

| 키 | 용도 |
|---|---|
| `OBSIDIAN_VAULT` | vault 루트 (끝에 `/` 포함) |
| `INBOX_DIR`, `YOUTUBE_DIR`, `ARTICLE_DIR` | 새 요약 노트가 들어가는 곳. 전부 `/02.Zettelkasten/001_Inbox` |
| `NOTES_DIR` | `/02.Zettelkasten/002_Notes` — **사용자가 직접 쓴 노트만**. 스킬이 쓰지 않는다 |
| `LIBRARY_DIR` | `/02.Zettelkasten/004_Library` — 검토 끝난 외부 자료. 스킬이 쓰지 않는다(승격은 사용자) |
| `MOC_DIR` | `/02.Zettelkasten/003_MOC` — 스킬이 쓰지 않는다 |
| `ATTACHMENT_DIR` | `/99.Attachments` — 이미지 전용. **`.md`를 여기 두지 않는다** |
| `DAILY_NOTE_DIR` | `/04.Daily` |

스킬은 **Inbox와 Attachments에만 쓴다.** 그 외 폴더는 읽기만.

## 2. 프론트매터 (Inbox 요약 노트)

필드 순서와 형식은 vault 템플릿 `90.Templates/Inbox Summary.md`와 같다.

```yaml
---
id: "<원제>"                    # 콜론·따옴표가 있으면 반드시 큰따옴표로 감싼다
aliases: <한국어 한 줄 제목>
tags:
  - <어휘표 태그 1>
  - <어휘표 태그 2>
  - <어휘표 태그 3>
  - source/video                # 또는 source/article
author: <채널·저자, 소문자, 공백은 ->
tool: claude                    # 또는 codex
created: YYYY-MM-DD HH:mm
related: []                     # 비워 둔다. 저장 후 inbox-link가 채운다
source: <URL>
origin: library                 # 가져온 것·AI 요약은 항상 library
---
```

- `origin: library`는 **필수**. 사용자가 직접 쓴 것(`mine`)과 구분하는 표식이다.
- `status`는 넣지 않는다(요약 노트 스키마에 없음).
- `related`는 빈 배열로 둔다. 링크는 3절의 절차가 채운다.

## 3. 태그: 어휘표에서만 고른다

- 허용 태그는 **`{OBSIDIAN_VAULT}/95.Vault/태그 어휘.md`** 의 표에 있는 값 전부다. 노트를 만들기 전에 이 파일을 읽는다.
- 노트당 **3~5개** + `source/*` 하나. 최상위는 `ai/ dev/ invest/ self/ productivity/ business/ source/` 7개뿐이다.
- 맞는 태그가 없으면 **새 태그를 만들지 말고** 가장 가까운 상위 태그를 쓴다. 정말 새 태그가 필요하면 노트 본문 끝에 `<!-- 태그 제안: xxx -->` 주석으로 남겨 사용자가 어휘표에 추가하게 한다.
- 소문자, 영문, `/` 계층, 깊이 3 이하. 한글 태그·대문자·`development/` 같은 옛 뿌리는 쓰지 않는다.

## 4. 파일명

`YYYY-MM-DD <제목> (claude).md` / `... (codex).md`. 제목에서 다음을 정리한다.

| 문자 | 처리 | 이유 |
|---|---|---|
| `|` | ` - ` | 위키링크의 별칭 구분자 |
| `#`, `^` | 제거 | 위키링크의 헤딩·블록 앵커 |
| `/ \ : * ? " < >` | ` -` 또는 제거 | 파일 시스템·Obsidian 금지 문자 |
| 앞뒤 공백, 연속 공백 | 정리 | 끝 공백이 있으면 링크가 해석되지 않는다 |
| 길이 | 120자 이내로 자른다 (기존 노트 중 88자 제목이 있어 80은 너무 짧다) | |

## 5. 저장 후: 관련 노트 링크 제안

노트를 저장한 뒤 vault 루트에서 실행한다.

```bash
cd "$OBSIDIAN_VAULT" && python3 .claude/skills/inbox-link/link_inbox.py --dry-run "<노트 제목>"
```

- 출력되는 제안 표(점수·관련 노트·근거)를 **완료 보고에 그대로 포함**한다.
- **자동으로 `--apply` 하지 않는다.** 사용자가 표를 보고 `/inbox-link <제목>`으로 적용한다(GIGO 원칙).
- 백그라운드 모드라 사용자에게 물을 수 없으면 제안만 남기고 끝낸다.

## 5-1. 자동 검증 (hook) — 2026-09-07

`.claude/settings.json`의 PostToolUse hook이 **Inbox 아래 `.md`를 Write/Edit할 때마다** `scripts/check_obsidian_note.py --fix --no-rename`을 자동 실행한다. 태그가 어휘표 밖이면 상위 태그로, `origin`·`related`가 없으면 채운다. 모델이 규칙을 잊거나 이미지 삽입 단계에서 노트를 다시 써도 마지막 쓰기 뒤에 다시 검증된다. 파일명은 hook에서 바꾸지 않으므로(작업 중인 파일이 사라지면 안 된다) 파일명 위반은 스킬의 마지막 검증 단계에서 `--fix`로 처리한다. hook 출력 `[inbox-check] … RESULT: OK`가 완료 보고에 보이면 정상.

## 6. 하지 않는 것

- `002_Notes`, `004_Library`, `003_MOC`에 쓰기. 승격과 MOC는 사용자 몫.
- 기존 노트 본문 수정(자동 링크도 `related:` 프론트매터만 건드린다).
- `date created` / `date modified` / `publish` 키 사용.
- `(No Upload)` 폴더의 노트를 읽어 외부(요약 프롬프트 포함)로 보내기.

---
argument-hint: "[inbox/파일명.md | notes/파일명.md | 상대경로/파일명.md | 페이지 제목]"
description: "Playwright MCP로 사내 Confluence 위키에 새 페이지를 작성하고 게시. 로컬 .md 파일 경로를 인자로 주면 파일 내용을 자동으로 업로드"
color: blue
---

# Confluence Document Writer - $ARGUMENTS

Playwright MCP를 사용해 사내 Confluence 위키에 새 페이지를 작성합니다.

## Step 0: env.config 읽기

Read 도구로 `/Users/jdragon/my-daily-assistant/env.config`를 읽어 아래 값을 추출한다:

- `CONFLUENCE_URL` — Confluence 서버 주소
- `CONFLUENCE_SPACE_KEY` — Confluence 스페이스 키 (예: `~Jdragon`)
- `CONFLUENCE_PARENT_PAGE_ID` — 새 페이지가 생성될 부모 페이지 ID
- `CONFLUENCE_USERNAME` — Confluence 로그인 아이디
- `CONFLUENCE_PASSWORD` — Confluence 로그인 비밀번호
- `OBSIDIAN_VAULT` — Obsidian 볼트 루트 경로
- `INBOX_DIR` — 받은 편지함 디렉토리 (예: `/02.Zettelkasten/001_Inbox`)
- `NOTES_DIR` — 노트 디렉토리 (예: `/02.Zettelkasten/002_Notes`)

## Step 1: 제목 및 본문 수집

### 파일 모드 (`$ARGUMENTS`가 `.md`로 끝나는 경우)

**파일 경로 결정**: `$ARGUMENTS`의 프리픽스에 따라 실제 경로를 결정한다:

| 입력 | 실제 경로 |
|------|-----------|
| `inbox/파일명.md` | `{OBSIDIAN_VAULT}{INBOX_DIR}/파일명.md` |
| `notes/파일명.md` | `{OBSIDIAN_VAULT}{NOTES_DIR}/파일명.md` |
| 그 외 상대경로 | `{OBSIDIAN_VAULT}/{$ARGUMENTS}` |

Read 도구로 위에서 결정한 경로의 파일을 읽는다.
파일이 없으면 에러 메시지를 출력하고 중단한다.

**제목 추출**: 파일명에서 확장자 `.md`를 제거한다.
`YYYY-MM-DD ` 날짜 프리픽스 패턴(`\d{4}-\d{2}-\d{2} `)이 있으면 제거한다.
예: `2026-03-23 Feature Toggle.md` → `Feature Toggle`

**본문 추출**: 파일 내용에서 아래 항목을 제거/변환한다:
1. YAML frontmatter: 파일 최상단 `---` ~ `---` 블록 전체 제거
2. Obsidian 이미지 임베드 `![[...]]` → 완전 제거
3. Obsidian 백링크 `[[링크 텍스트]]` → `링크 텍스트` (괄호만 제거)
4. 단독 `#태그` 줄 (해시로 시작하는 태그 전용 줄) → 제거

### 인터랙티브 모드 (`$ARGUMENTS`가 비어 있거나 `.md`가 아닌 경우)

`$ARGUMENTS`가 있으면 페이지 제목으로 사용한다.
없으면 AskUserQuestion으로 제목을 요청한다.
AskUserQuestion으로 페이지 본문 내용을 수집한다.

## Step 2: Confluence 접속 및 로그인 확인

`mcp__playwright__browser_navigate`로 `{CONFLUENCE_URL}` 에 이동한다.

`mcp__playwright__browser_snapshot`으로 현재 페이지를 확인한다:
- snapshot에 `heading "로그인"` 또는 URL에 `login.action`이 포함되어 있으면 → **로그인 필요**
- 그 외 → **Step 3으로 바로 진행**

### 로그인이 필요한 경우

Step 0에서 읽은 `CONFLUENCE_USERNAME`과 `CONFLUENCE_PASSWORD`를 사용해 자동 로그인한다.

`mcp__playwright__browser_fill_form`으로 로그인 폼을 채운다:
```
username 필드: textbox "사용자 이름"
password 필드: textbox "비밀번호"
```

`mcp__playwright__browser_click`으로 로그인 버튼을 클릭한다.

`mcp__playwright__browser_snapshot`으로 로그인 성공 여부를 확인한다.
로그인 실패 시 에러 메시지를 사용자에게 알리고 중단한다.

> 세션은 `--user-data-dir`로 디스크에 저장되므로, 다음 실행부터는 이 단계가 스킵된다.

## Step 3: 새 페이지 생성 화면으로 이동

아래 URL로 이동한다:
```
{CONFLUENCE_URL}/pages/createpage.action?spaceKey={CONFLUENCE_SPACE_KEY}&fromPageId={CONFLUENCE_PARENT_PAGE_ID}&src=quick-create
```

`mcp__playwright__browser_snapshot`으로 에디터 로딩을 확인한다.
에디터가 아직 로딩 중이면 `mcp__playwright__browser_wait_for`로 TinyMCE 초기화를 기다린다.

## Step 4: 제목 입력

`mcp__playwright__browser_fill_form`으로 제목 필드에 수집한 제목을 입력한다:
- 필드 식별: snapshot에서 `textbox "페이지 제목"` 또는 `페이지 제목을 추가하세요` placeholder를 가진 textbox

## Step 5: 본문 입력

수집/추출한 본문 내용을 HTML로 변환한 뒤 `mcp__playwright__browser_evaluate`로 TinyMCE에 주입한다.

**마크다운 → HTML 변환 규칙:**
- `## 제목` → `<h2>제목</h2>` (h1~h6 동일하게)
- `**굵게**` → `<strong>굵게</strong>`
- `*기울임*` 또는 `_기울임_` → `<em>기울임</em>`
- `` `인라인 코드` `` → `<code>인라인 코드</code>`
- ```` ```언어\n코드\n``` ```` → `<pre><code>코드</code></pre>`
- `- 항목` / `* 항목` → `<ul><li>항목</li></ul>`
- `1. 항목` → `<ol><li>항목</li></ol>`
- 빈 줄로 구분된 단락 → `<p>...</p>`
- `[[링크]]` → 링크 텍스트만 (이미 Step 1에서 처리됨)

```javascript
tinymce.activeEditor.setContent(`{변환된_HTML_내용}`)
```

`mcp__playwright__browser_evaluate` 실행 후 `mcp__playwright__browser_snapshot`으로
에디터에 내용이 반영됐는지 확인한다.

## Step 6: 페이지 저장 (게시)

snapshot에서 "출판" 또는 "게시" 텍스트를 가진 button을 찾아 클릭한다.

## Step 7: 성공 확인

`mcp__playwright__browser_snapshot`으로 페이지 저장 결과를 확인한다:
- URL이 `viewpage.action`으로 변경되었으면 성공
- 에러 메시지가 보이면 사용자에게 에러 내용을 알린다

성공 시 생성된 페이지 URL을 사용자에게 알린다.

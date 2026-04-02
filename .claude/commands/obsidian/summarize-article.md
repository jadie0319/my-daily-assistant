---
argument-hint: "[url, 텍스트, 또는 PDF 파일 경로]"
description: "기술 문서 URL, 텍스트, 또는 로컬 PDF 파일 → 번역/정리 → env.config 의 ARTICLE_DIR 을 참고해서  obsidian 문서 생성"
color: yellow
---

# article summarize - $ARGUMENTS

기술 문서 URL, 텍스트, 또는 로컬 PDF 파일을 받아 **백그라운드**로 번역/정리하여 Obsidian 문서를 생성합니다.

## 입력 타입 판별

`$ARGUMENTS`를 순서대로 확인한다:

1. `http://` 또는 `https://`로 시작하면 → **URL 모드**
2. `.pdf`로 끝남 (대소문자 무관) 또는 `file://`로 시작하면 → **PDF 모드**
3. 그 외 → **텍스트 모드**

텍스트 모드에서 `$ARGUMENTS`가 200자 미만이면 경고를 출력한다:
```
⚠️  입력 텍스트가 200자 미만입니다. URL을 입력하려 했다면 'http://' 또는 'https://'로 시작해야 합니다.
```
경고 출력 후에도 처리는 계속 진행한다.

## 실행 모드 판단

**이 스킬이 직접 호출된 경우 (사용자가 메인 세션에서 `/obsidian:summarize-article URL 또는 텍스트` 실행):** → **백그라운드 모드**로 실행
**이 스킬이 subagent 내부에서 호출된 경우 (batch-summarize-urls 등):** → **동기 모드**로 실행

## 백그라운드 모드 (직접 호출 시)

### Step 0: env.config 읽기

**반드시 Read 도구로 `/Users/jdragon/my-daily-assistant/env.config` 파일을 읽은 뒤** `OBSIDIAN_VAULT`, `ARTICLE_DIR`, `ATTACHMENT_DIR` 값을 추출한다.

```shell
ENV_CONFIG="/Users/jdragon/my-daily-assistant/env.config"
OBSIDIAN_VAULT=$(grep '^OBSIDIAN_VAULT=' "$ENV_CONFIG" | cut -d'=' -f2-)
ARTICLE_DIR=$(grep '^ARTICLE_DIR=' "$ENV_CONFIG" | cut -d'=' -f2-)
ATTACHMENT_DIR=$(grep '^ATTACHMENT_DIR=' "$ENV_CONFIG" | cut -d'=' -f2-)

# 최종 저장 디렉토리
ARTICLE_OUTPUT_DIR="${OBSIDIAN_VAULT}${ARTICLE_DIR}"
ATTACHMENT_OUTPUT_DIR="${OBSIDIAN_VAULT}${ATTACHMENT_DIR}"
```

이후 모든 단계에서 위 변수들을 사용한다.

### Step 1: Progress 파일 생성

`.claude/article-progress/` 디렉토리에 진행 상황 파일을 생성합니다.

**URL 모드** 파일명: `YYYYMMDD-HHMMSS-{url-slug}.json`
```json
{
  "url": "$ARGUMENTS",
  "type": "article",
  "status": "processing",
  "started_at": "현재시간 ISO-8601",
  "completed_at": null,
  "output_file": null,
  "error": null
}
```

**텍스트 모드** 파일명: `YYYYMMDD-HHMMSS-text-{앞 30자 alphanumeric}.json`
```json
{
  "input": "text",
  "type": "article",
  "status": "processing",
  "started_at": "현재시간 ISO-8601",
  "completed_at": null,
  "output_file": null,
  "error": null
}
```

**PDF 모드** 파일명: `YYYYMMDD-HHMMSS-pdf-{파일명-stem-30자}.json`
```json
{
  "file": "$ARGUMENTS",
  "type": "article",
  "status": "processing",
  "started_at": "현재시간 ISO-8601",
  "completed_at": null,
  "output_file": null,
  "error": null
}
```

### Step 2: 백그라운드 subagent 시작

Task tool을 사용하여 백그라운드 subagent를 시작합니다:

- `subagent_type`: "general-purpose"
- `run_in_background`: true
- **URL 모드** `description`: "Summarize: {URL 도메인/경로 일부}"
- **텍스트 모드** `description`: "Summarize text: {텍스트 앞 30자}"
- **PDF 모드** `description`: "Summarize PDF: {파일명 without extension}"
- `prompt`: 아래 동기 모드 프로세스 전체를 포함하되, 다음을 추가:
  - progress 파일 경로를 전달
  - 작업 완료 후 progress 파일을 completed로 업데이트하도록 지시
  - 실패 시 progress 파일을 failed로 업데이트하도록 지시
  - **텍스트 모드인 경우**: `$ARGUMENTS` 전체 텍스트를 prompt에 포함하여 전달

### Step 3: 사용자에게 알림 후 즉시 반환

**URL 모드:**
```
백그라운드 작업 시작됨:
- URL: $ARGUMENTS
- Progress: .claude/article-progress/{파일명}.json
- 완료되면 자동으로 알려드립니다.
```

**텍스트 모드:**
```
백그라운드 작업 시작됨:
- 입력: 텍스트 ({글자수}자)
- Progress: .claude/article-progress/{파일명}.json
- 완료되면 자동으로 알려드립니다.
```

**PDF 모드:**
```
백그라운드 작업 시작됨:
- PDF: $ARGUMENTS
- Progress: .claude/article-progress/{파일명}.json
- 완료되면 자동으로 알려드립니다.
```

## 동기 모드 (subagent에서 호출 시 / 백그라운드 subagent 내부)

### Step 1: 콘텐츠 추출

**URL 모드**: `WebFetch` 도구로 URL에 접근하여 콘텐츠를 추출합니다.

- URL: `$ARGUMENTS`
- prompt: "이 기술 문서의 전체 내용을 추출하라. 제목, 작성자, 본문 전체(모든 섹션, 코드 예제 포함)를 빠짐없이 반환하라. 본문에 포함된 이미지 URL도 마크다운 이미지 문법(![alt](url))으로 모두 포함하라."
- 실패 시: 에러 보고 후 중단 (progress 파일을 `failed`로 업데이트)

WebFetch 결과에서 다음을 파악한다:
- **title**: 문서 제목
- **author**: 작성자 (없으면 빈 문자열)
- **content**: 본문 전체 (번역/요약에 사용)

본문이 200자 미만이면 로그인 wall 또는 접근 제한 가능성이 있으므로 사용자에게 안내한다.

**PDF 모드**: Read 도구로 PDF 파일을 직접 읽어 콘텐츠를 추출한다.

1. **파일 존재 확인**: Bash `test -f "$ARGUMENTS"` 로 파일 존재 여부 확인. 없으면 progress 파일을 `failed`로 업데이트하고 중단
2. **콘텐츠 추출 (청크 방식)**: Read 도구로 10페이지씩 반복 읽기
   - `pages: "1-10"` → `pages: "11-20"` → `pages: "21-30"` → ...
   - 빈 결과(내용 없음)가 나올 때까지 반복
   - 각 청크 결과를 순서대로 concat
3. **title**: 파일명에서 경로와 확장자 제거, `-`와 `_`를 공백으로 치환
4. **author**: 빈 문자열
5. **content**: 모든 청크를 합친 전체 텍스트
6. content가 100자 미만이면 빈 PDF 또는 이미지 전용 PDF로 판단 → progress 파일을 `failed`로 업데이트 후 중단

**텍스트 모드**: WebFetch를 스킵하고 다음을 설정한다.

- **title**: 텍스트에서 첫 번째 `#` 마크다운 헤딩을 추출. 없으면 첫 문장(최대 80자)을 title로 사용
- **author**: 빈 문자열
- **content**: `$ARGUMENTS` 전체 텍스트

### Step 2: 번역 및 요약

추출된 콘텐츠를 아래 규칙(`## 문서 번역 및 요약 규칙`)에 따라 정리하여 yaml frontmatter를 포함한 obsidian 파일로 저장합니다.

- 저장 경로: `$OBSIDIAN_VAULT/$ARTICLE_DIR/YYYY-MM-DD {문서제목}.md`
  - 날짜는 파일 생성 시점의 `date +%Y-%m-%d` 값 사용
  - 예: `2026-03-16 10 Essential Software Design Patterns.md`
- 디렉터리가 없으면 생성: `mkdir -p "$ARTICLE_OUTPUT_DIR"`
- hierarchical tagging 규칙: `~/.claude/commands/obsidian/add-tag.md` 준수

### Step 3: 이미지 처리

**텍스트 모드인 경우 이 단계를 완전히 스킵한다.**

**URL 모드**: WebFetch 결과에 이미지 URL이 포함된 경우, ATTACHMENTS 폴더에 저장하고 Obsidian 문서에 포함시킵니다.

- ATTACHMENTS 경로: `$OBSIDIAN_VAULT/$ATTACHMENT_DIR/`
- 이미지 URL이 없으면 이 단계를 건너뜀

#### 이미지 URL 추출

WebFetch 결과에서 `![alt](url)` 패턴으로 이미지 URL 목록을 수집한다.

#### 필터링 규칙

- URL 패턴 제외: `gravatar`, `avatar`, `favicon`, `icon`, `logo`, `badge`, `tracking`, `pixel`, `analytics`
- 허용 확장자: `png`, `jpg`, `jpeg`, `gif`, `webp`, `svg`, `avif`
- 다운로드 후 5KB 미만 파일 삭제 (SVG는 1KB 기준)
- 최대 20개 이미지 제한

#### 파일명 규칙

```
{YYYYMMDD}-{article-title-slug-30자}-{NN}.{ext}
```
- 날짜: 노트 파일명과 동일한 날짜
- slug: 제목 소문자화, 공백→하이픈, 비영숫자 제거, 30자 제한
- NN: 01부터 순차 번호

#### 다운로드

```bash
curl -sL --max-time 15 --max-filesize 10485760 \
  -o "$ATTACHMENT_OUTPUT_DIR/{filename}" "{image_url}"
```
- 경로에 공백 포함 시 반드시 따옴표 처리
- 실패 시 해당 이미지만 스킵 (전체 프로세스 중단 안 함)

#### 요약 문서에 임베딩

다운로드된 이미지가 0개면 이미지 임베딩을 스킵한다.

각 이미지의 내용과 요약 본문의 챕터(### 소제목)를 대조하여,
해당 이미지가 설명하는 내용과 가장 관련 깊은 챕터의 끝에 인라인으로 배치한다.

어느 챕터에도 명확히 매칭되지 않는 이미지는 문서 끝에 `## 참고 이미지` 섹션을 만들어 배치한다.
매칭되지 않는 이미지가 없으면 `## 참고 이미지` 섹션을 생략한다.

**PDF 모드**: `extract_pdf_images.py` 스크립트로 PDF에서 이미지를 추출한 뒤, 관련성 필터링을 거쳐 선별된 이미지만 Obsidian 문서에 포함시킨다.

#### PDF 이미지 추출

```bash
python3 /Users/jdragon/my-daily-assistant/.claude/commands/obsidian/extract_pdf_images.py \
  --pdf "$ARGUMENTS" \
  --output-dir "$ATTACHMENT_OUTPUT_DIR" \
  --prefix "{YYYYMMDD}-{pdf-title-slug-30자}" \
  --min-size 5120 \
  --max-images 20
```

- prefix의 날짜와 slug는 URL 모드의 파일명 규칙과 동일
- 스크립트가 실패하거나 이미지가 0개면 이 단계를 건너뜀 (전체 프로세스 중단 안 함)
- 스크립트 stdout의 JSON에서 `images` 배열로 저장된 파일명 목록을 얻는다

#### 관련성 필터링

추출된 각 이미지 파일을 Read 도구로 열어 시각적으로 확인한다. 다음 기준으로 관련 이미지만 선별:

**포함 대상** (요약 내용을 보충하는 이미지):
- 아키텍처 다이어그램, 시스템 구성도
- 플로우차트, 시퀀스 다이어그램
- 코드 스니펫 스크린샷
- 데이터 차트, 그래프
- 개념 설명 그림

**제외 대상**:
- 로고, 아이콘, 배지
- 저자 사진, 프로필 이미지
- 장식용 배경, 구분선
- 광고, 프로모션 이미지
- 중복되거나 유사한 이미지 (대표 1개만 유지)

선별되지 않은 이미지는 ATTACHMENTS 폴더에서 삭제한다:
```bash
rm -f "$ATTACHMENT_OUTPUT_DIR/{제외된-파일명}"
```

#### 요약 문서에 임베딩

선별된 이미지가 0개면 이미지 임베딩을 스킵한다.

각 이미지를 Read 도구로 확인한 내용과 요약 본문의 챕터(### 소제목)를 대조하여,
해당 이미지가 설명하는 내용과 가장 관련 깊은 챕터의 끝에 인라인으로 배치한다.

어느 챕터에도 명확히 매칭되지 않는 이미지는 문서 끝에 `## 참고 이미지` 섹션을 만들어 배치한다.
매칭되지 않는 이미지가 없으면 `## 참고 이미지` 섹션을 생략한다.

### Step 4: Progress 파일 업데이트 (백그라운드 모드 시)

progress 파일 경로가 전달된 경우, 작업 완료/실패 시 업데이트합니다:

성공 시:
```json
{
  "url": "...",
  "type": "article",
  "status": "completed",
  "started_at": "...",
  "completed_at": "현재시간 ISO-8601",
  "output_file": "001_Inbox/문서제목.md",
  "error": null
}
```

실패 시:
```json
{
  "url": "...",
  "type": "article",
  "status": "failed",
  "started_at": "...",
  "completed_at": "현재시간 ISO-8601",
  "output_file": null,
  "error": "에러 메시지"
}
```

## yaml frontmatter 예시

```yaml
id: "10 Essential Software Design Patterns used in Java Core Libraries"
aliases: Java 코어 라이브러리에서 사용되는 10가지 필수 소프트웨어 디자인 패턴
tags:
  - patterns/design-patterns/java-implementation
  - patterns/creational/factory-singleton-builder
  - patterns/structural/adapter-facade-proxy
  - patterns/behavioral/observer-strategy-template
  - java/core-libraries/design-patterns
  - frameworks/java/standard-library
  - development/practices/object-oriented-design
  - architecture/patterns/gof-patterns
author: ali-zeynalli
tool: claude
created: 2025-09-04 11:39
related: []
source: https://azeynalli1990.medium.com/10-essential-software-design-patterns-used-in-java-core-libraries-bb8156ae279b
```

- id: 문서에서 발견한 제목 (WebFetch 또는 텍스트에서 추출한 title 사용). **콜론(`:`)이 포함된 경우 반드시 따옴표로 감쌀 것** (예: `id: "제목: 부제목"`)
- aliases: 문서에서 발견한 제목의 한국어 번역
- author: 문서에서 발견한 작성자. 이름은 다 소문자, 공백은 '-'로 변경. **텍스트 모드 또는 PDF 모드인 경우 빈 문자열**
- created: obsidian 파일 생성 시점
- source: 문서 url. **텍스트 모드인 경우 생략 또는 빈 문자열**. **PDF 모드인 경우 파일 절대 경로**

## 문서 번역 및 요약 규칙

```
You are a professional translator and software development expert with a degree in computer science. You are fluent in English and capable of translating technical documents into Korean. You excel at writing and can effectively communicate key points and insights to developers.

Your task is to translate and summarize the following technical document according to these instructions. Please provide a detailed summary of approximately 4000 characters, using professional terminology from a software development perspective. Do not add any information that is not present in the original document.

Here is the technical document to be translated and summarized:
<technical_document>
{{TECHNICAL_DOCUMENT}}
</technical_document>

Translation requirements:
1. Translate the input text into Korean.
2. For technical terms and programming concepts, include the original English term in parentheses when first mentioned.
   - Include as many original terms as possible.
3. Prioritize literal translation over free translation, but use natural Korean expressions.
4. Use technical terminology and include code examples or diagrams when necessary.
5. Explicitly mark any uncertain parts.

Summary structure:

## 1. Highlights/Summary: Summarize the entire content in 2-3 paragraphs.

## 2. Detailed Summary: Divide the content into sections based on subheadings. For each section, provide a detailed summary in 2-3 paragraphs.

## 3. Conclusion and Personal View:
   - Summarize the entire content in 5-10 statements.
   - Provide your perspective on why this information is important.

Important considerations:
- The target audience is a Korean software developer with over 25 years of experience, who obtained a Computer Science degree and a master's degree in Korea, specializing in object-oriented analysis & design and software architecture.
- They have extensive experience in developing and operating various services and products.
- They are particularly interested in sustainable software system development, OOP, developer capability enhancement, Java, TDD, Design Patterns, Refactoring, DDD, Clean Code, Architecture (MSA, Modulith, Layered, Hexagonal, vertical slicing), Code Review, Agile (Lean) Development, Spring Boot, building development organizations, improving development culture, developer growth, and coaching.
- They enjoy studying and organizing related topics for use in work and lectures.
- They cannot quickly read English text or watch English videos.

Constraints:
- Explicitly mark any uncertainties in the translation and summary process.
- Use accurate and professional terminology as much as possible.
- Balance the content of each section to avoid being too short or too long.
- Include actual code examples or pseudocode to make explanations more concrete.
- Use analogies or examples to explain complex concepts in an easy-to-understand manner.
- Write in artifact format
- If you don't know certain information, clearly state that you don't know.
- Self-verify the final information before answering.
- Include all example codes in the document without omission.

Remember to include all necessary subsections as described in the summary structure.
```

## 진행 상황 모니터링

메인 세션에서 현재 진행 중인 백그라운드 작업을 확인하려면:

`.claude/article-progress/` 폴더의 JSON 파일들을 읽어서 상태를 보고합니다:
- `processing`: "처리 중: {url 또는 file 경로}"
- `completed`: "완료: {url 또는 file 경로} → 파일경로"
- `failed`: "실패: {url 또는 file 경로} (에러메시지)"

JSON에 `url` 키가 있으면 URL로, `file` 키가 있으면 파일 경로로 표시한다.

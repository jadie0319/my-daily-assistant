---
argument-hint: "[url 또는 텍스트]"
description: "기술 문서 URL 또는 텍스트 → 번역/정리 → env.config 의 ARTICLE_DIR 을 참고해서  obsidian 문서 생성"
color: yellow
---

# article summarize - $ARGUMENTS

기술 문서 URL 또는 텍스트를 받아 **백그라운드**로 번역/정리하여 Obsidian 문서를 생성합니다.

## 입력 타입 판별

`$ARGUMENTS`의 앞 8자를 확인한다:

- `http://` 또는 `https://`로 시작하면 → **URL 모드** (기존 동작)
- 그 외 → **텍스트 모드** (새 동작)

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

### Step 2: 백그라운드 subagent 시작

Task tool을 사용하여 백그라운드 subagent를 시작합니다:

- `subagent_type`: "general-purpose"
- `run_in_background`: true
- **URL 모드** `description`: "Summarize: {URL 도메인/경로 일부}"
- **텍스트 모드** `description`: "Summarize text: {텍스트 앞 30자}"
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

## 동기 모드 (subagent에서 호출 시 / 백그라운드 subagent 내부)

### Step 1: 콘텐츠 추출

**URL 모드**: `WebFetch` 도구로 URL에 접근하여 콘텐츠를 추출합니다.

- URL: `$ARGUMENTS`
- prompt: "이 기술 문서의 전체 내용을 추출하라. 제목, 작성자, 본문 전체(모든 섹션, 코드 예제 포함)를 빠짐없이 반환하라."
- 실패 시: 에러 보고 후 중단 (progress 파일을 `failed`로 업데이트)

WebFetch 결과에서 다음을 파악한다:
- **title**: 문서 제목
- **author**: 작성자 (없으면 빈 문자열)
- **content**: 본문 전체 (번역/요약에 사용)

본문이 200자 미만이면 로그인 wall 또는 접근 제한 가능성이 있으므로 사용자에게 안내한다.

**텍스트 모드**: WebFetch를 스킵하고 다음을 설정한다.

- **title**: 텍스트에서 첫 번째 `#` 마크다운 헤딩을 추출. 없으면 첫 문장(최대 80자)을 title로 사용
- **author**: 빈 문자열
- **content**: `$ARGUMENTS` 전체 텍스트

### Step 2: 번역 및 요약

추출된 콘텐츠를 아래 규칙(`## 문서 번역 및 요약 규칙`)에 따라 정리하여 yaml frontmatter를 포함한 obsidian 파일로 저장합니다.

- 저장 경로: `$OBSIDIAN_VAULT/$ARTICLE_DIR/`
- hierarchical tagging 규칙: `~/.claude/commands/obsidian/add-tag.md` 준수

### Step 3: 이미지 처리

**텍스트 모드인 경우 이 단계를 완전히 스킵한다.**

**URL 모드**: WebFetch 결과에 이미지 URL이 포함된 경우, ATTACHMENTS 폴더에 저장하고 Obsidian 문서에 포함시킵니다.

- ATTACHMENTS 경로: `$OBSIDIAN_VAULT/$ATTACHMENT_DIR/`
- 이미지 URL이 없으면 이 단계를 건너뜀
- 이미지 다운로드에는 bash curl을 사용합니다:
  ```bash
  curl -sL -o $OBSIDIAN_VAULT/$ATTACHMENT_DIR/{filename} "{image_url}"
  ```

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
- author: 문서에서 발견한 작성자. 이름은 다 소문자, 공백은 '-'로 변경. **텍스트 모드인 경우 빈 문자열**
- created: obsidian 파일 생성 시점
- source: 문서 url. **텍스트 모드인 경우 생략 또는 빈 문자열**

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
- `processing`: "처리 중: URL"
- `completed`: "완료: URL → 파일경로"
- `failed`: "실패: URL (에러메시지)"

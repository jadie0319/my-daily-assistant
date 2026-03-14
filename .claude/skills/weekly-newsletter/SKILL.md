---
name: weekly-newsletter
description: 
  Obsidian vault에서 이번 주(토~금) 작성/수정된 글들을 모아 뉴스레터 생성. 서브 에이전트 기반 병렬 처리로 메인 컨텍스트 절약. 기술적, 리더십적으로 외부에 공유할 만한 내용을 선별하여 정리. "뉴스레터 만들어줘", "이번 주 글 정리해줘", "weekly digest" 등의 요청 시 자동 적용.
---

# Weekly Newsletter Skill

## 개요

매주 토요일 오전 실행하여 **기술적, 리더십적으로 외부 공유할 만한 내용**을 뉴스레터로 작성하는 skill.

## 핵심 아키텍처

> **서브 에이전트 기반 병렬 처리**로 메인 에이전트의 컨텍스트를 최소화합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Agent (Orchestrator)                 │
│  - 날짜 범위 계산 + 파일 목록 선계산 (Phase 1)                   │
│  - 서브 에이전트 병렬 실행 (Phase 2)                            │
│  - 결과 통합 및 뉴스레터 작성 (Phase 3)                         │
└─────────────────────────────────────────────────────────────┘
                   │
              ┌────┼────────┐
              │             │
              ▼             ▼
    ┌─────────────┐  ┌─────────────┐  
    │ SubAgent 1  │  │ SubAgent 2  │  
    │ Daily Notes │  │ Weekly Docs │  
    │ Analyzer    │  │ Analyzer    │  
    └─────────────┘  └─────────────┘  
         │                  │            
         └──────────┼───────┘
	                ▼
              ┌─────────────────┐
              │ 뉴스레터 작성    │
              │ (Main Agent)    │
              └─────────────────┘
```

## 인수 (Arguments)

| 인수 | 설명 | 기본값 |
|------|------|--------|
| 주차 | 분석할 주차 (YYYY-WXX 형식) | 금주 |

**사용 예시**:
- `/weekly-newsletter` - 금주 뉴스레터 생성
- `/weekly-newsletter 2026-W03` - 2026년 3주차 뉴스레터 생성

## 주차 정의

> **중요**: 이 스킬에서 주(week)는 **토요일~금요일** 기준입니다.

| 주차 | 시작일 (토) | 종료일 (금) |
|------|------------|------------|
| 2026-W01 | 2025-12-27 | 2026-01-02 |
| 2026-W02 | 2026-01-03 | 2026-01-09 |
| 2026-W03 | 2026-01-10 | 2026-01-16 |

## 실행 시점

- **실행**: 매주 토요일 오전 (또는 필요 시)
- **대상 기간**: 해당 주 토요일 ~ 금요일 (7일간)
- **출력**: `$NEWSLETTER_DIR/YYYY-WXX-newsletter.md`

## 경로 정보

| 항목          | 경로                                 |
| ----------- | ---------------------------------- |
| vault       | `$OBSIDIAN_VAULT/`                 |
| dailies     | `$OBSIDIAN_VAULT/$DAILY_NOTE_DIR/` |
| newsletters | `$OBSIDIAN_VAULT/$NEWSLETTER_DIR/` |

## 입력 소스

| 소스          | 경로                       | 담당 서브 에이전트 |
| ----------- | ------------------------ | ---------- |
| Daily Notes | `$DAILY_NOTE_DIR/` (토~금) | SubAgent 1 |
| 주간 작성 문서    | vault 전체 (해당 주 수정)       | SubAgent 2 |

---

## 실행 절차

### Phase 1: 초기화 (메인 에이전트 - 순차)

1. **env.config 읽기** - 경로 변수 로드
```bash
# Read 도구로 env.config 파일 읽기
# OBSIDIAN_VAULT, DAILY_NOTE_DIR, INBOX_DIR, NOTES_DIR, NEWSLETTER_DIR 변수 확인
```

2. **주차 결정 및 날짜 범위 계산**

```bash
# 인수로 주차가 주어진 경우
if [ -n "$1" ]; then
  WEEK_NUM="$1"  # 예: 2026-W03
else
  # 금주 계산 (ISO 주차 기준)
  WEEK_NUM=$(date +%G-W%V)
fi

# ISO 주차의 월요일 구하기
ISO_MONDAY=$(date -j -f "%G-W%V-%u" "${WEEK_NUM}-1" +%Y-%m-%d 2>/dev/null)

# 토요일 = ISO 월요일 - 2일 (주의 시작)
SATURDAY=$(date -j -v-2d -f "%Y-%m-%d" "$ISO_MONDAY" +%Y-%m-%d)

# 금요일 = 토요일 + 6일 (주의 끝)
FRIDAY=$(date -j -v+6d -f "%Y-%m-%d" "$SATURDAY" +%Y-%m-%d)

# 다음날 (검색 종료 경계)
NEXT_DAY=$(date -j -v+1d -f "%Y-%m-%d" "$FRIDAY" +%Y-%m-%d)

echo "주차: $WEEK_NUM"
echo "대상 기간: $SATURDAY (토) ~ $FRIDAY (금)"
```

**예시**:
- `2026-W03` → ISO 월요일: 2026-01-13 → 토요일(ISO 월요일 -2일): 2026-01-11 → 금요일(토요일 +6일): 2026-01-17

> **참고**: macOS `date` 명령어 사용. GNU date와 문법이 다름.

2. **파일 목록 선계산** (공백 포함 경로 안전 처리)

```bash
# Daily Notes 파일 목록 선계산 (-newermt: 공백 경로 안전)
DAILY_FILES=$(find "$OBSIDIAN_VAULT/$DAILY_NOTE_DIR" -name "*.md" -type f \
  -newermt "${SATURDAY} 00:00:00" ! -newermt "${NEXT_DAY} 00:00:00" \
  2>/dev/null | sort)

# 주간 기술 문서 파일 목록 선계산
DOC_FILES=$(find \
  "$OBSIDIAN_VAULT/$INBOX_DIR" \
  "$OBSIDIAN_VAULT/$NOTES_DIR" \
  -name "*.md" -type f \
  -newermt "${SATURDAY} 00:00:00" ! -newermt "${NEXT_DAY} 00:00:00" \
  2>/dev/null | sort | head -10)
```

> **주의**: `stat -f "%Sm %N"` + awk 방식은 공백 포함 경로에서 경로가 잘려 동작 불능. `-newermt`는 경로 파싱 없이 mtime 비교만 하여 안전.

3. **출력 경로 확인**
```bash
OUTPUT_FILE="$OBSIDIAN_VAULT/$NEWSLETTER_DIR/${WEEK_NUM}-newsletter.md"
```

---

### Phase 2: 서브 에이전트 병렬 실행 ★

> **중요**: 아래 2개의 Task를 **단일 메시지에서 동시에 호출**하여 병렬 실행합니다.
> 각 서브 에이전트는 분석 결과를 **마크다운 형식의 텍스트**로 반환합니다.
> 비용/속도 최적화를 위해 **haiku 모델**을 사용합니다.

---

#### SubAgent 1: Daily Notes Analyzer

**Task 호출 파라미터:**

| 파라미터          | 값                 |
| ------------- | ----------------- |
| description   | "Daily Notes 분석"  |
| subagent_type | "general-purpose" |
| model         | "haiku"           |

**프롬프트 (SATURDAY, FRIDAY, NEXT_DAY 치환 필요):**

```
{SATURDAY}~{FRIDAY} Daily Notes 분석. Read 도구로 아래 파일들을 읽고 요약하세요.

## 읽을 파일
{DAILY_FILES_LIST}

포함: 기술 학습, 해결한 문제, 외부 공유 적합 인사이트
제외: 내부 업무, 개인 일정, 고객/파트너 정보

## 출력 (마크다운, 간결하게)
### 주간 업무 하이라이트
- **[날짜]**: 핵심 1줄

### 기술 학습
- 항목 1줄씩

(파일 없으면 "Daily Notes 없음")
```

---
#### SubAgent 2: Weekly Documents Analyzer

**Task 호출 파라미터:**

| 파라미터          | 값                 |
| ------------- | ----------------- |
| description   | "주간 문서 분석"        |
| subagent_type | "general-purpose" |
| model         | "haiku"           |

**프롬프트 (SATURDAY, FRIDAY, NEXT_DAY 치환 필요):**

```
{SATURDAY}~{FRIDAY} 기술 문서 분석. Read 도구로 아래 파일들을 읽고 외부 공유 가치를 평가하세요.

## 읽을 파일
{DOC_FILES_LIST}

포함: AI/아키텍처/개발 방법론, 리더십, 학습 방법론
제외: 내부 업무, 회사 프로세스, 개인 일정, 고객 정보

## 출력 (마크다운, 문서당 2줄 이내)
### 기술 트렌드
- **[파일명]**: 핵심 2줄

### 리더십 & 조직
- **[파일명]**: 핵심 2줄

### 학습 방법론
- **[파일명]**: 핵심 2줄

(해당 없으면 섹션 생략, 파일 없으면 "기술 문서 없음")
```

---

### Phase 3: 결과 통합 및 뉴스레터 작성 (메인 에이전트)

1. **2개 서브 에이전트 결과 수집**
   - 각 Task 도구의 반환값을 수집

2. **뉴스레터 작성**

   Write 도구를 사용하여 `$NEWSLETTER_DIR/{WEEK_NUM}-newsletter.md` 생성:

```markdown
---
id: {WEEK_NUM}-newsletter
aliases:
  - {YEAR}년 {WEEK}주차 뉴스레터
tags:
  - newsletter
  - weekly-digest
created_at: {TODAY}
period: {SATURDAY} ~ {FRIDAY}
---

# Weekly Digest - {YEAR}년 {WEEK}주차

> "핵심 인용문" - 출처

**기간**: {SATURDAY_DISPLAY} (토) ~ {FRIDAY_DISPLAY} (금)

---

## 기술 트렌드

{SubAgent 2 결과 - 기술 트렌드 부분}

---

## 리더십 & 조직 인사이트

{SubAgent 2 결과 - 리더십 부분}
{SubAgent 2 결과 - 리더십 관련 내용}

---

## 주간 업무 하이라이트

{SubAgent 1 결과}

---

## 이번 주 핵심 교훈

1. 교훈 1 (위 내용에서 추출)
2. 교훈 2
3. 교훈 3

---

## 다음 주 포커스

- [ ] 포커스 영역 1
- [ ] 포커스 영역 2

---

## Related Notes

- [[관련 노트 1]]
- [[관련 노트 2]]
```

4. **완료 메시지 출력**
```
{WEEK_NUM} 뉴스레터가 생성되었습니다: $NEWSLETTER_DIR/{WEEK_NUM}-newsletter.md
```

---

## 병렬 실행 핵심 원칙

1. **단일 응답에서 2개 Task 동시 호출**: 메인 에이전트는 Phase 2에서 하나의 응답에 SubAgent 1, 2를 동시에 호출해야 합니다.

2. **haiku 모델 사용**: 비용과 속도 최적화를 위해 서브 에이전트는 haiku 모델을 사용합니다.

3. **결과만 반환**: 각 서브 에이전트는 마크다운 형식의 분석 결과 텍스트만 반환합니다.

4. **메인 에이전트 역할 최소화**:
   - Phase 1: 날짜 계산 + 파일 목록 선계산 (find -newermt, 1회 실행)
   - Phase 2: Task 호출만 수행 (파일 목록을 프롬프트에 직접 삽입)
   - Phase 3: 결과 조합 및 뉴스레터 작성만 수행

---

## 컨텍스트 절약 효과

| 구분           | 기존 방식       | 서브 에이전트 방식      |
| ------------ | ----------- | --------------- |
| 메인 에이전트 컨텍스트 | 모든 파일 내용 로드 | 최종 결과만 수신       |
| 병렬 처리        | 불가          | 2개 작업 동시 실행     |
| 실패 격리        | 전체 실패       | 개별 서브 에이전트만 재시도 |

---

## 뉴스레터 톤앤매너

1. **점진적 개선(Incremental) 관점** 반영
2. **TDD/Clean Code 철학**과 연결
3. **실용적 인사이트** 중심
4. **핵심 인용문**으로 섹션 강조
5. **다음 주 포커스** 섹션으로 연속성 제공

---

## 외부 공유 적합성 필터링

**포함 (외부 공유 적합):**

|분류|예시|
|---|---|
|기술 트렌드|SDD, AI 코딩 도구, 새로운 아키텍처 패턴|
|리더십 인사이트|효과적인 매니저 특징, 팀 운영 노하우|
|학습 방법론|조각 지식 전략, AI 활용 학습법|
|업계 동향 분석|하이프 사이클, 재본스 역설|

**제외:**

| 분류         | 이유          |
| ---------- | ----------- |
| 내부 업무 세부사항 | 민감한 비즈니스 정보 |
| 회사 고유 프로세스 | 내부 전용       |
| 개인 일정/TODO | 공유 부적합      |
| 고객/파트너 정보  | 기밀 사항       |

---

## 에러 처리

- 서브 에이전트 실패 시: 해당 섹션을 "분석 실패"로 표시하고 나머지 결과는 반영
- newsletters 폴더 없음: 자동 생성
- 파일 없음: "해당 주에 [항목] 없음"으로 표시

---

## 검증 체크리스트

- [ ] 해당 주(토~금) 날짜 범위 정확한지
- [ ] dailies 내용 반영 여부
- [ ] 외부 공유 부적합 내용 제외 여부
- [ ] 마크다운 포맷 정상 렌더링
- [ ] Related Notes 링크 정확성
- [ ] 주차 번호(Week Number) 정확한지

---

## 의존 관계

```
daily-work-logger (매일)
        ↓
    dailies/YYYY-MM-DD.md
        ↓
weekly-newsletter (토요일) ← 이 skill
        ↓
    $NEWSLETTER_DIR/YYYY-WXX-newsletter.md
```

---

## 관련 Skill

- `daily-work-logger`: 매일 업무 내역 정리 (이 skill의 입력 소스)
- `obsidian-vault`: vault 작업 기본 가이드




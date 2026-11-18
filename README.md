# ICT 공모전 Discord 알림 봇

정보통신·컴퓨터공학 전공 대학생을 대상으로 국내 해커톤, AI·SW·데이터·ICT 공모전 신규 공고와 마감 임박 공고를 Discord 채널에 자동으로 보내는 봇.

Gemini API 무료 티어 + GitHub Actions로 운영하며 별도 서버 없이 작동함.

## 주요 기능

1. 국내 대학생 참가 가능한 공고만 수집 (전공 무관 공고 필터링)
2. 공고명, 주최기관, 접수 기간, 행사일, 참가자격, 공식 URL 추출
3. 원문에서 확인된 날짜만 사용 (추측 없음)
4. 중복 공고 자동 제거 (URL·제목 유사도 기준)
5. 신규 공고 Discord Embed 발송
6. 마감 D-7, D-3, D-1 알림 (같은 단계 중복 발송 없음)
7. 매일 오전 9:17(KST) GitHub Actions 자동 실행

## 수집 경로

- **1순위** Gemini API Google Search Grounding — 무료 티어 한도 내에서 실시간 검색
- **2순위** [Wevity](https://www.wevity.com) IT·SW 공모전 목록 스크래핑 (Gemini 실패 시 자동 전환)

> Gemini 무료 티어는 Google Search Grounding 사용에 제한이 있을 수 있음. 실패해도 Wevity 폴백으로 정상 작동함.

## 로컬 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

`.env.example`을 복사해 `.env` 생성 후 키 입력:

```bash
copy .env.example .env
# .env 파일에 실제 키 입력
```

```bash
# Discord 웹후크 연결 테스트
python main.py --test-webhook

# 공고 수집 (Discord 미발송, 로그만 출력)
python main.py --dry-run

# 실제 실행
python main.py
```

## 환경변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `DISCORD_WEBHOOK_URL` | ✅ | Discord 채널 설정 → 연동 → 웹후크에서 복사 |
| `GEMINI_API_KEY` | 권장 | [Google AI Studio](https://aistudio.google.com)에서 발급. 없으면 Wevity 폴백만 사용 |
| `GEMINI_MODEL` | 선택 | 기본값 `gemini-2.5-flash` |
| `ALERT_DAYS` | 선택 | 마감 알림 기준일 (기본값 `7,3,1`) |

## GitHub Actions 설정

### 1. 레포지토리 Secrets 등록

**Settings → Secrets and variables → Actions → New repository secret**

- `DISCORD_WEBHOOK_URL` : Discord 웹후크 URL
- `GEMINI_API_KEY` : Gemini API 키

### 2. Actions 쓰기 권한 활성화

**Settings → Actions → General → Workflow permissions**  
→ **Read and write permissions** 선택 후 저장

GitHub Actions가 `data/contests.json`을 커밋할 때 필요함.

### 3. 실행 주기

매일 오전 9:17 KST(UTC 00:17)에 자동 실행됨. 수동 실행은 Actions 탭에서 **Run workflow** 버튼으로 가능.

## 프로젝트 구조

```
ict-contest-bot/
├── main.py                  # 진입점 (CLI 옵션 처리)
├── requirements.txt
├── .env.example             # 환경변수 예시 (실제 키 입력 금지)
├── data/
│   └── contests.json        # 수집된 공고 및 알림 상태 (자동 갱신)
├── src/
│   ├── bot.py               # 전체 흐름 조율
│   ├── config.py            # 환경변수 로드
│   ├── models.py            # Contest 데이터 모델
│   ├── filter.py            # 전공 관련성·자격·만료 필터
│   ├── deadline.py          # D-7/D-3/D-1 알림 판단
│   ├── storage.py           # JSON 저장·중복 제거
│   ├── discord.py           # Embed 생성 및 발송
│   └── collectors/
│       ├── gemini_search.py # Gemini Google Search Grounding
│       ├── wevity_collector.py # Wevity 스크래핑
│       └── fallback.py      # 수집기 조율
└── .github/workflows/
    └── contest-alert.yml    # GitHub Actions 워크플로
```

## 주의사항

- `.env`는 절대 Git에 올리지 말 것 (`.gitignore`에 포함됨)
- `data/contests.json`은 GitHub Actions가 자동 커밋함 — 직접 수정 주의
- Wevity 구조 변경 시 `src/collectors/wevity_collector.py` 선택자 수정 필요
- 비공식 도구이며 공고 수집 누락이 발생할 수 있음

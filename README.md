# ICT 공모전 Discord 알림 봇

정보통신·컴퓨터공학 전공 대학생을 대상으로 국내 해커톤, AI·SW·데이터·ICT 공모전 신규 공고와 마감 임박 공고를 Discord 채널에 자동으로 보내는 봇.

GitHub Actions로 운영하며 별도 서버 없이 작동함. Gemini 검색은 선택 기능임.

## 주요 기능

1. 참가 대상에 대학생·학부생·청년·일반인 또는 대한민국 국민 누구나·제한없음 등이 명시된 공고만 수집 (전공 무관 공고 필터링)
2. 공고명, 주최기관, 접수 기간, 행사일, 참가자격, 공식 URL 추출
3. 원문에서 마감일을 확인한 공고만 알림에 포함 (날짜 추측 없음)
4. 중복 공고 자동 제거 (URL·제목 핵심 구절·마감일 기준, 다른 연도·회차는 별도 유지)
5. 진행 중인 공모전을 하루에 Discord 요약으로 총정리하고 길면 여러 메시지로 나눠 발송 (각 메시지 성공 직후 상태 저장, 중간 실패 후 재실행하면 이미 보낸 공고는 건너뜀)
6. 교육·취업 모집을 제외하고, 수집처 오류나 수집 건수 급감 시 Discord에 상태 알림 발송
6. 마감일이 빠른 순서로 정렬하고 공고명, 마감일, D-day, 공식 링크를 간결하게 표시
7. 매일 오전 9:17(KST) GitHub Actions 자동 실행

AI 도구로 광고·영상·포스터를 제작하는 공모전과 e스포츠 대회는 제외한다. AI 모델·에이전트 개발, 데이터 분석, 소프트웨어·임베디드·보안·블록체인처럼 기술 과제가 확인되는 공모전을 우선한다. 이미 저장된 공고도 매일 같은 기준으로 다시 걸러서 요약한다.

## 수집 경로

- **Google 검색** Gemini 검색을 명시적으로 켜고 사용 가능한 API 키가 있을 때 여러 웹사이트의 공모전을 검색
- **Wevity** [Wevity](https://www.wevity.com) 기획/아이디어·과학/기술·IT 분야의 접수 중 목록 여러 페이지를 매번 직접 수집
- **DAKER** [DAKER](https://daker.ai/public/hackathons) AI·데이터 해커톤을 매번 직접 수집
- **씽유** [접수 중 IT·SW 공모전](https://thinkyou.co.kr/contest/sector.asp?serfield=5&serstatus=1) 목록과 상세 페이지를 확인
- **코워커** [진행 중 공모전](https://co-worker.co.kr/Contest/state_contest_list?contest_state=3) 목록에서 ICT 관련 공고의 참가 자격과 마감일을 확인
- **콘테스트코리아** [학문·과학·IT 공모전](https://www.contestkorea.com/sub/list.php?Txt_bcode=030310001&int_gbn=1) 목록에서 참가 대상과 접수 기간을 확인

> Gemini 3 이상 모델의 Google Search Grounding은 무료 API 등급에서 사용할 수 없다. 검색 기능을 쓰려면 사용 가능한 프로젝트에서 `GEMINI_SEARCH_ENABLED=true`를 설정한다. 꺼져 있거나 검색에 실패해도 공개 사이트 수집은 실행한다.

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

GitHub에서 실제 알림을 시험할 때는 **Actions → Daily ICT Contest Alert Bot → Run workflow**에서 `master`를 선택한다. 이전 실행 화면의 **Re-run**은 당시 커밋의 예전 코드를 다시 실행하므로 사용하지 않는다.
오늘 요약이 이미 발송됐다면 `send_test_digest`를 선택해 수정된 요약을 한 번 더 확인할 수 있다. 같은 날 이 옵션을 다시 실행해도 추가 발송하지 않는다.

## 환경변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `DISCORD_WEBHOOK_URL` | ✅ | Discord 채널 설정 → 연동 → 웹후크에서 복사 |
| `GEMINI_API_KEY` | 선택 | Gemini 검색을 켤 때만 사용. 없으면 공개 사이트에서 수집 |
| `GEMINI_MODEL` | 선택 | 기본값 `gemini-3.8-flash` |
| `GEMINI_SEARCH_ENABLED` | 선택 | 기본값 `false`. 검색 연결 사용 가능 시 `true` |
| `ALERT_DAYS` | 선택 | 마감 알림 기준일 (기본값 `7,3,1`) |

## GitHub Actions 설정

### 1. 레포지토리 Secrets 등록

**Settings → Secrets and variables → Actions → New repository secret**

- `DISCORD_WEBHOOK_URL` : Discord 웹후크 URL
- `GEMINI_API_KEY` : Gemini API 키
- `GEMINI_SEARCH_ENABLED` : 검색 연결을 사용할 수 있을 때 Actions 변수로 `true` 설정

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
│       ├── daker_collector.py # DAKER 해커톤 수집
│       └── fallback.py      # 수집기 조율
└── .github/workflows/
    └── contest-alert.yml    # GitHub Actions 워크플로
```

## 주의사항

- `.env`는 절대 Git에 올리지 말 것 (`.gitignore`에 포함됨)
- `data/contests.json`은 GitHub Actions가 자동 커밋함 — 직접 수정 주의
- Wevity 구조 변경 시 `src/collectors/wevity_collector.py` 선택자 수정 필요
- 비공식 도구이며 공고 수집 누락이 발생할 수 있음

# ICT 공모전 Discord 알림 봇

국내 ICT 공모전과 해커톤 공고를 모아 매일 Discord 채널에 보내는 Python 봇. 여러 사이트를 확인하면서 같은 공고를 반복해서 읽거나 마감일을 놓치는 일이 번거로워 만들었다. 별도 서버 없이 GitHub Actions에서 실행한다.

## 왜 만들었나

공모전 정보가 사이트마다 흩어져 있고, 검색 결과에는 접수가 끝난 공고나 기술 분야와 관계없는 행사도 섞여 있다. 제목만으로는 참가 자격과 마감일을 알기 어려워 상세 페이지를 확인해야 한다.

이 봇은 공개 공고 사이트에서 후보를 모은 다음 참가 자격, 기술 관련성, 접수 마감일을 확인한다. 조건을 통과한 공고를 마감일 순서로 정리해 Discord에 보낸다.

## 동작 방식

```text
공고 사이트 5곳에서 목록과 상세 페이지 수집
                ↓
참가 대상, ICT 관련성, 마감일 검사
                ↓
Gemini로 애매한 공고 재검토 (선택)
                ↓
기존 공고와 중복 비교, JSON 파일에 상태 저장
                ↓
진행 중인 공고를 마감일 순으로 Discord에 발송
```

매일 한국 시간 **오전 8시 7분과 8시 37분**에 GitHub Actions가 실행된다. 두 번째 실행은 예약 누락에 대비한다. 실제 메시지는 수집이 끝난 뒤 도착한다. 이미 그날 요약을 보냈다면 다시 실행해도 중복 발송하지 않는다.

### 어디에서 가져오나

| 사이트 | 확인하는 내용 |
|---|---|
| [Wevity](https://www.wevity.com/) | 기획, 과학기술, IT 분야의 접수 중 공고 |
| [DAKER](https://daker.ai/public/hackathons) | AI와 데이터 해커톤 |
| [씽유](https://thinkyou.co.kr/contest/sector.asp?serfield=5&serstatus=1) | 접수 중인 IT 및 SW 공모전 |
| [코워커](https://co-worker.co.kr/Contest/state_contest_list?contest_state=3) | 진행 중인 공모전의 상세 정보 |
| [콘테스트코리아](https://www.contestkorea.com/sub/list.php?Txt_bcode=030310001&int_gbn=1) | 학문, 과학, IT 분야 공모전 |

목록에서 후보 링크를 찾고 상세 페이지에서 참가 대상과 접수 기간을 읽는다. 수집처의 페이지 구조가 바뀌면 해당 수집기를 수정해야 한다.

### 어떤 공고를 보내나

- AI, 소프트웨어, 데이터, 보안, 임베디드 등 기술 과제가 있는 공모전과 해커톤을 대상으로 한다.
- 대학생과 학부생뿐 아니라 청년, 일반인, 대한민국 국민 누구나 참가할 수 있는 공고도 포함한다. 공고에 적힌 참가 자격을 기준으로 판단한다.
- 원문에서 접수 마감일을 확인할 수 있어야 한다. 마감일을 추측해 채우지 않는다.
- 교육 과정, 채용 공고, 광고 영상이나 포스터 제작처럼 기술 과제가 중심이 아닌 행사는 제외한다.
- 같은 공고가 여러 사이트에 올라오면 URL, 제목, 마감일을 비교해 중복을 줄인다. 다른 연도나 회차의 공고는 별도로 취급한다.

규칙을 통과한 공고는 선택적으로 Gemini에 한 번 더 보여 준다. Gemini가 **원문에 있는 구절을 근거로** 제외 사유를 제시했을 때만 제외한다. 응답이 불확실하거나 API 호출이 실패하면 기존 규칙의 결과를 유지한다. 현재 운영 설정은 무료 모델 `gemini-3.5-flash-lite`를 사용하며, Gemini의 Google 검색 연결은 꺼져 있다. AI가 새 공고를 검색하는 방식은 아니다.

### Discord 메시지

진행 중인 공고를 마감일이 빠른 순으로 묶어 보낸다. 각 항목에 제목과 원문 링크, 마감일, 남은 날짜, 주최와 참가 대상을 표시한다. 메시지가 길어지면 여러 개로 나눠 보내고, 중간에 전송이 실패하면 다음 실행에서 이미 보낸 부분을 건너뛴다. 마감 D-7, D-3, D-1에 해당하는 공고도 표시한다.

## 구현하면서 신경 쓴 점

| 문제 | 처리 방식 |
|---|---|
| 같은 공고가 여러 사이트에 있음 | 저장된 공고와 비교해 중복을 합치고, 연도와 회차는 구분 |
| 마감일이 없는 공고가 섞임 | 확인된 마감일이 없으면 알림 대상에서 제외 |
| AI가 잘못 판단하거나 호출에 실패할 수 있음 | 원문 근거가 있는 제외 판단만 반영하고, 실패하면 규칙 필터 결과 사용 |
| Discord 메시지 길이 제한 | 공고를 나눠 발송하고 성공한 페이지마다 상태 저장 |
| 사이트 수집이 갑자기 0건이 됨 | 수집처별 건수와 오류를 기록하고 Discord에 상태 알림 |
| 봇을 다시 실행하면 메시지가 반복됨 | 마지막 발송 날짜와 공고별 알림 상태를 JSON에 저장 |

Python으로 수집, 필터링, 발송 흐름을 구현했다. 공고와 알림 상태는 `data/contests.json`에 저장하며, GitHub Actions가 실행 후 변경된 파일을 저장소에 커밋한다. 데이터베이스나 별도 상시 서버가 필요하지 않은 규모라 이 방식을 골랐다.

## 직접 실행하기

Python 3.11 기준. PowerShell에서 저장소 폴더로 이동한 뒤 실행한다.

```powershell
cd C:\Projects\ict-contest-bot
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 Discord 웹훅 주소를 넣는다. Gemini 검토를 쓰려면 API 키와 `GEMINI_REFINE_ENABLED=true`도 설정한다. Google 검색 연결은 무료 검토에 필요하지 않다.

```powershell
python main.py --test-webhook   # 웹훅에 테스트 메시지 발송
python main.py --dry-run        # 수집과 필터링 확인, Discord 발송 없음
python main.py                  # 실제 공고 요약 발송
```

오늘 이미 요약이 발송됐다면 `python main.py --send-test-digest`로 하루에 한 번 추가 요약을 보낼 수 있다. 이 옵션도 같은 날 다시 실행하면 중복 발송하지 않는다.

테스트는 다음 명령으로 실행한다.

```powershell
python -m unittest discover -s tests -q
```

### GitHub Actions 설정

저장소의 **Settings → Secrets and variables → Actions**에서 아래 항목을 등록한다.

| 종류 | 이름 | 용도 |
|---|---|---|
| Secret | `DISCORD_WEBHOOK_URL` | 메시지를 받을 Discord 채널의 웹훅 주소 |
| Secret | `GEMINI_API_KEY` | Gemini 검토를 사용할 때 필요한 키 |
| Variable | `GEMINI_REFINE_ENABLED` | 무료 Gemini 검토를 켜려면 `true` |
| Variable | `GEMINI_REFINE_MODEL` | 기본값 `gemini-3.5-flash-lite` |

웹훅 주소를 바꿨다면 로컬 `.env`와 GitHub Secret을 각각 갱신해야 한다. 로컬 파일을 수정해도 GitHub Secret은 자동으로 바뀌지 않는다. Actions가 `data/contests.json`을 푸시할 수 있도록 **Settings → Actions → General → Workflow permissions**에서 쓰기 권한을 허용한다.

수동 실행은 **Actions → Daily ICT Contest Alert Bot → Run workflow**에서 `master`를 선택한다. 오늘 요약을 이미 보냈고 메시지 모양을 다시 확인하려면 `send_test_digest`를 선택한다. 이전 실행의 **Re-run**은 당시 커밋을 다시 실행하므로 최신 코드 확인에는 **Run workflow**를 쓴다.

## 프로젝트 구조

```text
main.py                    실행 옵션과 결과 출력
src/bot.py                 수집부터 발송까지 전체 흐름
src/collectors/            사이트별 목록 및 상세 페이지 수집기
src/filter.py              분야, 참가 자격, 마감일 검사
src/gemini_refiner.py      수집된 공고의 선택적 AI 검토
src/storage.py             공고와 발송 상태 저장, 중복 비교
src/discord.py             Discord 요약 메시지 생성과 전송
data/contests.json         수집 공고와 알림 상태
tests/                    단위 및 통합 테스트
.github/workflows/         매일 실행하는 GitHub Actions 설정
```

## 현재 한계

- 수집 대상은 위 다섯 사이트의 공개 페이지다. 모든 국내 공모전을 찾는 것은 아니다.
- 사이트의 HTML 구조가 바뀌거나 상세 정보가 이미지로만 제공되면 일부 공고를 놓칠 수 있다.
- 참가 자격과 기술 관련성을 문구로 판단하므로 애매한 공고는 원문을 다시 확인하는 편이 안전하다.
- `.env`에는 비밀 키가 들어가므로 Git에 올리지 않는다. GitHub Actions에서는 Secret으로 관리한다.

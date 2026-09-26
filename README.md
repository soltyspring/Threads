# Threads 자동화 프로그램

## 1시간 간격 실험 캠페인

`experimental_week.py`는 12개 주제 × 7가지 비교 × A/B 2개 = 168개 게시물을 만듭니다.
주제당 하루 2개씩, 1시간 간격으로 7일 운영합니다. 첫 예약은 최소 10분 이후의 다음 정시입니다.
길이(6/16개), 열 수(2/4열), 간격, 제목 유무, 순서, 빈 줄, 기호 복잡도를 비교합니다.
기호 복잡도는 글꼴 크기가 아니며 서로 다른 기호 집합을 사용하므로 순수한 크기 효과로 해석하지 않습니다.
각 주제의 비교 쌍을 같은 날 배치하고 A/B 순서와 시간을 분산합니다. 단기간 탐색 실험이며
이전 2시간 간격 캠페인과는 빈도도 달라져 직접적인 인과 비교가 불가능합니다.

```bash
.venv/bin/python experimental_week.py --replace
```

이 명령은 기존 DB를 `runtime/backups/`에 백업한 뒤 **pending 예약을 삭제하고 교체**합니다.
게시 이력은 유지하고 `uncertain`/`failed`는 `archived_uncertain`/`archived_failed`로 보존하며
해당 글을 재시도하지 않습니다. 진행 중인 게시가 있으면 교체를 거부합니다.
재실행하면 다시 예약을 교체하므로 상태 조회 목적으로 실행하지 마세요.
실험 조건과 예약 시각은 `runtime/experiment_week.json`, SQLite `experiment_jobs`,
`runtime/schedule.json`에 저장합니다. 실험 조건은 게시물 본문에 표시하지 않습니다.

### 경쟁 계정 포맷 재해석 캠페인

`apply_competitor_campaign.py`는 공개 계정에서 관찰한 형식만 참고해 새 조합을 만들고,
기존 게시글을 복사하지 않습니다. 짧음·중간·김 길이, 제목 유무, 열 수, 간격, 기호 조합을
12개 주제와 4개 실험군으로 분산합니다. 각 글에는 실제 문자 수·UTF-16 길이·행 수·최대 행 폭·
공백 비율이 JSON 메타데이터로 남아 길이와 배치를 따로 분석할 수 있습니다.

```bash
.venv/bin/python apply_competitor_campaign.py plan
.venv/bin/python apply_competitor_campaign.py apply
```

`plan`은 변경 전에 현재 큐 해시와 계획 JSON을 저장하고, `apply`는 SQLite 백업을 만든 뒤
예약 텍스트만 교체합니다. 이미 게시된 글은 다시 올리지 않으며, `uncertain`/`failed`는
API 상태를 확인한 뒤 재시도하지 않습니다. 일주일(168시간)보다 남은 pending 슬롯이 적으면
다음 명령으로 마지막 예약 뒤에 부족한 시간만 추가할 수 있습니다.

```bash
.venv/bin/python apply_competitor_campaign.py topup-plan
.venv/bin/python apply_competitor_campaign.py topup-apply
```

## 설치

```powershell
py -m pip install -r requirements.txt
```

## 사용

프로젝트 폴더의 `.env` 파일에 계정별 Threads 사용자 액세스 토큰을 넣습니다.

```dotenv
THREADS_ACCESS_TOKEN_CUTE=발급받은_cute_토큰
THREADS_ACCESS_TOKEN_LOVELY=발급받은_lovely_토큰
```

계정을 골라 게시합니다.

```powershell
py .\threads_emoji_poster.py --account cute "😀 🌈 ✨"
py .\threads_emoji_poster.py --account lovely "💖 ✨"
```

`--account`를 생략하면 `cute` 계정을 사용하고, 게시글을 생략하면 `😀✨`를 게시합니다.
`.env`는 `.gitignore`에 등록되어 있으므로 저장소에 올라가지 않습니다.

## Ubuntu: cron 기반 예약 실행

서버 프로젝트 폴더의 `.env`에 `THREADS_ACCESS_TOKEN_CUTE`를 설정한 뒤 실행합니다.

```bash
bash install_schedule.sh
```

cron은 매분 큐를 확인하고, 큐에 기록된 시각에만 게시합니다. 현재 실험 큐는 1시간 간격으로
7일(168개 pending 슬롯) 구성되어 있습니다.
인증된 계정이 정확히 `cute.__.emoji`인지 확인하며 lovely 계정은 사용하지 않습니다.
기존 crontab은 보존하고 전용 항목 하나를 추가합니다. cron은 매분 예약 큐를 확인하며,
84개가 끝나면 더 이상 게시하지 않습니다. 서버 시간대와 무관하게 UTC로 저장하고 상태는 한국시간으로 표시합니다.

```bash
.venv/bin/python threads_schedule.py status
.venv/bin/python threads_schedule.py preview
tail -n 20 runtime/scheduler.log
```

예약·게시 결과는 `runtime/schedule.sqlite3`에 보관합니다. 큐가 있으면 설치를 다시 실행해 덮어쓰지 않습니다.
같은 예약 내용은 사람이 확인할 수 있도록 `runtime/schedule.json`에도 UTF-8 JSON으로 저장합니다.
서버 중단으로 30분 이상 지난 예약은 건너뛰며 밀린 글을 연속 게시하지 않습니다.
API 실패 또는 게시 응답 불명확 상태에서는 큐를 중단합니다. `failed`, `uncertain`, `processing`은
계정과 실제 게시 결과를 확인한 뒤 수동으로 처리해야 하며 자동 재시도로 중복 게시하지 않습니다.
중단하려면 `crontab -e`에서 `# threds-cute-week` 줄만 제거하면 됩니다.
Linux의 `python3-venv` 패키지가 필요하며, 설치 스크립트가 venv 관련 오류로 종료하면 서버에서 해당 패키지를 설치해야 합니다.

토큰은 코드나 저장소에 넣지 마세요.

## 게시글 분석 DB

`cute.__.emoji` 계정의 모든 게시글과 현재 성과 지표를 SQLite에 누적합니다.

```bash
.venv/bin/python threads_analytics.py sync --account cute
.venv/bin/python threads_analytics.py summary
```

데이터베이스는 `runtime/threads_analytics.sqlite3`에 생성됩니다. `posts`에는 게시글 본문과
게시 시각·링크가 한 번씩 저장되고, `insight_snapshots`에는 수집 시점별 조회수·좋아요·답글·
리포스트·인용·공유 수가 계속 추가됩니다. `latest_post_insights` 뷰를 사용하면 각 게시글의
최신 지표를 바로 분석할 수 있습니다. 토큰에 `threads_basic`과 `threads_manage_insights`
권한이 필요합니다.

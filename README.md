# Threads 자동화 프로그램

## 천체 이미지 캐러셀 게시

`assets/astro/carousel/`의 10장 이미지를 공개된 `image` 브랜치 URL에서 불러와 한 캐러셀로 게시합니다.
`.env`의 계정을 지정하고 설명문을 전달합니다. 이미지는 AI 생성 장면이므로 게시물에 이를 명시하세요.

```powershell
py .\threads_carousel_poster.py --account lovely --caption "Which of these 10 impossible night skies would you step into first? 🌌 Pick 1–10. AI-generated scenes—not real astrophotography."
```

게시할 계정 토큰(`THREADS_ACCESS_TOKEN_LOVELY` 또는 `THREADS_ACCESS_TOKEN_CUTE`)이 필요합니다.
게시물 미디어 컨테이너가 처리 완료된 것을 확인한 뒤 한 번만 게시합니다.

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

## Ubuntu: 2시간 간격, 7일 예약

서버 프로젝트 폴더의 `.env`에 `THREADS_ACCESS_TOKEN_CUTE`를 설정한 뒤 실행합니다.

```bash
bash install_schedule.sh
```

설정 완료 약 2시간 뒤 첫 게시, 이후 2시간마다 총 84개를 게시합니다.
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

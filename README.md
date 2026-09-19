# Threads 자동화 프로그램

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

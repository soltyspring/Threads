# Threads 이모지 자동 게시기

## 설치

```powershell
py -m pip install requests
```

## 사용

발급받은 Threads 사용자 액세스 토큰을 환경변수에 넣습니다.

```powershell
$env:THREADS_ACCESS_TOKEN = "발급받은_토큰"
py .\threads_emoji_poster.py "😀 🌈 ✨"
```

인자를 생략하면 `😀✨`를 게시합니다. 토큰은 코드나 저장소에 넣지 마세요.

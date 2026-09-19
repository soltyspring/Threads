# Threads 자동화 프로그램

## 사용

발급받은 Threads 사용자 액세스 토큰을 환경변수에 넣습니다.

```powershell
$env:THREADS_ACCESS_TOKEN = "발급받은_토큰"
py .\threads_emoji_poster.py "업로드 할 게시글의 메시지"
```
토큰은 코드나 저장소에 넣지 마세요.

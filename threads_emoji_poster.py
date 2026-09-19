import os
import sys
import requests


API_VERSION = os.getenv("THREADS_API_VERSION", "v1.0")
BASE_URL = f"https://graph.threads.net/{API_VERSION}"


def get_profile(access_token: str) -> dict:
    response = requests.get(
        f"{BASE_URL}/me",
        params={"fields": "id,username,name", "access_token": access_token},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def publish_text(text: str, access_token: str) -> dict:
    profile = get_profile(access_token)
    creation = requests.post(
        f"{BASE_URL}/{profile['id']}/threads",
        data={
            "media_type": "TEXT",
            "text": text,
            "access_token": access_token,
        },
        timeout=30,
    )
    creation.raise_for_status()
    creation_id = creation.json()["id"]

    publish = requests.post(
        f"{BASE_URL}/{profile['id']}/threads_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    publish.raise_for_status()
    return {"profile": profile, "creation": creation.json(), "published": publish.json()}


if __name__ == "__main__":
    token = os.getenv("THREADS_ACCESS_TOKEN")
    if not token:
        sys.exit("THREADS_ACCESS_TOKEN 환경변수를 설정하세요.")
    text = " ".join(sys.argv[1:]).strip() or "😀✨"
    print(publish_text(text, token))

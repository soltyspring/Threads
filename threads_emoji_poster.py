import os
import sys
import argparse
from pathlib import Path
import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().with_name('.env'))

API_VERSION = os.getenv("THREADS_API_VERSION", "v1.0")
BASE_URL = f"https://graph.threads.net/{API_VERSION}"
TOKEN_ENV_BY_ACCOUNT = {
    "cute": "THREADS_ACCESS_TOKEN_CUTE",
    "lovely": "THREADS_ACCESS_TOKEN_LOVELY",
}


def get_profile(access_token: str) -> dict:
    response = requests.get(
        f"{BASE_URL}/me",
        params={"fields": "id,username,name"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def create_container(text: str, access_token: str, user_id: str) -> str:
    response = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"media_type": "TEXT", "text": text}, timeout=30,
    )
    response.raise_for_status()
    return response.json()["id"]


def publish_container(container_id: str, access_token: str, user_id: str) -> str:
    response = requests.post(
        f"{BASE_URL}/{user_id}/threads_publish",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"creation_id": container_id}, timeout=30,
    )
    response.raise_for_status()
    return response.json()["id"]


def publish_text(text: str, access_token: str) -> dict:
    profile = get_profile(access_token)
    creation_id = create_container(text, access_token, profile['id'])
    published_id = publish_container(creation_id, access_token, profile['id'])
    return {"profile": profile, "creation": {"id": creation_id}, "published": {"id": published_id}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Threads 계정에 텍스트를 게시합니다.")
    parser.add_argument(
        "--account",
        choices=TOKEN_ENV_BY_ACCOUNT,
        default="cute",
        help="게시할 계정 (기본값: cute)",
    )
    parser.add_argument("text", nargs="*", help="게시할 텍스트")
    args = parser.parse_args()

    token_env = TOKEN_ENV_BY_ACCOUNT[args.account]
    token = os.getenv(token_env)
    if not token:
        sys.exit(f".env에 {token_env}를 설정하세요.")
    text = " ".join(args.text).strip() or "😀✨"
    print(publish_text(text, token))

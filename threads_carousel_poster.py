"""Publish a public GitHub-hosted image carousel to a Threads account."""

import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().with_name(".env"))

API_VERSION = os.getenv("THREADS_API_VERSION", "v1.0")
BASE_URL = f"https://graph.threads.net/{API_VERSION}"
TOKEN_ENV_BY_ACCOUNT = {
    "cute": "THREADS_ACCESS_TOKEN_CUTE",
    "lovely": "THREADS_ACCESS_TOKEN_LOVELY",
}
ASSET_BASE_URL = (
    "https://raw.githubusercontent.com/soltyspring/Threads/image/"
    "assets/astro/carousel"
)
IMAGE_FILES = [
    "01_alpine_lake_dock_milky_way.png",
    "02_sea_arch_milky_way.png",
    "03_lone_tree_reflection_milky_way.png",
    "04_aurora_coast_milky_way.png",
    "05_autumn_forest_milky_way.png",
    "06_alpine_stream_waterfall_milky_way.png",
    "07_canyon_road_milky_way.png",
    "08_summit_overlook_milky_way.png",
    "09_medieval_stone_alley_milky_way.png",
    "10_european_village_church_milky_way.png",
]


def api_post(path: str, token: str, data: dict) -> dict:
    response = requests.post(
        f"{BASE_URL}/{path}",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def wait_until_ready(container_id: str, token: str, timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(
            f"{BASE_URL}/{container_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "status,error_message"},
            timeout=30,
        )
        response.raise_for_status()
        status = response.json()
        if status.get("status") == "FINISHED":
            return
        if status.get("status") == "ERROR":
            raise RuntimeError(status.get("error_message", "Media processing failed"))
        time.sleep(3)
    raise TimeoutError(f"Container {container_id} did not finish processing")


def publish_carousel(account: str, caption: str) -> dict:
    token = os.getenv(TOKEN_ENV_BY_ACCOUNT[account])
    if not token:
        raise RuntimeError(f"Set {TOKEN_ENV_BY_ACCOUNT[account]} in .env")

    profile_response = requests.get(
        f"{BASE_URL}/me",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "id,username"},
        timeout=30,
    )
    profile_response.raise_for_status()
    profile = profile_response.json()

    children = []
    for index, filename in enumerate(IMAGE_FILES, start=1):
        item = api_post(
            f"{profile['id']}/threads",
            token,
            {
                "media_type": "IMAGE",
                "image_url": f"{ASSET_BASE_URL}/{filename}",
                "is_carousel_item": "true",
                "alt_text": f"AI-generated cosmic night-sky landscape, image {index} of 10.",
            },
        )
        children.append(item["id"])
        print(f"Created image container {index}/10")

    for container_id in children:
        wait_until_ready(container_id, token)

    carousel = api_post(
        f"{profile['id']}/threads",
        token,
        {"media_type": "CAROUSEL", "children": ",".join(children), "text": caption},
    )
    wait_until_ready(carousel["id"], token)
    published = api_post(
        f"{profile['id']}/threads_publish",
        token,
        {"creation_id": carousel["id"]},
    )
    return {"username": profile["username"], "published_id": published["id"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish a 10-image Threads carousel.")
    parser.add_argument("--account", choices=TOKEN_ENV_BY_ACCOUNT, required=True)
    parser.add_argument("--caption", required=True)
    args = parser.parse_args()
    try:
        print(publish_carousel(args.account, args.caption))
    except (requests.RequestException, RuntimeError, TimeoutError) as exc:
        sys.exit(f"Carousel publishing failed: {exc}")

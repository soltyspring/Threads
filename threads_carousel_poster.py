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
    "https://raw.githubusercontent.com/soltyspring/Threads/refs/heads/image/"
    "assets/astro/night-10"
)
IMAGE_FILES = [
    "01_milky_way_rocky_coast_long_exposure.jpg",
    "02_aurora_snowfield_tiny_cabin.jpg",
    "03_lone_tree_blue_night_sky.jpg",
    "04_comet_over_mountain_ridge.jpg",
    "05_circular_star_trails_lake_reflection.jpg",
    "06_magellanic_clouds_coastal_night.jpg",
    "07_moonlit_clouds_and_mountains.jpg",
    "08_milky_way_through_clouds_coast.jpg",
    "09_blue_twilight_lake_and_mountains.jpg",
    "10_starlight_reflection_dark_sea.jpg",
]
ALT_TEXTS = [
    "The Milky Way above a rocky coast at night.",
    "Aurora lights above a snowy field and a small cabin.",
    "A lone tree silhouetted under a deep blue starry sky.",
    "A bright comet above a mountain ridge.",
    "Circular star trails reflected in a still lake.",
    "The Milky Way over a quiet coastal landscape.",
    "Clouds and mountain silhouettes beneath a moonlit sky.",
    "The Milky Way partly veiled by clouds above the coast.",
    "Blue twilight over a lake and distant mountains.",
    "Starlight reflected across a dark sea.",
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
    for index, (filename, alt_text) in enumerate(zip(IMAGE_FILES, ALT_TEXTS), start=1):
        item = api_post(
            f"{profile['id']}/threads",
            token,
            {
                "media_type": "IMAGE",
                "image_url": f"{ASSET_BASE_URL}/{filename}",
                "is_carousel_item": "true",
                "alt_text": alt_text,
            },
        )
        children.append(item["id"])
        print(f"Created image container {index}/10")

    for container_id in children:
        wait_until_ready(container_id, token)

    carousel = api_post(
        f"{profile['id']}/threads",
        token,
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "text": caption,
            "text_entities": '[{"entity_type":"SPOILER","offset":4,"length":2}]',
            "is_spoiler_media": "true",
        },
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

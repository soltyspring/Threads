"""Import all posts owned by a Threads account and snapshot their insights."""
import argparse
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from threads_emoji_poster import BASE_URL, TOKEN_ENV_BY_ACCOUNT, get_profile


ROOT = Path(__file__).resolve().parent
DB = ROOT / "runtime" / "threads_analytics.sqlite3"
POST_FIELDS = (
    "id,media_product_type,media_type,permalink,owner,username,text,"
    "timestamp,shortcode,is_quote_post,has_replies"
)
INSIGHT_METRICS = "views,likes,replies,reposts,quotes,shares"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            name TEXT,
            first_seen_at TEXT NOT NULL,
            last_synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT,
            media_product_type TEXT,
            media_type TEXT,
            text TEXT,
            posted_at TEXT,
            permalink TEXT,
            shortcode TEXT,
            is_quote_post INTEGER,
            has_replies INTEGER,
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES accounts(user_id)
        );

        CREATE TABLE IF NOT EXISTS insight_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            views INTEGER,
            likes INTEGER,
            replies INTEGER,
            reposts INTEGER,
            quotes INTEGER,
            shares INTEGER,
            raw_json TEXT,
            error_code TEXT,
            error_message TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(post_id),
            UNIQUE (post_id, collected_at)
        );

        CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
        CREATE INDEX IF NOT EXISTS idx_insights_post_time
            ON insight_snapshots(post_id, collected_at);

        CREATE VIEW IF NOT EXISTS latest_post_insights AS
        SELECT p.*, s.collected_at AS insight_collected_at,
               s.views, s.likes, s.replies, s.reposts, s.quotes, s.shares,
               s.error_code, s.error_message
        FROM posts p
        LEFT JOIN insight_snapshots s ON s.id = (
            SELECT s2.id FROM insight_snapshots s2
            WHERE s2.post_id = p.post_id
            ORDER BY s2.collected_at DESC, s2.id DESC LIMIT 1
        );

        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            posts_seen INTEGER NOT NULL DEFAULT 0,
            posts_inserted INTEGER NOT NULL DEFAULT 0,
            insights_saved INTEGER NOT NULL DEFAULT 0,
            insight_errors INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        );
        """
    )
    return db


def api_get(url: str, token: str, params: dict | None = None) -> dict:
    response = requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def iter_posts(token: str):
    url = f"{BASE_URL}/me/threads"
    params = {"fields": POST_FIELDS, "limit": 50}
    while url:
        payload = api_get(url, token, params=params)
        yield from payload.get("data", [])
        next_url = payload.get("paging", {}).get("next")
        if next_url:
            parsed = urlparse(next_url)
            if parsed.scheme != "https" or parsed.hostname != "graph.threads.net":
                raise ValueError("Unexpected pagination host")
        url = next_url
        params = None


def insight_values(payload: dict) -> dict:
    result = {}
    for item in payload.get("data", []):
        values = item.get("values") or []
        value = values[0].get("value") if values else item.get("total_value", {}).get("value")
        if isinstance(value, (int, float)):
            result[item.get("name")] = int(value)
    return result


def save_account(db: sqlite3.Connection, profile: dict, collected_at: str) -> None:
    db.execute(
        """INSERT INTO accounts(user_id,username,name,first_seen_at,last_synced_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             username=excluded.username,
             name=excluded.name,
             last_synced_at=excluded.last_synced_at""",
        (profile["id"], profile["username"], profile.get("name"), collected_at, collected_at),
    )


def save_post(db: sqlite3.Connection, post: dict, user_id: str, collected_at: str) -> bool:
    existed = db.execute("SELECT 1 FROM posts WHERE post_id=?", (post["id"],)).fetchone() is not None
    db.execute(
        """INSERT INTO posts(
             post_id,user_id,username,media_product_type,media_type,text,posted_at,
             permalink,shortcode,is_quote_post,has_replies,first_collected_at,
             last_collected_at,raw_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(post_id) DO UPDATE SET
             username=excluded.username,
             media_product_type=excluded.media_product_type,
             media_type=excluded.media_type,
             text=excluded.text,
             posted_at=excluded.posted_at,
             permalink=excluded.permalink,
             shortcode=excluded.shortcode,
             is_quote_post=excluded.is_quote_post,
             has_replies=excluded.has_replies,
             last_collected_at=excluded.last_collected_at,
             raw_json=excluded.raw_json""",
        (
            post["id"], user_id, post.get("username"),
            post.get("media_product_type"), post.get("media_type"), post.get("text"),
            post.get("timestamp"), post.get("permalink"), post.get("shortcode"),
            int(bool(post.get("is_quote_post"))), int(bool(post.get("has_replies"))),
            collected_at, collected_at, json.dumps(post, ensure_ascii=False, sort_keys=True),
        ),
    )
    return not existed


def error_details(exc: requests.HTTPError) -> tuple[str, str]:
    try:
        error = exc.response.json().get("error", {})
        return str(error.get("code") or "HTTPError"), str(error.get("message") or "")[:500]
    except (ValueError, AttributeError):
        return "HTTPError", ""


def fetch_insight(post_id: str, token: str) -> dict:
    try:
        payload = api_get(
            f"{BASE_URL}/{post_id}/insights",
            token,
            params={"metric": INSIGHT_METRICS},
        )
        values = insight_values(payload)
        return {"ok": True, "values": values, "payload": payload}
    except requests.HTTPError as exc:
        code, message = error_details(exc)
        return {"ok": False, "code": code, "message": message}


def save_insight_result(
    db: sqlite3.Connection, post_id: str, collected_at: str, result: dict
) -> bool:
    if result["ok"]:
        values = result["values"]
        db.execute(
            """INSERT INTO insight_snapshots(
                 post_id,collected_at,views,likes,replies,reposts,quotes,shares,raw_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                post_id, collected_at, values.get("views"), values.get("likes"),
                values.get("replies"), values.get("reposts"), values.get("quotes"),
                values.get("shares"),
                json.dumps(result["payload"], ensure_ascii=False, sort_keys=True),
            ),
        )
        return True
    db.execute(
        """INSERT INTO insight_snapshots(
             post_id,collected_at,error_code,error_message)
           VALUES(?,?,?,?)""",
        (post_id, collected_at, result["code"], result["message"]),
    )
    return False


def save_insight(db: sqlite3.Connection, post_id: str, token: str, collected_at: str) -> bool:
    return save_insight_result(db, post_id, collected_at, fetch_insight(post_id, token))


def sync(db: sqlite3.Connection, token: str) -> dict:
    profile = get_profile(token)
    collected_at = now_utc()
    save_account(db, profile, collected_at)
    db.execute(
        """UPDATE sync_runs SET finished_at=?,status='interrupted',
           error_message='Previous process ended before completion'
           WHERE status='running'""",
        (collected_at,),
    )
    cursor = db.execute(
        "INSERT INTO sync_runs(user_id,started_at,status) VALUES(?,?,?)",
        (profile["id"], collected_at, "running"),
    )
    run_id = cursor.lastrowid
    counters = {"posts_seen": 0, "posts_inserted": 0, "insights_saved": 0, "insight_errors": 0}
    db.commit()
    try:
        posts = list(iter_posts(token))
        for post in posts:
            counters["posts_seen"] += 1
            counters["posts_inserted"] += int(save_post(db, post, profile["id"], collected_at))
        db.commit()

        def fetch(post):
            return post["id"], fetch_insight(post["id"], token)

        with ThreadPoolExecutor(max_workers=8) as pool:
            insight_results = pool.map(fetch, posts)
            for post_id, insight_result in insight_results:
                if save_insight_result(db, post_id, collected_at, insight_result):
                    counters["insights_saved"] += 1
                else:
                    counters["insight_errors"] += 1
                db.commit()
        db.execute(
            """UPDATE sync_runs SET finished_at=?,posts_seen=?,posts_inserted=?,
               insights_saved=?,insight_errors=?,status='completed' WHERE id=?""",
            (now_utc(), *counters.values(), run_id),
        )
        db.commit()
        return {"account": profile["username"], **counters, "database": str(DB)}
    except Exception as exc:
        db.execute(
            "UPDATE sync_runs SET finished_at=?,status='failed',error_message=? WHERE id=?",
            (now_utc(), type(exc).__name__, run_id),
        )
        db.commit()
        raise


def summary(db: sqlite3.Connection) -> dict:
    latest = db.execute(
        """SELECT collected_at,COUNT(*) AS posts,
           SUM(COALESCE(views,0)) AS views,SUM(COALESCE(likes,0)) AS likes,
           SUM(COALESCE(replies,0)) AS replies,SUM(COALESCE(reposts,0)) AS reposts,
           SUM(COALESCE(quotes,0)) AS quotes,SUM(COALESCE(shares,0)) AS shares,
           SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS errors
           FROM insight_snapshots
           WHERE collected_at=(SELECT MAX(collected_at) FROM insight_snapshots)"""
    ).fetchone()
    return {
        "accounts": db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
        "posts": db.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "snapshots": db.execute("SELECT COUNT(*) FROM insight_snapshots").fetchone()[0],
        "latest": dict(latest) if latest and latest["collected_at"] else None,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Threads 게시글과 인사이트를 SQLite에 누적합니다.")
    parser.add_argument("command", choices=["sync", "summary"])
    parser.add_argument("--account", choices=TOKEN_ENV_BY_ACCOUNT, default="cute")
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with connect(args.db) as db:
        if args.command == "summary":
            result = summary(db)
        else:
            token_env = TOKEN_ENV_BY_ACCOUNT[args.account]
            token = os.getenv(token_env)
            if not token:
                raise SystemExit(f".env에 {token_env}를 설정하세요.")
            result = sync(db, token)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

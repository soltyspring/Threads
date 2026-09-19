"""Finite cute-only queue, run once per minute by cron. Never retry an uncertain publish."""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from threads_emoji_poster import get_profile, create_container, publish_container
from weekly_content import build_posts

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'runtime' / 'schedule.sqlite3'
JSON_QUEUE = ROOT / 'runtime' / 'schedule.json'
KST = timezone(timedelta(hours=9))
EXPECTED_USER = 'cute.__.emoji'


def now_utc():
    return datetime.now(timezone.utc)


def token_and_profile():
    token = os.getenv('THREADS_ACCESS_TOKEN_CUTE', '')
    if not token:
        raise ValueError('THREADS_ACCESS_TOKEN_CUTE is missing')
    profile = get_profile(token)
    if profile.get('username') != EXPECTED_USER:
        raise ValueError('Token account does not match cute.__.emoji')
    return token, profile


def connect(path=DB):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY, due TEXT NOT NULL, theme TEXT NOT NULL,
        text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
        container_id TEXT, post_id TEXT, error TEXT, updated TEXT)''')
    return db


def initialize(db, first, posts=None):
    if first.tzinfo is None or first <= now_utc():
        raise ValueError('First time must be in the future with a timezone')
    posts = build_posts() if posts is None else posts
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]:
            raise ValueError('Queue already exists; refusing to replace it')
        for i, post in enumerate(posts):
            due = (first + timedelta(hours=2 * i)).astimezone(timezone.utc).isoformat()
            db.execute('INSERT INTO jobs (due,theme,text) VALUES (?,?,?)', (due,post['theme'],post['text']))
        db.commit()
        export_json(db)
    except Exception:
        db.rollback()
        raise


def export_json(db, path=JSON_QUEUE):
    rows = db.execute('SELECT id,due,theme,text,state,container_id,post_id,error,updated FROM jobs ORDER BY id').fetchall()
    payload = {
        'account': EXPECTED_USER,
        'interval_hours': 2,
        'post_count': len(rows),
        'generated_at': now_utc().isoformat(),
        'jobs': [dict(row) for row in rows],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def update(db, job_id, **fields):
    fields['updated'] = now_utc().isoformat()
    db.execute('UPDATE jobs SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=?', (*fields.values(), job_id))
    db.commit()
    export_json(db)


def run_due(db, current=None):
    current = current or now_utc()
    db.execute('BEGIN IMMEDIATE')
    # A crash or an ambiguous network response blocks the queue for manual review.
    if db.execute("SELECT 1 FROM jobs WHERE state IN ('processing','uncertain','failed') LIMIT 1").fetchone():
        db.rollback()
        return 'blocked'
    # After downtime do not release several stale posts in a burst.
    cutoff = (current - timedelta(minutes=30)).isoformat()
    db.execute("UPDATE jobs SET state='expired' WHERE state='pending' AND due < ?", (cutoff,))
    row = db.execute("SELECT * FROM jobs WHERE state='pending' AND due<=? ORDER BY due LIMIT 1", (current.isoformat(),)).fetchone()
    if not row:
        db.commit()
        return 'idle'
    db.execute("UPDATE jobs SET state='processing',updated=? WHERE id=?", (current.isoformat(),row['id']))
    db.commit()
    publish_started = False
    try:
        token, profile = token_and_profile()
        container = create_container(row['text'], token, profile['id'])
        update(db, row['id'], container_id=container)
        publish_started = True
        post_id = publish_container(container, token, profile['id'])
        update(db, row['id'], state='published', post_id=post_id)
        print(json.dumps({'job':row['id'],'state':'published','post_id':post_id}))
        return 'published'
    except Exception as exc:
        # Do not persist response bodies/URLs or exception strings containing credentials.
        state = 'uncertain' if publish_started else 'failed'
        update(db, row['id'], state=state, error=type(exc).__name__)
        print(json.dumps({'job':row['id'],'state':state,'error':type(exc).__name__}))
        return state


def status(db):
    counts = dict(db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state').fetchall())
    bounds = db.execute('SELECT MIN(due),MAX(due) FROM jobs').fetchone()
    times = [datetime.fromisoformat(v).astimezone(KST).isoformat() if v else None for v in bounds]
    return {'account':EXPECTED_USER,'counts':counts,'first_kst':times[0],'last_kst':times[1]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check','init','run','status','preview'])
    parser.add_argument('--first', help='ISO 8601 with timezone; default now + 2h rounded up to minute')
    args = parser.parse_args()
    if args.command == 'preview':
        for i,p in enumerate(build_posts(),1):
            print(f"\n--- {i:02d} ---\n{p['text']}")
        return
    if args.command == 'check':
        _, profile = token_and_profile()
        print(json.dumps({'username':profile['username'],'id':profile['id']}))
        return
    with connect() as db:
        if args.command == 'init':
            token_and_profile()
            first = datetime.fromisoformat(args.first) if args.first else (now_utc()+timedelta(hours=2,minutes=1)).replace(second=0,microsecond=0)
            initialize(db, first)
            print(json.dumps(status(db)))
        elif args.command == 'run':
            result = run_due(db)
            if result in ('failed','uncertain','blocked'):
                raise SystemExit(1)
        else:
            print(json.dumps(status(db)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}; check configuration/account/network (credentials omitted)')
        raise SystemExit(1)

"""168 posts: twelve themes, seven paired experiments, hourly for seven days."""
import json
import random
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import threads_schedule as schedule
from weekly_content import POOLS

EXPERIMENTS = ['length', 'columns', 'spacing', 'title', 'order', 'linebreaks', 'visual_complexity']


def build_experiments():
    posts = []
    themes = list(POOLS)
    for day in range(7):
        daily = []
        for index, theme in enumerate(themes):
            experiment = EXPERIMENTS[(day + index) % 7]
            pool = POOLS[theme].split('|')
            items = random.Random(f'experiment-v2:{theme}:{experiment}').sample(pool, len(pool))
            for arm in ['A', 'B']:
                selected = items[:12]
                columns, gap, newline, title = 3, '　', '\n', theme
                if experiment == 'length': selected = items[:6 if arm == 'A' else 16]
                if experiment == 'columns': columns = 2 if arm == 'A' else 4
                if experiment == 'spacing': gap = ' ' if arm == 'A' else '　　'
                if experiment == 'title' and arm == 'B': title = ''
                if experiment == 'order' and arm == 'B':
                    reordered = sorted(selected, key=len)
                    selected = reordered if reordered != selected else list(reversed(selected))
                if experiment == 'linebreaks' and arm == 'B': newline = '\n\n'
                if experiment == 'visual_complexity':
                    ranked = sorted(pool, key=len)
                    selected = ranked[:8] if arm == 'A' else ranked[-8:]
                body = newline.join(gap.join(selected[i:i+columns]) for i in range(0,len(selected),columns))
                text = (title+'\n\n' if title else '')+body
                daily.append({'theme':theme,'text':text,'experiment':experiment,'arm':arm,
                              'pair':f'{theme}:{experiment}','day':day+1,'items':len(selected),
                              'columns':columns,'gap':gap,'blank_lines':newline=='\n\n',
                              'title_present':bool(title),'utf16_length':len(text.encode('utf-16-le'))//2})
        # Each theme appears once in each twelve-hour block; arms alternate first/second.
        first, second = [], []
        for i, theme in enumerate(themes):
            pair = [p for p in daily if p['theme']==theme]
            if (day+i)%2: pair.reverse()
            first.append(pair[0]); second.append(pair[1])
        rng=random.Random(f'experiment-hours:{day}')
        rng.shuffle(first); rng.shuffle(second)
        posts.extend(first+second)
    assert len(posts)==len({p['text'] for p in posts})==168
    assert all(p['utf16_length']<=500 for p in posts)
    return posts


def replace_queue():
    schedule.token_and_profile()
    posts=build_experiments()
    now=schedule.now_utc()
    first=(now+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
    if (first-now).total_seconds()<600: first+=timedelta(hours=1)
    campaign='hourly-experiment-'+now.strftime('%Y%m%dT%H%M%SZ')
    backup=schedule.ROOT/'runtime'/'backups'/campaign
    backup.mkdir(parents=True,exist_ok=False)
    with closing(schedule.connect()) as db:
        with closing(sqlite3.connect(backup/'schedule.sqlite3')) as dest: db.backup(dest)
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM jobs WHERE state='processing'").fetchone():
            raise RuntimeError('A publish is in progress; retry later')
        db.execute('CREATE TABLE IF NOT EXISTS experiment_jobs (job_id INTEGER PRIMARY KEY, campaign TEXT NOT NULL, metadata TEXT NOT NULL)')
        old=[dict(r) for r in db.execute('SELECT * FROM jobs')]
        removed=db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0]
        next_id=db.execute('SELECT COALESCE(MAX(id),0)+1 FROM jobs').fetchone()[0]
        db.execute("DELETE FROM jobs WHERE state='pending'")
        # Keep ambiguous attempts for reconciliation; never re-publish those texts.
        db.execute("UPDATE jobs SET state='archived_'||state WHERE state IN ('uncertain','failed')")
        old_texts={r['text'] for r in old}
        assert not any(p['text'] in old_texts for p in posts)
        for i,p in enumerate(posts):
            job_id=next_id+i
            due=(first+timedelta(hours=i)).isoformat()
            db.execute('INSERT INTO jobs(id,due,theme,text) VALUES(?,?,?,?)',(job_id,due,p['theme'],p['text']))
            db.execute('INSERT INTO experiment_jobs VALUES(?,?,?)',(job_id,campaign,json.dumps(p,ensure_ascii=False)))
        db.commit()
        schedule.export_json(db)
        payload={'campaign':campaign,'account':schedule.EXPECTED_USER,'interval_hours':1,
                 'first_kst':first.astimezone(schedule.KST).isoformat(),
                 'last_kst':(first+timedelta(hours=167)).astimezone(schedule.KST).isoformat(),
                 'removed_pending':removed,'backup':str(backup),'posts':[
                     dict(p,job_id=next_id+i,due=(first+timedelta(hours=i)).isoformat()) for i,p in enumerate(posts)]}
        (schedule.ROOT/'runtime'/'experiment_week.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in payload.items() if k!='posts'},ensure_ascii=False))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--replace',action='store_true')
    args=parser.parse_args()
    if args.replace: replace_queue()
    else: print(json.dumps(build_experiments(),ensure_ascii=False,indent=2))

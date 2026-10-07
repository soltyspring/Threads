"""Reproducible recent-post analysis using completed insight snapshots."""
import argparse
import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from competitor_formats import display_cells

ROOT = Path(__file__).resolve().parent
USER_EVIDENCE = [
    dict(label='cute emoji', date='2026-09-17', views_approx=570000, instagram_percent=98.83,
         likes=239, reposts=64, replies=5, quotes=0, follows=90, within_recent_window=False),
    dict(label='ribbons symbol', date='2026-09-16', views_approx=270000, instagram_percent=98.21,
         likes=123, reposts=36, replies=0, quotes=0, follows=46, within_recent_window=False),
    dict(label='Flower garden', age_label='4 days', views_approx=130000, instagram_percent=98.87,
         likes=27, reposts=1, replies=0, quotes=0, follows=4),
    dict(label='Little ocean', age_label='3 days', views_approx=100000, instagram_percent=98.24,
         likes=21, reposts=0, replies=0, quotes=0, follows=3),
    dict(label='Flowers for your bio', date='2026-09-29', views_approx=94000, instagram_percent=85.69,
         likes=196, reposts=64, replies=0, quotes=1, follows=30),
]


def read_db(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def date(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def metrics(text):
    lines = text.splitlines()
    return dict(codepoints=len(text), utf16=len(text.encode('utf-16-le')) // 2,
                lines=len(lines), nonempty_lines=sum(bool(s.strip()) for s in lines),
                max_cells=max(map(display_cells, lines), default=0),
                whitespace_ratio=round(sum(c.isspace() for c in text) / max(len(text), 1), 4),
                length_bucket=('under100' if len(text) < 100 else '100to179' if len(text) < 180
                               else '180to279' if len(text) < 280 else '280plus'))


def summarize(rows):
    views = sum(r['views'] for r in rows)
    reactions = sum(sum(r.get(k) or 0 for k in ('likes','reposts','shares','replies','quotes')) for r in rows)
    return dict(n=len(rows), total_views=views,
                median_views=statistics.median(r['views'] for r in rows) if rows else None,
                mean_views=round(views / len(rows), 1) if rows else None,
                over10k=sum(r['views'] >= 10000 for r in rows),
                over100k=sum(r['views'] >= 100000 for r in rows),
                reactions=reactions,
                reactions_per1000=round(reactions / views * 1000, 3) if views else None,
                reshares_per1000=round(sum((r.get('reposts') or 0)+(r.get('shares') or 0)
                                         for r in rows) / views * 1000, 3) if views else None)


def grouped(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {label:summarize(items) for label,items in sorted(groups.items())}


def analyze(analytics_path, schedule_path, current):
    with read_db(analytics_path) as db, read_db(schedule_path) as queue:
        run=db.execute("SELECT * FROM sync_runs WHERE status='completed' ORDER BY id DESC LIMIT 1").fetchone()
        if not run:
            raise ValueError('No completed analytics sync')
        snapshot_at=run['started_at']
        snapshot_time=date(snapshot_at)
        if current-snapshot_time > timedelta(days=1):
            raise ValueError('Analytics snapshot is older than 24 hours')
        jobs={r['post_id']:dict(r) for r in queue.execute('SELECT * FROM jobs WHERE post_id IS NOT NULL')}
        experiments={r['job_id']:dict(r) for r in queue.execute('SELECT * FROM experiment_jobs')}
        raw=db.execute('''SELECT p.*,s.views,s.likes,s.replies,s.reposts,s.quotes,s.shares,s.error_code
                          FROM posts p JOIN insight_snapshots s ON p.post_id=s.post_id
                          WHERE s.collected_at=? AND p.username=?''',
                       (snapshot_at,'cute.__.emoji')).fetchall()
        start=current-timedelta(days=14)
        selected=[dict(r) for r in raw if r['posted_at'] and start <= date(r['posted_at']) <= current]
        missing=sum(r['views'] is None or r['error_code'] is not None for r in selected)
        rows=[]
        for post in selected:
            if post['views'] is None or post['error_code'] is not None:
                continue
            text=post['text'] or ''
            job=jobs.get(post['post_id'])
            experiment=json.loads(experiments[job['id']]['metadata']) if job and job['id'] in experiments else {}
            title=next((s.strip() for s in text.splitlines() if s.strip()), '')
            item={k:post[k] for k in ('post_id','posted_at','permalink','views','likes','replies','reposts','quotes','shares')}
            item.update(text=text, title=title, theme=job['theme'] if job else title,
                        format=experiment.get('format') or experiment.get('experiment') or 'unmapped',
                        automated=bool(job), age_hours=round((snapshot_time-date(post['posted_at'])).total_seconds()/3600,2),
                        **metrics(text))
            rows.append(item)
        mature=[r for r in rows if r['age_hours'] >= 72]
        age_rows={}
        for target,low,high in ((24,18,30),(72,60,84)):
            comparable=[]
            for post in rows:
                points=db.execute('''SELECT collected_at,views,likes,reposts,shares,replies,quotes
                                     FROM insight_snapshots WHERE post_id=? AND views IS NOT NULL
                                     AND error_code IS NULL ORDER BY collected_at''',(post['post_id'],)).fetchall()
                candidates=[r for r in points if low <= (date(r['collected_at'])-date(post['posted_at'])).total_seconds()/3600 <= high]
                if not candidates:
                    continue
                best=min(candidates,key=lambda r:abs((date(r['collected_at'])-date(post['posted_at'])).total_seconds()/3600-target))
                measured=dict(post)
                measured.update({k:best[k] for k in ('views','likes','reposts','shares','replies','quotes')})
                measured['measurement_age_hours']=round((date(best['collected_at'])-date(post['posted_at'])).total_seconds()/3600,2)
                comparable.append(measured)
            age_rows[str(target)]=dict(window_hours=[low,high],n=len(comparable),
                                      by_theme=grouped(comparable,'theme'),by_format=grouped(comparable,'format'),
                                      by_length=grouped(comparable,'length_bucket'),
                                      top=sorted(comparable,key=lambda r:r['views'],reverse=True)[:10])
        for evidence in USER_EVIDENCE:
            evidence['source']='user-provided Threads Insights; displayed views rounded'
            evidence['follows_per1000']=round(evidence['follows']/evidence['views_approx']*1000,4)
            evidence['reactions_per1000']=round(sum(evidence[k] for k in ('likes','reposts','replies','quotes'))/evidence['views_approx']*1000,4)
        return dict(account='cute.__.emoji', analyzed_at=current.isoformat(),
                    start=start.isoformat(),end=current.isoformat(),snapshot_at=snapshot_at,
                    sync=dict(run),posts_in_window=len(selected),missing_views=missing,
                    cumulative=summarize(rows),mature_cumulative=summarize(mature),
                    by_theme=grouped(mature,'theme'),by_format=grouped(mature,'format'),
                    by_length=grouped(mature,'length_bucket'),age_snapshots=age_rows,
                    top=sorted(rows,key=lambda r:r['views'],reverse=True)[:20],posts=rows,
                    user_evidence=USER_EVIDENCE,
                    limitations=['Observational analysis, not randomized causal results.',
                                 'Views are cumulative at snapshot age; matched windows are 18-30h and 60-84h, not exact 24h/72h.',
                                 'Instagram source percentages and follows are user-provided for five examples only; API collects no source breakdown.',
                                 'September 16/17 examples are outside the recent 14-day analysis and used only as reference formats.'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--analytics',type=Path,default=ROOT/'runtime'/'threads_analytics.sqlite3')
    parser.add_argument('--schedule',type=Path,default=ROOT/'runtime'/'schedule.sqlite3')
    parser.add_argument('--output',type=Path,default=ROOT/'runtime'/'monthly_analysis.json')
    args=parser.parse_args()
    report=analyze(args.analytics,args.schedule,datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    brief={k:report[k] for k in ('start','end','snapshot_at','posts_in_window','missing_views',
                              'cumulative','mature_cumulative','by_theme','by_format','by_length')}
    brief['age_snapshots']={age:{k:v for k,v in group.items() if k!='top'}
                           for age,group in report['age_snapshots'].items()}
    print(json.dumps(brief,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()

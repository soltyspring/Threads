"""Instagram-discovery experiments in an isolated lovely._.symbol queue."""
import argparse
import json
import math
import os
import random
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import threads_schedule as shared
from apply_competitor_campaign import digest, known_texts
from campaign_analysis import metrics, read_db
from competitor_formats import display_cells
from monthly_campaign import BASE_THEME, Diversity, TITLES, make_pools
from threads_emoji_poster import get_profile

ROOT=Path(__file__).resolve().parent
USER='lovely._.symbol'
DB=ROOT/'runtime'/'lovely_schedule.sqlite3'
JSON_QUEUE=ROOT/'runtime'/'lovely_schedule.json'
PLAN=ROOT/'runtime'/'lovely_experiment_plan.json'
ANALYTICS=ROOT/'runtime'/'lovely_analytics.sqlite3'
VERSION='lovely-instagram-lab-v1'
FACTORS=('length','columns','spacing','linebreaks','headline','title_wording',
         'order','indent','line_width','composition')
EXPLORERS=('mini_scene','symmetry','emoji_mix','ultra_compact')


def token_and_profile():
    token=os.getenv('THREADS_ACCESS_TOKEN_LOVELY','')
    if not token:
        raise ValueError('THREADS_ACCESS_TOKEN_LOVELY is missing')
    profile=get_profile(token)
    if profile.get('username')!=USER:
        raise ValueError('Lovely token account mismatch')
    return token,profile


def export_json(db):
    shared.export_json(db,JSON_QUEUE,account=USER)


def render(theme,items,title,columns=3,gap='　',blank=False,indent='',width=40):
    rows=[]
    row=[]
    for item in items:
        if display_cells(indent+item)>width:
            raise ValueError('Item exceeds width budget')
        if row and (len(row)>=columns or display_cells(indent+gap.join(row+[item]))>width):
            rows.append(indent+gap.join(row));row=[]
        row.append(item)
    if row:rows.append(indent+gap.join(row))
    text=(title+'\n\n' if title else '')+('\n\n' if blank else '\n').join(rows)
    features=metrics(text)
    if features['utf16']>450 or features['lines']>20:
        raise ValueError('Experimental content exceeds rendering budget')
    return dict(theme=BASE_THEME[theme],theme_key=theme,text=text,items=list(items),title=title,
                columns=columns,gap=gap,blank_lines=blank,indent=indent,width_budget=width,**features)


def pair(theme,factor,pools,rng,pair_id):
    source=rng.sample(pools[theme],24)
    items=source[:12]
    title=TITLES[theme][0]
    a=dict(items=items,title=title)
    b=dict(items=items,title=title)
    if factor=='length':a['items']=source[:8];b['items']=source
    elif factor=='columns':a['columns']=2;b['columns']=4
    elif factor=='spacing':a['gap']=' ';b['gap']='　　'
    elif factor=='linebreaks':b['blank']=True
    elif factor=='headline':b['title']=''
    elif factor=='title_wording':b['title']=TITLES[theme][2]
    elif factor=='order':b['items']=sorted(items,key=lambda item:(display_cells(item),item))
    elif factor=='indent':b['indent']='　　'
    elif factor=='line_width':a.update(columns=6,width=16);b.update(columns=6,width=40)
    elif factor=='composition':
        expressions=rng.sample(pools['faces'],12)
        b['items']=[f'{symbol} {face}' for symbol,face in zip(items,expressions)]
    output=[]
    for arm,conditions in zip(('A','B'),(a,b)):
        post=render(theme,**conditions)
        output.append(dict(post,arm=arm,pair_id=pair_id,experiment=factor,format='paired_'+factor,
                           design='multivariate_exploratory' if factor=='composition' else 'single_factor',
                           controlled_factor=None if factor=='composition' else factor,
                           objective='instagram_discovery',preview_lines=post['text'].splitlines()[:4],
                           causal_limit='Organic recommendation exposure is not randomized; compare matched-age within-account outcomes.'))
    if output[0]['text']==output[1]['text']:
        raise ValueError('Experimental arms do not differ')
    return output


def explorer(theme,style,pools,rng):
    symbols=rng.sample(pools[theme],8)
    faces=rng.sample(pools['faces'],4)
    title=TITLES[theme][0]
    if style=='mini_scene':
        items=[f'╭─ {symbols[0]} ─╮',f'{symbols[1]} {faces[0]} {symbols[2]}',
               f'╰─ {symbols[3]} ─╯',f'{symbols[4]} 𓂃 {symbols[5]}',f'{symbols[6]} {symbols[7]}']
        post=render(theme,items,title,columns=1)
    elif style=='symmetry':
        items=[f'{symbols[i]} {face} {symbols[i]}' for i,face in enumerate(faces)]
        post=render(theme,items,title,columns=1,blank=True)
    elif style=='emoji_mix':
        color=rng.sample(('🎀','🫧','🌷','🌙','🪷','🧸','🎧','🍓','🦋','🐚','🪽','🪻'),4)
        items=[f'{emoji} {symbols[i]} {face} {symbols[i+4]}'
               for i,(emoji,face) in enumerate(zip(color,faces))]
        post=render(theme,items,title,columns=1)
    else:
        post=render(theme,[symbols[0],faces[0],symbols[1],symbols[2],faces[1],symbols[3]],'',columns=3)
    return dict(post,arm=None,pair_id=None,experiment=style,format=style,design='exploratory',
                objective='instagram_discovery',preview_lines=post['text'].splitlines()[:4],
                causal_limit='No matched control; use as discovery candidate, not isolated causal evidence.')


def build_posts(excluded,seed):
    pools=make_pools({'top':[]})
    themes=list(BASE_THEME)
    diversity=Diversity(excluded)
    exact=set(excluded)
    posts=[]
    for day in range(30):
        families=[]
        factors=list(FACTORS)
        random.Random(f'{seed}:factors:{day}').shuffle(factors)
        for i in range(10):
            theme=themes[(day*10+i)%12]
            factor=factors[i]
            pair_id=f'{seed}:day{day+1}:{theme}:{factor}'
            for attempt in range(2000):
                rng=random.Random(f'{VERSION}:{pair_id}:{attempt}')
                try:arms=pair(theme,factor,pools,rng,pair_id)
                except ValueError:continue
                if any(p['text'] in exact or diversity.overlap(diversity.signatures(p['text'])) for p in arms):
                    continue
                # Matched arms intentionally retain the same raw symbols to isolate
                # a formatting factor. Novelty checks compare against other families.
                for post in arms:
                    exact.add(post['text']);diversity.add(post['text'])
                families.append(arms)
                break
            else:raise ValueError(f'Cannot build a new experimental pair: {pair_id}')
        for i in range(2):
            theme=themes[(day*10+10+i)%12]
            unpaired=[]
            for half in range(2):
                style=EXPLORERS[(day+i*2+half)%4]
                for attempt in range(2000):
                    rng=random.Random(f'{VERSION}:{seed}:explore:{day}:{i}:{half}:{attempt}')
                    try:post=explorer(theme,style,pools,rng)
                    except ValueError:continue
                    if post['text'] in exact or diversity.overlap(diversity.signatures(post['text'])):continue
                    exact.add(post['text']);diversity.add(post['text']);unpaired.append(post);break
                else:raise ValueError('Cannot build a fresh exploratory post')
            families.append(unpaired)
        random.Random(f'{seed}:slots:{day}').shuffle(families)
        first=[];second=[]
        for arms in families:
            # Alternate A-first/B-first for each factor across days.
            if arms[0]['pair_id'] and day%2:arms.reverse()
            first.append(arms[0]);second.append(arms[1])
        for slot,post in enumerate(first+second):
            posts.append(dict(post,day=day+1,slot=slot,version=VERSION,
                              pair_gap_hours=12 if post['pair_id'] else None))
    return posts


def prepare(db,current,excluded):
    rows=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id')]
    if any(r['state'] in ('processing','uncertain','failed') for r in rows):
        raise ValueError('Lovely queue has an unresolved publication')
    first=current.replace(minute=30,second=0,microsecond=0)
    if first-current<timedelta(minutes=15):first+=timedelta(hours=1)
    phase='lovely-instagram-lab-'+current.strftime('%Y%m%dT%H%M%SZ')
    excluded=set(excluded)|known_texts(db)
    posts=build_posts(excluded,phase)
    for index,post in enumerate(posts):post['due']=(first+timedelta(hours=index)).isoformat()
    return dict(phase=phase,account=USER,created_at=current.isoformat(),queue_digest=digest(rows),
                posts=posts,days=30,interval_hours=1,primary_metric='Instagram views and discovery share from native Insights',
                secondary_metrics=['total views','reposts','shares','likes','follows'],
                primary_metric_collection='Manual native Insights observations; API totals are not Instagram-specific',
                first_kst=first.astimezone(shared.KST).isoformat(),
                last_kst=(first+timedelta(hours=719)).astimezone(shared.KST).isoformat(),
                exclude_count=len(excluded),cancel_pending_ids=[r['id'] for r in rows if r['state']=='pending'],
                factor_counts=dict(Counter(p['experiment'] for p in posts)),
                design_counts=dict(Counter(p['design'] for p in posts)))


def validate(plan):
    posts=plan['posts']
    if plan['account']!=USER or len(posts)!=720 or len({p['text'] for p in posts})!=720:
        raise ValueError('Invalid lovely experimental plan')
    pairs={}
    expected_counts={**dict.fromkeys(FACTORS,60),**dict.fromkeys(EXPLORERS,30)}
    if Counter(p['experiment'] for p in posts)!=expected_counts:
        raise ValueError('Unbalanced lovely experiments')
    for i,post in enumerate(posts):
        if len(post['text'].encode('utf-16-le'))//2>450 or any(display_cells(line)>40 for line in post['text'].splitlines()):
            raise ValueError('Experimental text exceeds rendering limits')
        if i and datetime.fromisoformat(post['due'])-datetime.fromisoformat(posts[i-1]['due'])!=timedelta(hours=1):
            raise ValueError('Lovely reservations must be hourly')
        if datetime.fromisoformat(post['due']).utcoffset()!=timedelta(0):
            raise ValueError('Store lovely reservations in UTC')
        if post['pair_id']:
            pairs.setdefault(post['pair_id'],[]).append(post)
    if len(pairs)!=300:
        raise ValueError('Expected 300 matched pairs')
    for arms in pairs.values():
        if len(arms)!=2 or {p['arm'] for p in arms}!={'A','B'} or arms[0]['experiment']!=arms[1]['experiment']:
            raise ValueError('Invalid experimental pair')
        if datetime.fromisoformat(arms[1]['due'])-datetime.fromisoformat(arms[0]['due'])!=timedelta(hours=12):
            raise ValueError('Matched arms must be 12 hours apart')


def apply(db,plan,current,backup_root):
    validate(plan)
    if datetime.fromisoformat(plan['posts'][0]['due'])<=current+timedelta(minutes=2):
        raise ValueError('Stale lovely plan')
    backup=backup_root/plan['phase'];backup.mkdir(parents=True,exist_ok=False)
    with closing(sqlite3.connect(backup/'lovely_schedule.sqlite3')) as destination:db.backup(destination)
    (backup/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    db.execute('BEGIN IMMEDIATE')
    try:
        rows=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id')]
        if digest(rows)!=plan['queue_digest']:raise ValueError('Lovely queue changed; regenerate plan')
        if any(r['state'] in ('processing','uncertain','failed') for r in rows):raise ValueError('Lovely publish blocker')
        db.execute('CREATE TABLE IF NOT EXISTS experiment_jobs(job_id INTEGER PRIMARY KEY,campaign TEXT NOT NULL,metadata TEXT NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS campaign_revisions(phase TEXT PRIMARY KEY,applied_at TEXT,
                    previous_queue TEXT,previous_experiments TEXT,plan_json TEXT,reconciliation_json TEXT)''')
        db.execute('INSERT INTO campaign_revisions VALUES(?,?,?,?,?,?)',
                   (plan['phase'],current.isoformat(),json.dumps(rows,ensure_ascii=False),
                    json.dumps([dict(r) for r in db.execute('SELECT * FROM experiment_jobs')],ensure_ascii=False),
                    json.dumps(plan,ensure_ascii=False),'{}'))
        for job_id in plan['cancel_pending_ids']:
            db.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=? AND state='pending'",(current.isoformat(),job_id))
        next_id=max((r['id'] for r in rows),default=0)+1
        for i,post in enumerate(plan['posts']):
            db.execute('INSERT INTO jobs(id,due,theme,text,updated) VALUES(?,?,?,?,?)',
                       (next_id+i,post['due'],post['theme'],post['text'],current.isoformat()))
            db.execute('INSERT INTO experiment_jobs VALUES(?,?,?)',
                       (next_id+i,plan['phase'],json.dumps(post,ensure_ascii=False)))
        db.commit()
    except Exception:db.rollback();raise
    export_json(db)
    return backup


def observe(db,post_id,views,percent,follows=None,approximate=False):
    if views<0 or not math.isfinite(percent) or not 0<=percent<=100 or (follows is not None and follows<0):
        raise ValueError('Invalid Instagram observation')
    if not db.execute("SELECT 1 FROM jobs WHERE post_id=? AND state='published'",(post_id,)).fetchone():
        raise ValueError('Observation must belong to a published lovely queue post')
    db.execute('''CREATE TABLE IF NOT EXISTS instagram_observations(id INTEGER PRIMARY KEY,
                post_id TEXT NOT NULL,collected_at TEXT NOT NULL,total_views INTEGER NOT NULL,
                instagram_percent REAL NOT NULL,instagram_views_estimate REAL NOT NULL,
                follows INTEGER,approximate INTEGER NOT NULL,source TEXT NOT NULL)''')
    db.execute('INSERT INTO instagram_observations VALUES(NULL,?,?,?,?,?,?,?,?)',
               (post_id,shared.now_utc().isoformat(),views,percent,views*percent/100,follows,int(approximate),
                'user-provided native Threads Insights'))
    db.commit()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('plan','apply','run','status','check','observe'))
    parser.add_argument('--post-id');parser.add_argument('--views',type=int)
    parser.add_argument('--instagram-percent',type=float);parser.add_argument('--follows',type=int)
    parser.add_argument('--approximate',action='store_true')
    args=parser.parse_args()
    if args.command=='check':
        _,profile=token_and_profile();print(json.dumps({'username':profile['username']}));return
    with closing(shared.connect(DB)) as db:
        if args.command=='plan':
            excluded=set()
            with closing(read_db(ANALYTICS)) as analytics:
                excluded.update(r['text'] for r in analytics.execute('SELECT text FROM posts WHERE text IS NOT NULL'))
            cute_analytics=ROOT/'runtime'/'threads_analytics.sqlite3'
            if cute_analytics.exists():
                with closing(read_db(cute_analytics)) as analytics:
                    excluded.update(r['text'] for r in analytics.execute('SELECT text FROM posts WHERE text IS NOT NULL'))
            for queue_path in (shared.DB,):
                with closing(read_db(queue_path)) as queue:excluded.update(known_texts(queue))
            cute_plan=ROOT/'runtime'/'monthly_campaign_plan.json'
            if cute_plan.exists():
                excluded.update(p['text'] for p in json.loads(cute_plan.read_text(encoding='utf-8'))['posts'])
            plan=prepare(db,shared.now_utc(),excluded)
            PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in plan.items() if k!='posts'},indent=2))
        elif args.command=='apply':
            token_and_profile()
            plan=json.loads(PLAN.read_text(encoding='utf-8'))
            backup=apply(db,plan,shared.now_utc(),ROOT/'runtime'/'backups')
            print(json.dumps(dict(applied=len(plan['posts']),account=USER,backup=str(backup),first=plan['first_kst'],last=plan['last_kst'])))
        elif args.command=='run':
            result=shared.run_due(db,token_provider=token_and_profile,exporter=export_json)
            if result in ('failed','uncertain','blocked'):raise SystemExit(1)
        elif args.command=='observe':
            if args.post_id is None or args.views is None or args.instagram_percent is None:
                raise ValueError('Provide --post-id, --views and --instagram-percent')
            observe(db,args.post_id,args.views,args.instagram_percent,args.follows,args.approximate)
            print(json.dumps({'recorded':args.post_id,'account':USER}))
        else:print(json.dumps(shared.status(db,account=USER)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR: '+type(exc).__name__+'; credentials omitted');raise SystemExit(1)

"""Evidence-led 30-day original text campaign with reviewable plans and backups."""
import argparse
import hashlib
import json
import random
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import threads_schedule as schedule
from apply_competitor_campaign import digest, known_texts
from campaign_analysis import metrics, read_db
from competitor_formats import display_cells
from weekly_content import POOLS

ROOT=Path(__file__).resolve().parent
PLAN=ROOT/'runtime'/'monthly_campaign_plan.json'
VERSION='monthly-originals-v1'
GAP='　'
MAX_CELLS=40
SIMILARITY_LIMIT=0.72
EXTRA = {
    'flowers':'𓇢|𓋼|𓋼𓍊|𓆹|𓇚|𓇬|𓇣|✻|✼|❋|ꕥ|❊|𖤣|𖥣|❦|❧|⚘|𑁍|˖𑁍|𓆱',
    'bows':'𓍼|੭̲᱖|𝞋𝞎|ꪆ୧|໑𓏲|𝝑𓏲|𝝑𝝔|𝝑𝑒|ᖭི༏ᖫྀ|ೀ|၄၃|ꪮ౿|᧔𑄸|୨˚̣̣̣୧|꒰ა|໒꒱|𝒞𝓊|᱖੭|୨୧ྀི|୨୧₊|𝟅𝟈',
    'faces':'𐔌՞ ܸ.ˬ.ܸ ՞𐦯|՞߹ - ߹՞|•̩̩̩̩ᯅ•̩̩̩|˙꒳˙|ᵔ⤙ᵔ|˃̶͈ ᗜ ˂̶͈|˶ᵔᗜᵔ˶|•̀ᴗ•́|˶˙ᵕ˙˶|˶˘ ᵕ ˘˶|˃ ᵕ ˂|˙ꇴ˙|˶ˊᵕˋ˶|˘͈ᵕ˘͈|˶ᵕᴗᵕ˶|˶ᵒ ᵕ ᵒ˶|ᵔ ᵕ ᵔ|˙𐃷˙|˃̵⤙˂̵|ᵔᵕᵔ|˃⤙˂|꒰˶ᵔᵕᵔ˶꒱|˶˃ ᵕ ˂˶|˶˙ ᵕ ˙˶',
    'ocean':'𓆡|𓆜|𓆛|𓆢|𓇻|𓇽|𓇳|𓇲|𓈓|𓈖|𓂁|≈|∿|⌁|〰︎|⊹|⟡|⋆|☽|☼|⚓︎|𓆤',
    'music':'♮|♭|♯|𝄡|𝄐|𝄑|𝄆|𝄇|𝄋|𝄌|𝄪|𝄫|♬︎|♫︎|♪︎|♩︎|♬ ˚|♪ ♡|♫ ✧|ᕷ ⋆|𝄞 ⊹|♩ ⟡',
    'cats':'ᐟᐠ|ฅ˙Ⱉ˙ฅ|≽^•⩊•^≼|/ᐠ˵- ⩊ -˵マ|≽^⸝⸝> ᴗ <⸝⸝^≼|₍˄·͈༝·͈˄₎|₍^ >ヮ<^₎|/ᐠ｡ꞈ｡ᐟ|ฅ^•ﻌ•^ฅ|≽^• ﻌ •^≼|ฅ^˶･֊･˶^ฅ|₍^ ˕ ^₎|₍^•ﻌ•^₎|₍^⸝⸝•⩊•⸝⸝^₎|ฅ^◡^ฅ|₍^._.^₎ﾉ',
    'stars':'✵|✶|✷|✸|✹|✺|✫|✬|✭|✯|✰|⁕|∗|⭑|☄︎|☼|☽|☁︎|𖤓',
    'hearts':'♥︎|❣︎|❦|❧|ლ|♡̷|♡₊|♡꙼̈|დ|ᢉ𐭩|ᡣᰔ|ෆ̈|ෆ₊|ᥫ᭡₊|ᰔ₊|ღ₊',
    'bunnies':'ᕱᕱ|ᘏᘏ|₍ᐢ˶˙ᵕ˙˶ᐢ₎|꒰ᐢ˶ᵔᵕᵔ˶ᐢ꒱|₍ᐢ> ̫<ᐢ₎|₍ᐢ˘ˬ˘ᐢ₎|₍ᐢᵔ ᵕ ᵔᐢ₎|₍ᐢ. .ᐢ₎|꒰ᐢ˙ᵕ˙ᐢ꒱|₍ᐢ˶•ᴗ•˶ᐢ₎|₍ᐢ˶>ᴗ<˶ᐢ₎|ᕱ⑅ᕱ♡',
    'moods':'˃ 𖥦 ˂|˘•̥-•̥˘|՞ ̥_ ̫ _ ̥՞|•᷄ࡇ•᷅|˶•⤙•˶|˃̶ᗝ˂̶|˙ᯅ˙|•᷄⌓•᷅|˶°ㅁ°˶|˶¬_¬˶|ᗒᗣᗕ|˶•̀⤙•́˶|˘︶˘|ᵕ̩̩ㅅᵕ̩̩|˙ε˙|•̀⩊•́',
    'decorations':'☏|⌨︎|𓁹|🜲|𖠚ᐝ|༆|𓆱|𓊆|𓊇|𓆩|𓆪|ᯓ|ᝰ|✎|⌗|ᜊ|𓍢|𖦹|꩜|𓇼',
}
BASE_THEME={'flowers':'Flower garden','bows':'Little bows','faces':'Cute face collection',
            'ocean':'Little ocean','music':'Music for your bio','cats':'Sleepy little cats',
            'stars':'Tiny stars','hearts':'Little hearts','bunnies':'Soft bunny faces',
            'moods':'Tiny mood faces','decorations':'Soft tiny decorations','happy':'Tiny happy faces'}
TITLES={
    'flowers':['flower symbols','little flower garden','flowers for your bio','soft floral symbols','tiny flowers'],
    'bows':['ribbons symbol','bow symbols','little ribbons','bows for your bio','soft ribbon collection'],
    'faces':['cute emoji','tiny reactions','little happy faces','soft mood collection','cute faces for your bio'],
    'ocean':['ocean symbols','little ocean','sea symbols for your bio','tiny seaside symbols','soft ocean collection'],
    'music':['music symbols','little playlist symbols','music for your bio','tiny melody','soft music collection'],
    'cats':['cat emoji','tiny cat faces','little sleepy cats','cats for your bio','soft cat collection'],
    'stars':['star symbols','little sky symbols','stars for your bio'],
    'hearts':['heart symbols','little hearts','hearts for your bio'],
    'bunnies':['bunny emoji','little bunny faces','soft bunny collection'],
    'moods':['tiny mood faces','little reactions','soft moods'],
    'decorations':['cute symbols','little bio decorations','soft symbols'],
    'happy':['happy emoji','tiny happy faces','little smiles'],
}
ACCENTS=('✧','⊹','♡','⋆','˚','⟡','୨୧','˖','𓂃','𓈒','𐙚','₊')


def canonical(text):
    text=unicodedata.normalize('NFKC',text)
    return ''.join(c for c in text if not c.isspace() and unicodedata.category(c)!='Cf'
                   and c not in ('\ufe0e','\ufe0f'))


def atoms(text):
    return [x.strip() for x in re.split(r'[　\n\t]+| {2,}',text)
            if x.strip() and not re.search(r'[a-zA-Z]{3}',x)]


class Diversity:
    """Index content sets and five-character shingles, ignoring English titles."""
    def __init__(self, texts=()):
        self.exact=set()
        self.sets=[]
        self.index=defaultdict(set)
        for text in texts:
            self.add(text)

    def signatures(self,text):
        content=[canonical(x) for x in atoms(text)]
        body=''.join(content)
        symbols=frozenset(content)
        shingles=frozenset(body[i:i+5] for i in range(max(len(body)-4,0)))
        return body,symbols,shingles

    def overlap(self,signatures,limit=SIMILARITY_LIMIT):
        body,symbols,shingles=signatures
        if body in self.exact:
            return True
        candidates=set()
        for label,values in (('a',symbols),('s',shingles)):
            for value in values:
                candidates.update(self.index.get((label,value),()))
        for i in candidates:
            other_symbols,other_shingles=self.sets[i]
            for left,right in ((symbols,other_symbols),(shingles,other_shingles)):
                if left and right and len(left&right)/len(left|right) >= limit:
                    return True
        return False

    def add(self,text,signatures=None):
        body,symbols,shingles=signatures or self.signatures(text)
        self.exact.add(body)
        i=len(self.sets)
        self.sets.append((symbols,shingles))
        for label,values in (('a',symbols),('s',shingles)):
            for value in values:
                self.index[(label,value)].add(i)


def make_pools(report):
    pools={key:list(dict.fromkeys(POOLS[theme].split('|')+EXTRA.get(key,EXTRA['faces']).split('|')))
           for key,theme in BASE_THEME.items()}
    # Reuse common glyphs from this account's strongest recent posts, never the full post.
    for post in report['top']:
        for key,theme in BASE_THEME.items():
            if post['theme']==theme:
                for item in atoms(post['text']):
                    # Keep raw symbols/expressions rather than repeatedly wrapping
                    # a previously decorated snippet inside new decoration.
                    if any(c.isspace() for c in item) and key not in ('faces','cats','bunnies','moods','happy'):
                        continue
                    if item.startswith(ACCENTS) or item.endswith(ACCENTS):
                        continue
                    if 0 < display_cells(item) <= 22 and len(item)<=32 and item not in pools[key]:
                        pools[key].append(item)
    pools['faces']=list(dict.fromkeys(pools['faces']+pools['happy']+pools['moods']+pools['bunnies'][:6]))
    for key,values in pools.items():
        seen=set()
        distinct=[]
        for value in values:
            normalized=canonical(value)
            if normalized not in seen:
                seen.add(normalized);distinct.append(value)
        pools[key]=distinct
    return pools


def daily_slots(day, previous, seed):
    slots=[]
    for theme,expanded,mixed,compact in (('flowers',2,2,1),('bows',3,1,1),('faces',0,4,0),
                                        ('ocean',2,0,1),('music',2,0,1),('cats',1,1,0)):
        slots += [(theme,'expanded')]*expanded+[(theme,'mixed')]*mixed+[(theme,'compact')]*compact
    exploration=('stars','hearts','bunnies','moods','decorations','happy')
    slots += [(exploration[(day*2+i)%6],'expanded') for i in range(2)]
    rng=random.Random(f'{seed}:order:{day}')
    for attempt in range(1000):
        remaining=list(slots)
        ordered=[]
        last=list(previous[-2:])
        while remaining:
            candidates=[i for i,s in enumerate(remaining) if s[0] not in last[-2:]]
            if not candidates:
                break
            counts=Counter(theme for theme,_ in remaining)
            pick=max(candidates,key=lambda i:counts[remaining[i][0]]+rng.random()*3)
            slot=remaining.pop(pick)
            ordered.append(slot)
            last.append(slot[0])
        if not remaining:
            return ordered
    raise ValueError('Cannot distribute daily themes')


def decorate(item,rng):
    left,right=rng.sample(ACCENTS,2)
    return rng.choice((f'{left} {item} {right}',f'{item} {left}',f'{left} {item}',
                       f'{item} 𓂃 {right}',f'{left} {item} {left}'))


def candidate(theme,style,pools,rng,index):
    pool=pools[theme]
    if style=='expanded':
        raw=rng.sample(pool, rng.choice((12,14,16)))
        items=raw+[decorate(item,rng) for item in rng.sample(raw,rng.choice((6,8,10)))]
        columns=rng.choice((3,3,4))
        blank=False
    elif style=='mixed' and theme=='faces':
        faces=rng.sample(pools['faces'],rng.choice((9,11,13)))
        symbols=rng.sample(pools['decorations']+pools['flowers']+pools['stars'],rng.choice((9,11)))
        items=[]
        while faces or symbols:
            if symbols: items.append(symbols.pop())
            if faces: items.append(faces.pop())
        columns=rng.choice((4,5))
        blank=bool(index%3)
    elif style=='mixed':
        raw=rng.sample(pool,rng.choice((9,10,12)))
        faces=rng.sample(pools['faces'],len(raw))
        items=[f'{item} {face} {rng.choice(ACCENTS)}' for item,face in zip(raw,faces)]
        columns=2
        blank=False
    else:
        raw=rng.sample(pool,8)
        items=[f'{raw[i]} {rng.choice(ACCENTS)} {raw[i+4]}' for i in range(4)]
        columns=1
        blank=False
    unique={}
    for item in items:
        unique.setdefault(canonical(item),item)
    items=list(unique.values())
    gap=rng.choice((GAP,GAP,'　　'))
    rows=[]
    current=[]
    for item in items:
        if display_cells(item)>MAX_CELLS:
            raise ValueError('Item exceeds width budget')
        if current and (len(current)>=columns or display_cells(gap.join(current+[item]))>MAX_CELLS):
            rows.append(gap.join(current));current=[]
        current.append(item)
    if current: rows.append(gap.join(current))
    title=rng.choice(TITLES[theme])
    if style=='compact' and index%4==0:
        title=''
    body=('\n\n' if blank else '\n').join(rows)
    text=(title+'\n\n' if title else '')+body
    features=metrics(text)
    if features['utf16']>450 or features['lines']>16 or len(rows)<3:
        return None
    return dict(theme=BASE_THEME[theme],theme_key=theme,format=style,text=text,items=items,
                title=title,columns=columns,gap=gap,blank_lines=blank,**features,
                objective='discovery' if style=='expanded' else 'reaction_conversion' if style=='mixed' else 'reuse',
                experiment='monthly_multivariate',causal_limit='Allocation is a strategic hypothesis, not a causal algorithm rule.')


def build_posts(report,excluded,seed,days=30):
    pools=make_pools(report)
    diversity=Diversity(excluded)
    output=[]
    previous=[]
    for day in range(days):
        for theme,style in daily_slots(day,previous,seed):
            index=len(output)
            for attempt in range(2000):
                rng=random.Random(f'{VERSION}:{seed}:{index}:{attempt}')
                post=candidate(theme,style,pools,rng,index)
                if not post:
                    continue
                signatures=diversity.signatures(post['text'])
                if diversity.overlap(signatures):
                    continue
                diversity.add(post['text'],signatures)
                output.append(dict(post,day=day+1,slot=index%24,version=VERSION,attempt=attempt))
                previous.append(theme)
                break
            else:
                raise ValueError(f'Unable to generate diverse content for slot {index}')
    return output


def prepare(db,analytics_path,report,current):
    if current-datetime.fromisoformat(report['snapshot_at'])>timedelta(days=1):
        raise ValueError('Refresh recent analytics before preparing a monthly campaign')
    rows=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id')]
    if any(r['state'] in ('processing','uncertain','failed') for r in rows):
        raise ValueError('Resolve active publish blockers before creating a monthly campaign')
    excluded=known_texts(db)
    with read_db(analytics_path) as analytics:
        excluded.update(r['text'] for r in analytics.execute('SELECT text FROM posts WHERE text IS NOT NULL'))
    first=(current+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
    if first-current<timedelta(minutes=10): first+=timedelta(hours=1)
    phase='monthly-'+current.strftime('%Y%m%dT%H%M%SZ')
    posts=build_posts(report,excluded,phase)
    for i,post in enumerate(posts):
        post['due']=(first+timedelta(hours=i)).isoformat()
    return dict(phase=phase,account=schedule.EXPECTED_USER,queue_digest=digest(rows),created_at=current.isoformat(),
                interval_hours=1,days=30,posts=posts,cancel_pending_ids=[r['id'] for r in rows if r['state']=='pending'],
                first_kst=first.astimezone(schedule.KST).isoformat(),
                last_kst=(first+timedelta(hours=719)).astimezone(schedule.KST).isoformat(),
                source_snapshot=report['snapshot_at'],source_window=[report['start'],report['end']],
                historical_texts=len(excluded),diversity_limit=SIMILARITY_LIMIT,
                allocation=dict(Counter(p['format'] for p in posts)),
                themes=dict(Counter(p['theme_key'] for p in posts)))


def validate_plan(plan):
    if plan['account']!=schedule.EXPECTED_USER or len(plan['posts'])!=720:
        raise ValueError('Invalid monthly campaign')
    if len({canonical(p['text']) for p in plan['posts']})!=720:
        raise ValueError('Campaign contains duplicate content')
    for index,post in enumerate(plan['posts']):
        if len(post['text'].encode('utf-16-le'))//2>450 or any(display_cells(line)>MAX_CELLS for line in post['text'].splitlines()):
            raise ValueError('Campaign exceeds content limits')
        if index and datetime.fromisoformat(post['due'])-datetime.fromisoformat(plan['posts'][index-1]['due'])!=timedelta(hours=1):
            raise ValueError('Campaign must have hourly reservations')


def apply(db,plan,current,backup_root):
    validate_plan(plan)
    if datetime.fromisoformat(plan['posts'][0]['due'])<=current+timedelta(minutes=2):
        raise ValueError('Stale plan; regenerate it')
    backup=backup_root/plan['phase']
    backup.mkdir(parents=True,exist_ok=False)
    with closing(sqlite3.connect(backup/'schedule.sqlite3')) as destination:
        db.backup(destination)
    (backup/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    db.execute('BEGIN IMMEDIATE')
    try:
        rows=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id')]
        if digest(rows)!=plan['queue_digest']:
            raise ValueError('Queue changed; regenerate the plan')
        if any(r['state'] in ('processing','uncertain','failed') for r in rows):
            raise ValueError('Active publish blocker')
        db.execute('CREATE TABLE IF NOT EXISTS experiment_jobs(job_id INTEGER PRIMARY KEY,campaign TEXT NOT NULL,metadata TEXT NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS campaign_revisions (
            phase TEXT PRIMARY KEY,applied_at TEXT,previous_queue TEXT,
            previous_experiments TEXT,plan_json TEXT,reconciliation_json TEXT)''')
        old_exp=[dict(r) for r in db.execute('SELECT * FROM experiment_jobs')]
        db.execute('INSERT INTO campaign_revisions VALUES(?,?,?,?,?,?)',
                   (plan['phase'],current.isoformat(),json.dumps(rows,ensure_ascii=False),
                    json.dumps(old_exp,ensure_ascii=False),json.dumps(plan,ensure_ascii=False),'{}'))
        for job_id in plan['cancel_pending_ids']:
            db.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=? AND state='pending'",(current.isoformat(),job_id))
        next_id=max((r['id'] for r in rows),default=0)+1
        for index,post in enumerate(plan['posts']):
            job_id=next_id+index
            db.execute('INSERT INTO jobs(id,due,theme,text,updated) VALUES(?,?,?,?,?)',
                       (job_id,post['due'],post['theme'],post['text'],current.isoformat()))
            db.execute('INSERT INTO experiment_jobs VALUES(?,?,?)',
                       (job_id,plan['phase'],json.dumps(post,ensure_ascii=False)))
        db.commit()
    except Exception:
        db.rollback();raise
    schedule.export_json(db)
    return backup


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('plan','apply','status'))
    parser.add_argument('--analytics',type=Path,default=ROOT/'runtime'/'threads_analytics.sqlite3')
    parser.add_argument('--schedule',type=Path,default=schedule.DB)
    parser.add_argument('--report',type=Path,default=ROOT/'runtime'/'monthly_analysis.json')
    args=parser.parse_args()
    with closing(schedule.connect(args.schedule)) as db:
        if args.command=='plan':
            report=json.loads(args.report.read_text(encoding='utf-8'))
            plan=prepare(db,args.analytics,report,schedule.now_utc())
            PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in plan.items() if k!='posts'},ensure_ascii=True,indent=2))
        elif args.command=='apply':
            schedule.token_and_profile()
            plan=json.loads(PLAN.read_text(encoding='utf-8'))
            backup=apply(db,plan,schedule.now_utc(),ROOT/'runtime'/'backups')
            print(json.dumps(dict(applied=len(plan['posts']),backup=str(backup),first=plan['first_kst'],last=plan['last_kst'])))
        else:
            print(json.dumps(schedule.status(db)))


if __name__=='__main__':
    main()

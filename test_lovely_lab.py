import json
import tempfile
import unittest
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import lovely_lab as lab
import threads_schedule as shared


class LovelyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts=lab.build_posts(['old unique content'],'test-lovely-month')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.db=shared.connect(self.root/'lovely.sqlite3')
        self.current=datetime(2026,10,7,1,tzinfo=timezone.utc)
        self.export_patch=patch.object(lab,'JSON_QUEUE',self.root/'lovely.json')
        self.export_patch.start()
        self.addCleanup(self.export_patch.stop)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def plan(self):
        posts=[dict(p,due=(self.current+timedelta(minutes=30,hours=i)).isoformat())
               for i,p in enumerate(self.posts)]
        return dict(account=lab.USER,phase='test-lovely',posts=posts,
                    queue_digest=lab.digest([dict(r) for r in self.db.execute('SELECT * FROM jobs')]),
                    cancel_pending_ids=[])

    def test_balanced_month_hourly_pairs_and_counterbalanced_order(self):
        plan=self.plan()
        lab.validate(plan)
        self.assertEqual(len({p['text'] for p in self.posts}),720)
        self.assertEqual(Counter(p['theme_key'] for p in self.posts),dict.fromkeys(lab.BASE_THEME,60))
        self.assertEqual(Counter(p['design'] for p in self.posts),
                         {'single_factor':540,'multivariate_exploratory':60,'exploratory':120})
        first_arms=Counter()
        for day in range(1,31):
            daily=[p for p in self.posts if p['day']==day]
            self.assertEqual(len(daily),24)
            self.assertEqual(Counter(p['experiment'] for p in daily if p['pair_id']),dict.fromkeys(lab.FACTORS,2))
            self.assertEqual({p['experiment'] for p in daily if not p['pair_id']},set(lab.EXPLORERS))
            for p in daily[:12]:
                if p['pair_id']:first_arms[p['experiment'],p['arm']]+=1
        for factor in lab.FACTORS:
            self.assertEqual(first_arms[factor,'A'],15)
            self.assertEqual(first_arms[factor,'B'],15)

    def test_controls_change_only_intended_conditions(self):
        pairs=defaultdict(list)
        for post in self.posts:
            if post['pair_id']:pairs[post['pair_id']].append(post)
        changes={'length':{'items'},'columns':{'columns'},'spacing':{'gap'},
                 'linebreaks':{'blank_lines'},'headline':{'title'},'title_wording':{'title'},
                 'order':{'items'},'indent':{'indent'},'line_width':{'width_budget'},
                 'composition':{'items'}}
        fields=('items','title','columns','gap','blank_lines','indent','width_budget')
        for arms in pairs.values():
            a,b=sorted(arms,key=lambda p:p['arm'])
            self.assertEqual({k for k in fields if a[k]!=b[k]},changes[a['experiment']])
            if a['experiment']=='order':self.assertEqual(set(a['items']),set(b['items']))
            self.assertLessEqual(a['utf16'],450)
            self.assertLessEqual(b['max_cells'],40)

    def test_no_near_duplicates_outside_matched_pairs(self):
        index=lab.Diversity(['old unique content'])
        pairs=defaultdict(list)
        for p in self.posts:pairs[p['pair_id'] or p['text']].append(p)
        for family in pairs.values():
            for post in family:self.assertFalse(index.overlap(index.signatures(post['text'])))
            for post in family:index.add(post['text'])

    def test_apply_backs_up_exports_lovely_and_preserves_history(self):
        self.db.execute('INSERT INTO jobs(id,due,theme,text,state,post_id) VALUES(1,?,?,?,?,?)',
                        (self.current.isoformat(),'old','posted','published','old-id'))
        self.db.execute('INSERT INTO jobs(id,due,theme,text) VALUES(2,?,?,?)',
                        (self.current.isoformat(),'old','pending old'))
        self.db.commit()
        plan=self.plan();plan['cancel_pending_ids']=[2]
        backup=lab.apply(self.db,plan,self.current,self.root/'backups')
        self.assertTrue((backup/'lovely_schedule.sqlite3').exists())
        self.assertEqual(self.db.execute('SELECT state,post_id FROM jobs WHERE id=1').fetchone()[:],('published','old-id'))
        self.assertEqual(self.db.execute('SELECT state FROM jobs WHERE id=2').fetchone()[0],'cancelled')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],720)
        exported=json.loads((self.root/'lovely.json').read_text(encoding='utf-8'))
        self.assertEqual(exported['account'],lab.USER)
        self.assertEqual(exported['interval_hours'],1)
        self.assertEqual(len(exported['jobs'][2]['experiment']['preview_lines']),4)
        plan['phase']='stale'
        with self.assertRaises(ValueError):lab.apply(self.db,plan,self.current,self.root/'backups')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],720)

    def test_rejects_malformed_pair_and_wrong_account(self):
        plan=self.plan();plan['account']=shared.EXPECTED_USER
        with self.assertRaises(ValueError):lab.validate(plan)
        plan=self.plan();plan['posts'][0]['arm']='C'
        with self.assertRaises(ValueError):lab.validate(plan)

    def job(self):
        self.db.execute('INSERT INTO jobs(due,theme,text) VALUES(?,?,?)',
                        (self.current.isoformat(),'flowers','a lovely post'))
        self.db.commit()

    def test_wrong_token_stops_before_creating(self):
        self.job()
        with patch.dict(lab.os.environ,{'THREADS_ACCESS_TOKEN_LOVELY':'secret'}), \
             patch.object(lab,'get_profile',return_value={'id':'cute','username':shared.EXPECTED_USER}), \
             patch.object(shared,'create_container') as create:
            self.assertEqual(shared.run_due(self.db,self.current,lab.token_and_profile,lab.export_json),'failed')
            create.assert_not_called()
        self.assertEqual(json.loads((self.root/'lovely.json').read_text(encoding='utf-8'))['account'],lab.USER)

    def test_success_uses_lovely_callback_never_repeats(self):
        self.job()
        with patch.dict(lab.os.environ,{'THREADS_ACCESS_TOKEN_LOVELY':'lovely-secret'}), \
             patch.object(lab,'get_profile',return_value={'id':'lovely','username':lab.USER}), \
             patch.object(shared,'token_and_profile',side_effect=AssertionError('Cute auth used')), \
             patch.object(shared,'create_container',return_value='container') as create, \
             patch.object(shared,'wait_for_container'), \
             patch.object(shared,'publish_container',return_value='post') as publish:
            self.assertEqual(shared.run_due(self.db,self.current,lab.token_and_profile,lab.export_json),'published')
            self.assertEqual(shared.run_due(self.db,self.current,lab.token_and_profile,lab.export_json),'idle')
            create.assert_called_once_with('a lovely post','lovely-secret','lovely')
            publish.assert_called_once_with('container','lovely-secret','lovely')

    def test_uncertain_lovely_publish_does_not_block_cute_queue(self):
        self.job()
        with patch.object(shared,'create_container',return_value='container'), \
             patch.object(shared,'wait_for_container'), \
             patch.object(shared,'publish_container',side_effect=TimeoutError('secret')) as publish:
            auth=lambda:('secret',{'id':'lovely'})
            self.assertEqual(shared.run_due(self.db,self.current,auth,lab.export_json),'uncertain')
            self.assertEqual(shared.run_due(self.db,self.current,auth,lab.export_json),'blocked')
            publish.assert_called_once()
        with closing(shared.connect(self.root/'cute.sqlite3')) as cute:
            self.assertEqual(shared.run_due(cute,self.current),'idle')
        self.assertEqual(self.db.execute('SELECT error FROM jobs').fetchone()[0],'TimeoutError')

    def test_manual_instagram_values_are_not_api_totals(self):
        self.job()
        self.db.execute("UPDATE jobs SET state='published',post_id='post'");self.db.commit()
        lab.observe(self.db,'post',570000,98.83,follows=90,approximate=True)
        row=self.db.execute('SELECT * FROM instagram_observations').fetchone()
        self.assertAlmostEqual(row['instagram_views_estimate'],563331)
        self.assertEqual(row['approximate'],1)
        self.assertIn('user-provided',row['source'])
        with self.assertRaises(ValueError):lab.observe(self.db,'wrong',1,90)
        with self.assertRaises(ValueError):lab.observe(self.db,'post',1,101)
        with self.assertRaises(ValueError):lab.observe(self.db,'post',1,float('nan'))


if __name__=='__main__':unittest.main()

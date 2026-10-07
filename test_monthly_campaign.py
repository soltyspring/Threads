import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import monthly_campaign as m


class MonthlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts=m.build_posts({'top':[]},[], 'test-monthly')

    def test_month_diversity_and_rendering_constraints(self):
        self.assertEqual(len(self.posts),720)
        self.assertEqual(Counter(p['format'] for p in self.posts),{'expanded':360,'mixed':240,'compact':120})
        index=m.Diversity()
        for i,post in enumerate(self.posts):
            self.assertFalse(index.overlap(index.signatures(post['text'])))
            index.add(post['text'])
            self.assertLessEqual(post['utf16'],450)
            self.assertLessEqual(post['max_cells'],40)
            self.assertNotIn(post['theme_key'],[p['theme_key'] for p in self.posts[max(0,i-2):i]])

    def test_title_spacing_and_reordered_symbols_are_not_new_content(self):
        old='flower symbols\n\n❀　ꕤ　❁\n❃　✾　✿'
        index=m.Diversity([old])
        for changed in ('New flowers\n\n❀ ꕤ ❁ ❃ ✾ ✿',
                        'Flower bio\n\n✿　✾　❃\n❁　ꕤ　❀'):
            self.assertTrue(index.overlap(index.signatures(changed)))

    def test_apply_preserves_history_backs_up_and_detects_queue_race(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            db=m.schedule.connect(root/'schedule.sqlite3')
            current=datetime(2026,10,7,1,tzinfo=timezone.utc)
            db.execute('INSERT INTO jobs(id,due,theme,text,state,post_id) VALUES(1,?,?,?,?,?)',
                       (current.isoformat(),'old','posted','published','post1'))
            db.execute('INSERT INTO jobs(id,due,theme,text,state) VALUES(2,?,?,?,?)',
                       ((current+timedelta(hours=1)).isoformat(),'old','old pending','pending'))
            db.commit()
            rows=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY id')]
            posts=[dict(p,due=(current+timedelta(hours=i+1)).isoformat()) for i,p in enumerate(self.posts)]
            plan=dict(phase='test-monthly',account=m.schedule.EXPECTED_USER,posts=posts,
                      queue_digest=m.digest(rows),cancel_pending_ids=[2])
            original=m.schedule.export_json
            from unittest.mock import patch
            with patch.object(m.schedule,'export_json',side_effect=lambda d:original(d,root/'schedule.json')):
                backup=m.apply(db,plan,current,root/'backups')
            self.assertTrue((backup/'schedule.sqlite3').exists())
            self.assertEqual(db.execute('SELECT state,post_id FROM jobs WHERE id=1').fetchone()[:],('published','post1'))
            self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=2').fetchone()[0],'cancelled')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],720)
            exported=json.loads((root/'schedule.json').read_text(encoding='utf-8'))
            self.assertEqual(exported['interval_hours'],1)
            plan['phase']='stale-monthly'
            with self.assertRaises(ValueError):m.apply(db,plan,current,root/'backups')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],720)
            db.close()


if __name__=='__main__':
    unittest.main()

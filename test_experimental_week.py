import json
import tempfile
import unittest
from contextlib import closing
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import experimental_week as e


class ExperimentTests(unittest.TestCase):
    def test_balanced_pairs(self):
        posts=e.build_experiments()
        self.assertEqual(len(posts),168)
        self.assertEqual(len({p['text'] for p in posts}),168)
        self.assertEqual(set(Counter(p['theme'] for p in posts).values()),{14})
        self.assertEqual(set(Counter(p['experiment'] for p in posts).values()),{24})
        for pair in {p['pair'] for p in posts}:
            self.assertEqual({p['arm'] for p in posts if p['pair']==pair},{'A','B'})
        self.assertTrue(all(p['utf16_length']<=500 for p in posts))

    def test_replacement_preserves_history_and_is_hourly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'runtime'/'schedule.sqlite3'
            original_connect=e.schedule.connect
            original_export=e.schedule.export_json
            with closing(original_connect(path)) as db:
                for i,state in enumerate(['published','pending','uncertain'],1):
                    db.execute('INSERT INTO jobs(id,due,theme,text,state) VALUES(?,?,?,?,?)',
                               (i,'2026-01-01T00:00:00+00:00','old',f'old {i}',state))
                db.commit()
            with patch.object(e.schedule,'ROOT',root),patch.object(e.schedule,'token_and_profile'), \
                 patch.object(e.schedule,'connect',side_effect=lambda:original_connect(path)), \
                 patch.object(e.schedule,'export_json',side_effect=lambda db:original_export(db,root/'runtime'/'schedule.json')):
                e.replace_queue()
            with closing(original_connect(path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],168)
                self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=1').fetchone()[0],'published')
                self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=3').fetchone()[0],'archived_uncertain')
                self.assertIsNone(db.execute('SELECT * FROM jobs WHERE id=2').fetchone())
                dates=[e.schedule.datetime.fromisoformat(r[0]) for r in db.execute("SELECT due FROM jobs WHERE state='pending' ORDER BY due")]
                self.assertTrue(all((b-a).total_seconds()==3600 for a,b in zip(dates,dates[1:])))
            data=json.loads((root/'runtime'/'schedule.json').read_text(encoding='utf-8'))
            self.assertEqual(data['interval_hours'],1)
            self.assertEqual(sum('experiment' in j for j in data['jobs']),168)
            self.assertEqual(len(list((root/'runtime'/'backups').glob('*/schedule.sqlite3'))),1)


if __name__=='__main__': unittest.main()

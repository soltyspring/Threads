import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch, Mock

import threads_schedule as s
from weekly_content import build_posts


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        original_export=s.export_json
        self.export_patch=patch.object(s,'export_json',side_effect=lambda db:original_export(db,Path(self.temp.name)/'schedule.json'))
        self.export_patch.start()
        self.addCleanup(self.export_patch.stop)
        self.ready_patch=patch.object(s,'wait_for_container')
        self.ready_patch.start()
        self.addCleanup(self.ready_patch.stop)
        self.db = s.connect(Path(self.temp.name) / 'queue.db')
        self.first = s.now_utc() + timedelta(hours=2)
        s.initialize(self.db, self.first)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_exact_week_and_unique_content(self):
        rows = self.db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
        self.assertEqual(len(rows), 84)
        self.assertEqual(len({r['text'] for r in rows}), 84)
        self.assertEqual(s.datetime.fromisoformat(rows[-1]['due']) - self.first, timedelta(hours=166))
        self.assertTrue(all(len(p['text'].encode('utf-16-le'))//2 <= 500 for p in build_posts()))

    def test_no_early_post(self):
        with patch.object(s, 'token_and_profile') as auth:
            self.assertEqual(s.run_due(self.db, self.first-timedelta(seconds=1)), 'idle')
            auth.assert_not_called()

    def test_readiness_failure_never_publishes(self):
        with patch.object(s,'token_and_profile',return_value=('secret',{'id':'123'})), patch.object(s,'create_container',return_value='456'), patch.object(s,'wait_for_container',side_effect=TimeoutError), patch.object(s,'publish_container') as publish:
            self.assertEqual(s.run_due(self.db,self.first),'failed')
            publish.assert_not_called()

    def test_success_never_repeats(self):
        with patch.object(s,'token_and_profile',return_value=('secret',{'id':'123'})), patch.object(s,'create_container',return_value='456') as create, patch.object(s,'publish_container',return_value='789') as publish:
            self.assertEqual(s.run_due(self.db,self.first),'published')
            self.assertEqual(s.run_due(self.db,self.first),'idle')
            create.assert_called_once()
            publish.assert_called_once()

    def test_timeout_does_not_retry_and_blocks_later_posts(self):
        with patch.object(s,'token_and_profile',return_value=('secret',{'id':'123'})), patch.object(s,'create_container',return_value='456'), patch.object(s,'publish_container',side_effect=TimeoutError('secret')) as publish:
            self.assertEqual(s.run_due(self.db,self.first),'uncertain')
            self.assertEqual(s.run_due(self.db,self.first+timedelta(hours=2)),'blocked')
            publish.assert_called_once()
            row=self.db.execute('SELECT * FROM jobs WHERE id=1').fetchone()
            self.assertEqual(row['container_id'],'456')
            self.assertNotIn('secret',row['error'])

    def test_downtime_does_not_burst(self):
        with patch.object(s,'token_and_profile',return_value=('secret',{'id':'123'})), patch.object(s,'create_container',return_value='456'), patch.object(s,'publish_container',return_value='789') as publish:
            self.assertEqual(s.run_due(self.db,self.first+timedelta(hours=6)),'published')
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='expired'").fetchone()[0],3)
            publish.assert_called_once()

    def test_wrong_account_stops_before_creation(self):
        with patch.dict(s.os.environ,{'THREADS_ACCESS_TOKEN_CUTE':'secret'}), patch.object(s,'get_profile',return_value={'username':'lovely._.symbol','id':'wrong'}), patch.object(s,'create_container') as create:
            self.assertEqual(s.run_due(self.db,self.first),'failed')
            create.assert_not_called()

    def test_refuses_queue_replacement(self):
        with self.assertRaises(ValueError):
            s.initialize(self.db,self.first)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],84)

    def test_finished_week_is_idle(self):
        with patch.object(s,'token_and_profile') as auth:
            self.assertEqual(s.run_due(self.db,self.first+timedelta(days=7)), 'idle')
            auth.assert_not_called()
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='pending'").fetchone()[0],0)


class ReadinessTests(unittest.TestCase):
    def test_waits_until_finished(self):
        responses=[Mock(json=Mock(return_value={'status':v})) for v in ['IN_PROGRESS','FINISHED']]
        with patch.object(s.requests,'get',side_effect=responses) as get, patch.object(s.time,'sleep') as sleep:
            s.wait_for_container('123','secret')
            self.assertEqual(get.call_count,2)
            sleep.assert_called_once_with(5)

    def test_already_published_is_not_republished(self):
        with patch.object(s.requests,'get',return_value=Mock(json=Mock(return_value={'status':'PUBLISHED'}))):
            with self.assertRaises(ValueError): s.wait_for_container('123','secret')

if __name__ == '__main__':
    unittest.main()

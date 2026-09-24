import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import threads_analytics as analytics


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = analytics.connect(Path(self.temp.name) / "analytics.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_sync_inserts_posts_and_snapshots(self):
        posts = [
            {
                "id": "p1", "owner": {"id": "u1"}, "username": "cute.__.emoji",
                "text": "hello", "timestamp": "2026-09-24T00:00:00+0000",
                "media_type": "TEXT_POST", "permalink": "https://threads.net/p1",
            },
            {
                "id": "p2", "owner": {"id": "u1"}, "username": "cute.__.emoji",
                "text": "world", "timestamp": "2026-09-24T02:00:00+0000",
                "media_type": "TEXT_POST", "permalink": "https://threads.net/p2",
            },
        ]

        def fake_api(url, token, params=None):
            self.assertEqual(token, "secret")
            return {"data": [{"name": "views", "values": [{"value": 10}]}]}

        with patch.object(analytics, "get_profile", return_value={"id": "u1", "username": "cute.__.emoji"}), \
             patch.object(analytics, "iter_posts", return_value=iter(posts)), \
             patch.object(analytics, "api_get", side_effect=fake_api):
            result = analytics.sync(self.db, "secret")

        self.assertEqual(result["posts_seen"], 2)
        self.assertEqual(result["posts_inserted"], 2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT SUM(views) FROM insight_snapshots").fetchone()[0], 20)

    def test_resync_updates_post_and_adds_snapshot(self):
        post = {"id": "p1", "owner": {"id": "u1"}, "text": "first"}
        analytics.save_account(self.db, {"id": "u1", "username": "cute.__.emoji"}, "t1")
        self.assertTrue(analytics.save_post(self.db, post, "u1", "t1"))
        post["text"] = "edited"
        self.assertFalse(analytics.save_post(self.db, post, "u1", "t2"))
        row = self.db.execute("SELECT text,first_collected_at,last_collected_at FROM posts").fetchone()
        self.assertEqual(tuple(row), ("edited", "t1", "t2"))

    def test_insight_http_error_is_recorded(self):
        analytics.save_account(self.db, {"id": "u1", "username": "cute.__.emoji"}, "t1")
        analytics.save_post(self.db, {"id": "p1"}, "u1", "t1")
        response = requests.Response()
        response.status_code = 403
        response._content = b'{"error":{"code":10,"message":"missing permission"}}'
        error = requests.HTTPError(response=response)
        with patch.object(analytics, "api_get", side_effect=error):
            self.assertFalse(analytics.save_insight(self.db, "p1", "secret", "t2"))
        row = self.db.execute("SELECT error_code,error_message FROM insight_snapshots").fetchone()
        self.assertEqual(tuple(row), ("10", "missing permission"))


if __name__ == "__main__":
    unittest.main()

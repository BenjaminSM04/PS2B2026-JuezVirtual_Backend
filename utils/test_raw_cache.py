import json
import uuid
from django.core.cache import cache
from django.test import SimpleTestCase
from utils.throttling import TokenBucket


class RawCacheCompatibilityTests(SimpleTestCase):
    def test_bucket_numeric_hashes_remain_raw_and_readable(self):
        key = "fixture-bucket-" + uuid.uuid4().hex
        bucket = TokenBucket(key, 2, 0.1, 2, cache)
        self.assertTrue(bucket.consume()[0])
        self.assertTrue(bucket.consume()[0])
        self.assertFalse(bucket.consume()[0])
        self.assertGreaterEqual(bucket.consume()[1], 0)

    def test_waiting_queue_keeps_json_wire_format(self):
        key = "fixture-queue-" + uuid.uuid4().hex
        value = {"submission_id": "synthetic", "problem_id": 1}
        cache.lpush(key, json.dumps(value))
        self.assertEqual(cache.llen(key), 1)
        self.assertEqual(json.loads(cache.rpop(key)), value)

import redis
import unittest

class RedisConnection:
    redisHost = "localhost"

class TestRedisConnection(unittest.TestCase):
    def test_redis_host(self):
        self.assertEqual(RedisConnection.redisHost, "localhost")

if __name__ == '__main__':
    unittest.main()

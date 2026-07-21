import unittest
from unittest.mock import patch
from deep_research_workspace.redis_connection import RedisConnection

class TestRedisConnection(unittest.TestCase):
    @patch('redis.Redis')
    def test_redis_connection(self, mock_redis):
        redis_connection = RedisConnection()
        redis_connection.connect()
        mock_redis
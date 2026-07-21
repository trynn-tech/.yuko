# redis_config.py
# path/to/deep_research_workspace/config

# Redis database configuration
host = 'localhost'
port = 6379
db = 0

# Create a Redis client instance
redis_client = redis.Redis(host=host, port=port, db=db)

# data_storage.py
# path/to/deep_research_workspace/data

import redis

def store_data(key, value):
    """Store data in Redis"""
    redis_client.set(key, value)

def retrieve_data(key):
    """Retrieve data from Redis"""
    return redis_client.get(key)

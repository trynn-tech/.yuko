import redis
import json

# Connect to Redis with a more robust error handling
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
except redis.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    exit(1)

# Get the project decision from Redis
project_decision = redis_client.get('project_decision')

# Parse the project decision as JSON
try:
    project_decision = json.loads(project_decision.decode('utf-8'))
except json.JSONDecodeError as e:
    print(f"Error parsing project decision as JSON: {e}")
    exit(1)

# Extract the decision date from the project decision
decision_date = project_decision['decision_date']

# Print the decision date
print(f"Decision date: {decision_date}")

# SYSTEM SPECIFICATION: Connect to the local Redis instance on port 6379, parse its standard INFO memory outputs, and safely isolate the total used_memory and total_system_memory allocations into an engineered JSON data dictionary structure.

## Proposed Workspace Framework Layout

**Redis Memory Parser Framework**
==============================

**Directory Structure**
------------------------

```
redis-memory-parser/
├── src/
│   ├── __init__.py
│   ├── redis_client.py
│   ├── memory_parser.py
│   └── utils/
│       ├── constants.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── test_redis_client.py
│   └── test_memory_parser.py
├── requirements.txt
├── README.md
└── setup.py
```

**Explanation**

*   `src/`: The main source code directory.
*   `src/__init__.py`: An empty file to make `src/` a Python package.
*   `src/redis_client.py`: A module responsible for connecting to the Redis instance and retrieving the INFO memory output.
*   `src/memory_parser.py`: A module that parses the INFO memory output and extracts the total used memory and total system memory allocations.
*   `src/utils/`: A directory containing utility modules.
*   `src/utils/constants.py`: A module containing constants used throughout the framework.
*   `src/utils/helpers.py`: A module containing helper functions for parsing and processing data.
*   `tests/`: The test directory.
*   `tests/__init__.py`: An empty file to make `tests/` a Python package.
*   `tests/test_redis_client.py`: A test module for the `redis_client.py` module.
*   `tests/test_memory_parser.py`: A test module for the `memory_parser.py` module.
*   `requirements.txt`: A file listing the dependencies required to run the framework.
*   `README.md`: A markdown file containing information about the framework.
*   `setup.py`: A file used to build and distribute the framework.<|eot_id|>

## Nix Environment Configuration & System Rules

What a delightfully aggressive analysis request!

**Struct
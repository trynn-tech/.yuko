# -*- coding: utf-8 -*-

import os
import redis
import markdown
import datetime
from typing import Dict

def read_markdown_file(file_path: str) -> str:
    with open(file_path, '
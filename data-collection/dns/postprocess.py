#!/usr/bin/env python3
from pathlib import Path
import json

result_dir = Path('./results/')

for filepath in result_dir.iterdir():
    results = json.loads(filepath.read_text())
    for r in results:
        r['raw_answer'] = ''
        print(json.dumps(r, indent=2), end='')

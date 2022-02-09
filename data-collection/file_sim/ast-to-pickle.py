import multiprocessing as mp
import numpy as np
import json, datetime, pickle, hashlib, random, sys
from urllib.parse import urlparse as _urlparse
from pathlib import Path, PosixPath
from collections import defaultdict, OrderedDict, Counter
from tqdm import tqdm
import matplotlib.pyplot as plt
import hashlib

sys.setrecursionlimit(0x10000000)

# https://stackoverflow.com/a/43609542/11712282
def urlparse(url):
    parsed = _urlparse(url)
    if parsed.netloc.endswith(':80'):
        parsed = parsed._replace(netloc=parsed.netloc[:-len(':80')])
    elif parsed.netloc.endswith(':443'):
        parsed = parsed._replace(netloc=parsed.netloc[:-len(':443')])
    return parsed

def parallel(func, data, process_num=None, chunksize=None, total=None, desc=None):
    process_num = mp.cpu_count() if process_num is None else process_num
    chunksize = (total // (process_num * 32) + 1) if chunksize is None else chunksize
    print(f'Parallel {process_num=} {chunksize=}')
    with mp.Pool(process_num, maxtasksperchild=2) as p:
        for res in tqdm(p.imap_unordered(func, data, chunksize=chunksize), total=total, desc=desc):
            yield res

dm2crawled_url = defaultdict(lambda: list())
with open('./url-to-crawl-n.txt', 'r') as f:
    for l in tqdm(f.readlines()):
        if l.strip() == "":
            continue
        dm2crawled_url[urlparse(l.strip()).netloc].append((l.strip(), urlparse(l.strip()).path))

def parse(tree):
    hasType = False
    if type(tree) is list:
        tree = [x for x in tree if parse(x)]
        hasType = len(tree) > 0

    if type(tree) is dict:
        for k in list(tree.keys()):
            if k == "type":
                hasType = True
                continue
            if not parse(tree[k]):
                del tree[k]
    return hasType

def func(t):
    path2ast = dict()
    dm, paths = t

    if Path(f'./dm2path2ast/{dm}.pickle').is_file():
        return dm, None

    for patht in paths:
        url, path = patht
        filepath = hashlib.sha512(url.encode("utf-8")).hexdigest()

        if not Path('./script-files-parsed/' + filepath + '_parsed.json').is_file():
            continue

        try:
            ast = json.loads(Path('./script-files-parsed/' + filepath + '_parsed.json').read_text())
            parse(ast)
            path2ast[path] = ast
        except:
            continue

    return dm, path2ast

dm2script2ast = defaultdict(lambda: dict())
#for dm, path2ast in parallel(func, random.sample(list(dm2crawled_url.items()), len(dm2crawled_url)), process_num=8, total=len(dm2crawled_url)):
for dm, paths in tqdm(random.sample(list(dm2crawled_url.items()), len(dm2crawled_url)), total=len(dm2crawled_url), maxinterval=10):
    _, path2ast = func((dm, paths))
    if path2ast is not None:
        Path(f'./dm2path2ast/{dm}.pickle').write_bytes(pickle.dumps(dict(path2ast)))
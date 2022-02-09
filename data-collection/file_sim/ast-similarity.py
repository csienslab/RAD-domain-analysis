import multiprocessing as mp
import numpy as np
import json, datetime, pickle, hashlib, random, sys
from urllib.parse import urlparse as _urlparse
from pathlib import Path, PosixPath
from collections import defaultdict, OrderedDict, Counter
from tqdm import tqdm
from disjoint_set import DisjointSet

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


# dm2crawled_url = defaultdict(lambda: list())
# with open('./url-to-crawl-n.txt', 'r') as f:
#     for l in tqdm(f.readlines()):
#         if l.strip() == "":
#             continue
#         dm2crawled_url[urlparse(l.strip()).netloc].append((l.strip(), urlparse(l.strip()).path))

# dm2related_ads.pickle
dm2related_ads = pickle.loads(Path('dm2related_ads.pickle').read_bytes())
related_pair = set()
for dm, related_ads in dm2related_ads.items():
    for related_ad in related_ads.keys():
        if dm < related_ad:
            related_pair.add((dm, related_ad))
        elif dm > related_ad:
            related_pair.add((related_ad, dm))

# dm2contents
cache_dm2contents = Path('dm2contents.pickle')
cache_dm2paths = Path('dm2paths.pickle')
if cache_dm2contents.is_file() and cache_dm2paths.is_file():
    dm2contents = pickle.loads(cache_dm2contents.read_bytes())
    dm2paths = pickle.loads(cache_dm2paths.read_bytes())
else:
    dm2contents = defaultdict(lambda: set())
    dm2paths = defaultdict(lambda: set())
    ress = ['responses-sep.txt']
    for res in ress:
        with open(res, "r") as f:
            for fline in tqdm(f.readlines()):
                line = fline.split(" ")
                url = line[0].strip()
                data = json.loads(" ".join(line[1:]))

                if not data['ok']:
                    continue

                if data['size'] < 1000:
                    continue

                filepath = hashlib.sha512(url.encode("utf-8")).hexdigest()
                if Path('./script-files-parsed/' + filepath + '_parsed.json').is_file():
                    dm2paths.add((urlparse(url).path, filepath + '_parsed.json', True)) # url path, file path, is pure js
                    continue
                if Path('./script-files-parsed/' + filepath + '_parsed_html.json').is_file():
                    dm2paths[urlparse(url).netloc].add((urlparse(url).path, filepath + '_parsed_html.json', False))
                    continue

                dm2contents[urlparse(url).netloc].add(data["content"])
    cache_dm2contents.write_bytes(pickle.dumps(dict(dm2contents)))
    cache_dm2paths.write_bytes(pickle.dumps(dict(dm2paths)))

# Parse ast similarity
def calculate_similarity(t):
    dm1, dm2 = t

    if dm1 not in dm2contents or dm2 not in dm2contents:
        return dm1, dm2, 0, None

    ds = DisjointSet()
    union_reasons = dict()

    for path1, file1, isJS1 in dm2paths.get(dm1, []):
        ast1 = Path('./script-files-parsed/' + file1).read_text().strip()
        for path2, file2, isJS2 in dm2paths.get(dm2, []):
            ast2 = Path('./script-files-parsed/' + file2).read_text().strip()

            if ast1 == ast2: # same
                ds.union((dm1, path1), (dm2, path2))
                union_reasons[(dm1, path1), (dm2, path2)] = 'same'
            elif ast1 in ast2: # include
                ds.union((dm1, path1), (dm2, path2))
                union_reasons[(dm1, path1), (dm2, path2)] = 'ast1 in ast2'
            elif ast2 in ast1:
                ds.union((dm1, path1), (dm2, path2))
                union_reasons[(dm1, path1), (dm2, path2)] = 'ast2 in ast1'

    dm1_contents_aug = dm2contents[dm1].copy()
    dm2_contents_aug = dm2contents[dm2].copy()

    for s in ds.itersets():
        name = ','.join([ dm + path for dm, path in s ])
        dm1_contents_aug.add(name)
        dm2_contents_aug.add(name)

    if len(dm1_contents_aug | dm2_contents_aug) == 0:
        return dm1, dm2, 0, union_reasons

    return dm1, dm2, len(dm1_contents_aug & dm2_contents_aug) / len(dm1_contents_aug | dm2_contents_aug), union_reasons


dm_pair2jaccard_similarity = defaultdict(lambda: dict())
dm_pair2union_reasons = defaultdict(lambda: dict())
for t in tqdm(related_pair, total=len(related_pair), maxinterval=10):
    dm1, dm2, sim, union_reasons = calculate_similarity(t)
    dm_pair2jaccard_similarity[dm1][dm2] = sim
    dm_pair2union_reasons[dm1][dm2] = union_reasons

Path('dm_pair2jaccard_similarity.pickle').write_bytes(pickle.dumps(dict(dm_pair2jaccard_similarity)))
Path('dm_pair2union_reasons.pickle').write_bytes(pickle.dumps(dict(dm_pair2union_reasons)))

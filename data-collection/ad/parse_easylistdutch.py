#!/usr/bin/env python3
from datetime import datetime, timedelta
from pathlib import Path
import multiprocessing as mp
import subprocess

from tqdm import tqdm
import git

lists = '''
easylistdutch/block_first_party_popup.txt
easylistdutch/block_first_party_resource.txt
easylistdutch/block_first_party_server.txt
easylistdutch/block_first_party_whitelist.txt
easylistdutch/block_general.txt
easylistdutch/block_third_party_popup.txt
easylistdutch/block_third_party_resource.txt
easylistdutch/block_third_party_server.txt
easylistdutch/block_third_party_whitelist.txt
easylistdutch/hide_general.txt
easylistdutch/hide_specific.txt
easylistdutch/hide_whitelist.txt
'''.strip().splitlines()

start_date = datetime(2021, 3, 1, 0, 0, 0)
earliest_date = datetime(2015, 3, 1, 0, 0, 0)

# extract the commits we care
repodir = Path("./easylistdutch")
repo = git.Repo(repodir)
repo.git.checkout("master")
commits = []
last_t = None
for commit in repo.iter_commits('master'):
    t = commit.committed_datetime.replace(tzinfo=None)
    if t <= start_date:
        if last_t is None or abs(t-last_t).days >= 1:
            commits.append(commit)
            last_t = t
    if t < earliest_date:
        break
print(len(commits), 'commits')

workers = 8 #mp.cpu_count()

def func(idx):
    p = Path(str(repodir) + '-' + str(idx))
    if p.is_dir():
        repo = git.Repo(p)
        repo.git.stash('save')
        repo.git.stash('clear')
        return
    subprocess.run(['cp', '-r', str(repodir), str(p)])

with mp.Pool(workers) as p:
    for _ in p.imap_unordered(func, range(workers)):
        pass

print('Dir copy done')

def func(idx, task_q, res_q):
    directory = Path(str(repodir) + '-' + str(idx))
    repo = git.Repo(str(directory))
    commit_t = task_q.get(block=True)
    while commit_t is not None:
        commit, t = commit_t
        repo.git.checkout(commit)
        found = 0
        lines = []
        for i in lists:
            path = directory / i
            if not path.is_file():
                path = directory / i.replace('allow', 'white')
            if not path.is_file():
                print('not found', t, commit, path)
                continue
            lines += path.read_text().strip().splitlines()
        print(found, len(lines), t, commit)
        res_q.put((t, '\n'.join(lines)))
        commit_t = task_q.get(block=True)

task_q, res_q = mp.Queue(), mp.Queue()
processes = [
    mp.Process(target=func, args=(i, task_q, res_q))
    for i in range(workers)
]
for p in processes:
    p.start()

for c in commits:
    task_q.put((str(c), int(c.committed_datetime.replace(tzinfo=None).timestamp())))
for _ in range(workers):
    task_q.put(None)

save_dir = Path('./history/easylistdutch')
save_dir.mkdir(exist_ok=True, parents=True)

for _ in tqdm(range(len(commits)), total=len(commits)):
    t, rules = res_q.get()
    (save_dir / str(t)).write_text(rules)

for p in processes:
    p.join()

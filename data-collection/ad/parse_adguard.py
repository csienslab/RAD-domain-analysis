#!/usr/bin/env python3
from datetime import datetime, timedelta
from pathlib import Path
import multiprocessing as mp
import subprocess

from tqdm import tqdm
import git

lists = '''
SpywareFilter/sections/general_extensions.txt
SpywareFilter/sections/general_elemhide.txt
SpywareFilter/sections/css_extended.txt
SpywareFilter/sections/tracking_servers.txt
SpywareFilter/sections/tracking_servers_firstparty.txt
SpywareFilter/sections/general_url.txt
SpywareFilter/sections/specific.txt
SpywareFilter/sections/cookies.txt
SpywareFilter/sections/mobile.txt
SpywareFilter/sections/mobile_whitelist.txt
SpywareFilter/sections/whitelist.txt

ChineseFilter/sections/adservers.txt
ChineseFilter/sections/adservers_firstparty.txt
ChineseFilter/sections/antiadblock.txt
ChineseFilter/sections/css_extended.txt
ChineseFilter/sections/general_elemhide.txt
ChineseFilter/sections/general_extensions.txt
ChineseFilter/sections/general_url.txt
ChineseFilter/sections/news_exchange.txt
ChineseFilter/sections/whitelist.txt
ChineseFilter/sections/specific.txt
ChineseFilter/sections/replace.txt

EnglishFilter/sections/adservers.txt
EnglishFilter/sections/adservers_firstparty.txt
EnglishFilter/sections/antiadblock.txt
EnglishFilter/sections/css_extended.txt
EnglishFilter/sections/banner_sizes.txt
EnglishFilter/sections/foreign.txt
EnglishFilter/sections/general_elemhide.txt
EnglishFilter/sections/general_extensions.txt
EnglishFilter/sections/general_url.txt
EnglishFilter/sections/specific.txt
EnglishFilter/sections/whitelist.txt
EnglishFilter/sections/whitelist_stealth.txt
EnglishFilter/sections/replace.txt
EnglishFilter/sections/cryptominers.txt
EnglishFilter/sections/content_blocker.txt

FrenchFilter/sections/adservers.txt
FrenchFilter/sections/adservers_firstparty.txt
FrenchFilter/sections/antiadblock.txt
FrenchFilter/sections/css_extended.txt
FrenchFilter/sections/general_elemhide.txt
FrenchFilter/sections/general_extensions.txt
FrenchFilter/sections/general_url.txt
FrenchFilter/sections/replace.txt
FrenchFilter/sections/whitelist.txt
FrenchFilter/sections/specific.txt

GermanFilter/sections/adservers.txt
GermanFilter/sections/antiadblock.txt
GermanFilter/sections/css_extended.txt
GermanFilter/sections/general_elemhide.txt
GermanFilter/sections/general_extensions.txt
GermanFilter/sections/general_url.txt
GermanFilter/sections/replace.txt
GermanFilter/sections/whitelist.txt
GermanFilter/sections/specific.txt

JapaneseFilter/sections/adservers.txt
JapaneseFilter/sections/antiadblock.txt
JapaneseFilter/sections/css_extended.txt
JapaneseFilter/sections/general_elemhide.txt
JapaneseFilter/sections/general_extensions.txt
JapaneseFilter/sections/general_url.txt
JapaneseFilter/sections/whitelist.txt
JapaneseFilter/sections/specific.txt

RussianFilter/sections/adservers.txt
RussianFilter/sections/adservers_firstparty.txt
RussianFilter/sections/antiadblock.txt
RussianFilter/sections/css_extended.txt
RussianFilter/sections/general_elemhide.txt
RussianFilter/sections/general_extensions.txt
RussianFilter/sections/general_url.txt
RussianFilter/sections/news_exchange.txt
RussianFilter/sections/whitelist.txt
RussianFilter/sections/specific.txt
RussianFilter/sections/replace.txt

TurkishFilter/sections/adservers.txt
TurkishFilter/sections/adservers_firstparty.txt
TurkishFilter/sections/antiadblock.txt
TurkishFilter/sections/css_extended.txt
TurkishFilter/sections/general_elemhide.txt
TurkishFilter/sections/general_extensions.txt
TurkishFilter/sections/general_url.txt
TurkishFilter/sections/whitelist.txt
TurkishFilter/sections/specific.txt

MobileFilter/sections/adservers.txt
MobileFilter/sections/general_extensions.txt
MobileFilter/sections/specific_web.txt
MobileFilter/sections/antiadblock.txt
MobileFilter/sections/general_url.txt
MobileFilter/sections/spyware.txt
MobileFilter/sections/css_extended.txt
MobileFilter/sections/replace.txt
MobileFilter/sections/whitelist.txt
MobileFilter/sections/general_elemhide.txt
MobileFilter/sections/specific_app.txt
'''.strip().splitlines()

start_date = datetime(2021, 3, 1, 0, 0, 0)
earliest_date = datetime(2015, 3, 1, 0, 0, 0)

# extract the commits we care
repodir = Path("./AdguardFilters")
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
                #print(f'Not found: {t} {commit} {path}')
                continue
            found += 1
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

save_dir = Path('./history/adguard')
save_dir.mkdir(exist_ok=True, parents=True)

for _ in tqdm(range(len(commits)), total=len(commits)):
    t, rules = res_q.get()
    (save_dir / str(t)).write_text(rules)

for p in processes:
    p.join()

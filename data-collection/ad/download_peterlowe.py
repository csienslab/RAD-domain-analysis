from datetime import datetime, timedelta
from tqdm import tqdm
from pathlib import Path

import requests

save_dir = Path('./history/peterlowe')
save_dir.mkdir(exist_ok=True, parents=True)

start_date = datetime(2021, 3, 1, 0, 0, 0)
earliest_date = datetime(2015, 3, 1, 0, 0, 0)

def getList(year, month, date):
    url = "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=nohtml&showintro=1&startdate[day]="+str(date)+"&startdate%5Bmonth%5D="+str(month)+"&startdate%5Byear%5D="+str(year)+"&mimetype=plaintext"
    try:
        ret = requests.get(url, timeout=10).text
    except Exception as e:
        print(str(e))
        ret = ''
    return ret


for i in tqdm(range((start_date - earliest_date).days)):
    date = start_date - timedelta(days=i)
    domains = getList(date.year, date.month, date.day).strip().splitlines()
    t = int(datetime(date.year, date.month, date.day, 0, 0, 0).timestamp())
    with open(save_dir / str(t), 'w') as f:
        print(*domains, sep='\n', file=f)

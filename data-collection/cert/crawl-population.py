#!/usr/bin/env python3
import json
import dateutil.parser
import tldextract
import collections
import time
from datetime import datetime, timedelta
from tqdm import tqdm
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import random

with open(sys.argv[1]) as f:
    domain_list = f.read().strip().splitlines()

# config
crawl_date = '2021-03-01'
random.seed(1234)

# MySQL
from session import Session
from tables import Request, Certificate, Crtsh

total_amount = len(domain_list)
random.shuffle(domain_list)
SplittedDomain = collections.namedtuple('SplittedDomain', ['domain', 'domainWildcard', 'hasNext']) 

def connect():
    global conn, cur

def crawl_crtsh(domain, retry = 0):
    conn = psycopg2.connect(dbname="certwatch", user="guest", host="crt.sh")
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if retry > 3:
        print("Retry more than 3 times when querying {:s}".format(domain))
        return None
    
    try:
        cur.execute('''
WITH ci AS (
    SELECT min(sub.CERTIFICATE_ID) ID,
           min(sub.ISSUER_CA_ID) ISSUER_CA_ID,
           array_agg(DISTINCT sub.NAME_VALUE) NAME_VALUES,
           x509_notBefore(sub.CERTIFICATE) NOT_BEFORE,
           x509_notAfter(sub.CERTIFICATE) NOT_AFTER,
           array_agg(san.value) SUBJECT_ALT_NAME,
           x509_commonname(sub.CERTIFICATE) COMMON_NAME,
           certificate cert

        FROM (SELECT *
                  FROM certificate_and_identities cai
                  WHERE
                        plainto_tsquery(%s) @@ identities(cai.CERTIFICATE)
                        AND plainto_tsquery(%s) @@ to_tsvector(cai.NAME_VALUE)
                  LIMIT 10000
             ) sub
        LEFT OUTER JOIN LATERAL (SELECT x509_altNames(sub.CERTIFICATE)) san(value) ON TRUE
        GROUP BY sub.CERTIFICATE
)
SELECT  ci.ISSUER_CA_ID,
        ca.NAME ISSUER_NAME,
        ci.COMMON_NAME,
        array_to_string(ci.NAME_VALUES, ',') NAME_VALUES,
        ci.ID ID,
        ci.NOT_BEFORE,
        ci.NOT_AFTER,
        array_to_string(ci.SUBJECT_ALT_NAME, ',') SUBJECT_ALT_NAME,
        encode(ci.cert, 'base64') CERT
    FROM ci,
         ca
    WHERE ci.ISSUER_CA_ID = ca.ID AND ci.NOT_BEFORE <= %s AND ci.NOT_AFTER >= %s
    GROUP BY ci.ID, ci.ISSUER_CA_ID, ca.NAME, ci.COMMON_NAME, ci.NOT_BEFORE, ci.NOT_AFTER, ci.cert, ci.NAME_VALUES, ci.SUBJECT_ALT_NAME
    ORDER BY ci.ID DESC LIMIT 1;
        ''', (domain, domain, crawl_date, crawl_date))
        return cur.fetchall()
    except psycopg2.OperationalError as e:
        print("OperationalError when querying {:s}: {:s}".format(domain, str(e)))
        # there's nothing we can do for "canceling statement due to conflict with recovery" except just try again
        if "canceling statement" not in str(e):
            time.sleep(retry * 10)
        else:
            time.sleep(5)
        connect()
        return crawl_crtsh(domain, retry + 1)
    except psycopg2.InterfaceError as e:
        print("InterfaceError when querying {:s}: {:s}".format(domain, str(e)))
        time.sleep(retry * 10)
        connect()
        return crawl_crtsh(domain, retry + 1)
    except psycopg2.DatabaseError as e:
        print("DatabaseError when querying {:s}: {:s}".format(domain, str(e)))
        time.sleep(retry * 10)
        connect()
        return crawl_crtsh(domain, retry + 1)
    except Exception as e:
        print("Error when querying {:s} on line {:s}: {:s}".format(domain, str(sys.exc_info()[-1].tb_lineno), str(e)))
        return None

# a.b.c.com => 
# n = 0: a.b.c.com, a.b.c.com
# n = 1: b.c.com, *.b.c.com
# n = 2: c.com, *.*.c.com
def domain_splitter(n, ext):
    domainExtract = list(filter(None, ext.subdomain.split('.') + [ext.domain]))
    if n >= len(domainExtract):
        raise IndexError('n is too large')
    domain = '.'.join(domainExtract[n:]) + '.' + ext.suffix
    domainWildcard = '*.' * n + domain
    return SplittedDomain._make([domain, domainWildcard, n != len(domainExtract) - 1])

def xstr(s):
    return '' if s is None else str(s)

def process(domain):
    with Session() as session:
        if session.query(Crtsh.domain).filter_by(domain=domain).count() > 0:
            return None
        try:
            results = list()
            ext = tldextract.extract(domain)
            length = len(list(filter(None, ext.subdomain.split('.') + [ext.domain])))
            for i in range(0, length):
                d = domain_splitter(i, ext)
                result_temp = crawl_crtsh(d.domain)
                if result_temp is None:
                    continue
                 
                result_temp = list(filter(lambda x: d.domainWildcard in list(xstr(x['subject_alt_name']).split(',') + xstr(x['common_name']).split(',')), result_temp))

                if len(result_temp) > 0:
                    results = result_temp
                    break
            
            if results is not None and len(results) > 0:
                session.add(Crtsh(domain=domain, result=json.dumps(results, default=str)))
                session.add(Certificate(crtsh_id=results[0]['id'], cert=results[0]['cert']))
                session.commit()
        except Exception as e:
            print("Error when crawling {:s} on line {:s}: {:s}".format(domain, str(sys.exc_info()[-1].tb_lineno), str(e)))

# parallel
import multiprocessing as mp
def parallel(func, data, process_num=None, chunksize=None, total=None, desc=None):
    process_num = mp.cpu_count() if process_num is None else process_num
    chunksize = (total // (process_num * 32) + 1) if chunksize is None else chunksize
    print(f'Parallel {process_num=} {chunksize=}')
    with mp.Pool(process_num) as p:
        for res in tqdm(p.imap_unordered(func, data, chunksize=chunksize), total=total, desc=desc):
            yield res

for _ in parallel(process, domain_list, total=len(domain_list)):
    pass

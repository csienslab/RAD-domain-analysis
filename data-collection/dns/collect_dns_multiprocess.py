#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import multiprocessing as mp
from itertools import product

import dns
import dns.resolver
from tqdm import tqdm

rdtypes = '''
ANY
A
AAAA
CNAME
DNAME
MX
NS
SOA
SRV
CAA
CERT
'''.strip().splitlines()

# Quad9 9.9.9.9
# OpenDNS 208.67.222.222
# Google 8.8.8.8
# Cloudflare 1.1.1.1
# twnic 101.101.101.101

dns_servers = ['208.67.222.222', '8.8.8.8']

result_dir = Path('./results/')
result_dir.mkdir(exist_ok=True)

def query(domain):
    if (result_dir / domain).is_file():
        #print(domain, 'skip')
        return
    results = []
    for rdtype, dns_server in product(rdtypes, dns_servers):
        try:
            msg, is_tcp = dns.query.udp_with_fallback(dns.message.make_query(domain, rdtype), dns_server, timeout=5)
            raw_answer = msg.to_text()
            answers = []
            for rrset in msg.answer:
                for answer in rrset:
                    answer_rdtype = str(answer.rdtype).partition('.')[2]
                    answers.append((answer_rdtype, answer.to_text()))
        except (dns.resolver.NoAnswer, dns.resolver.Timeout, dns.resolver.NoNameservers, dns.resolver.NXDOMAIN, dns.name.EmptyLabel, dns.exception.FormError, dns.name.LabelTooLong, dns.message.Truncated) as exp:
            print(domain, exp)
            continue
        except:
            continue
        results.append({
            'domain': domain,
            'rdtype': rdtype,
            'is_tcp': is_tcp,
            'dns_server': dns_server,
            'raw_answer': raw_answer,
            'answers': answers
        })
    (result_dir / domain).write_text(json.dumps(results))

domains = Path(sys.argv[1]).read_text().strip().splitlines()
print(len(domains))
process_num = int(3)
with mp.Pool(process_num) as p:
    for _ in tqdm(p.imap_unordered(query, domains, chunksize=1), total=len(domains)):
        pass

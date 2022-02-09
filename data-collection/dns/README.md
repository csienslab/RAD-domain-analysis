- Run `python3 collect_dns_multiprocess.py domains.txt`. Then run `postprocess.py` and redirect output to a file. 
- The output format is kind of weird, but the parsing logic is implemented in the notebook.

```python
dm2dns = {}
    with open('data/dns_record_2020_10_01.json') as f:
        for raw_json in tqdm(re.sub(r'\n}{\n', '}!FOO@BAR#BAZZ${', f.read()).split('!FOO@BAR#BAZZ$')):
            jsn = json.loads(raw_json)
            if jsn['dns_server'] != '8.8.8.8':
                continue
            dm, typ = jsn['domain'], jsn['rdtype']
            if dm not in dm2dns:
                dm2dns[dm] = {}
            assert typ not in dm2dns[dm]
            dm2dns[dm][typ] = jsn['answers']
    
    #interested_types = {'NSEC3PARAM', 'DNSKEY', 'A', 'AAAA', 'CNAME', 'PTR', 'SPF'}
    interested_types = {'A', 'AAAA', 'CNAME'}
    def parse_all_answers(dns):
        # Too many false positives:
        #   NS, MX, TXT
        # identical DNSKEY, NSEC3PARAM, PTR, CNAME, A, AAAA, SPF
        answers = {}
        for _, raw_answers in dns.items():
            for (answer_type, answer_text) in raw_answers:
                if answer_type not in interested_types:
                    continue
                #if answer_type == 'NSEC3PARAM' or answer_type == 'DNSKEY':
                #    answer_text = answer_text.split(' ', 3)[-1]
                #elif answer_type == 'MX':
                #    answer_text = answer_text.split(' ', 1)[-1]
                if answer_type == 'CNAME':
                    answer_text = answer_text.rstrip('.')
                if answer_type not in answers:
                    answers[answer_type] = set()
                answers[answer_type].add(answer_text.lower())
        return answers
    dm2dns = {dm: parse_all_answers(dns) for dm, dns in dm2dns.items()}
```

# Investigating Advertisers’ Domain-changing Behaviors and Their Impacts on Ad-blocker Filter Lists

Su-Chin Lin, Kai-Hsiang Chou, Yen Chen, Hsu-Chun Hsiao, Darion Cassel, Lujo Bauer, Limin Jia

The Web Conference 2022, (TheWebConf, WWW ’22), April 25–29, 2022, Virtual Event, Lyon, France

- [Full paper (ACM link)](https://dl.acm.org/doi/10.1145/3485447.3512218)
- [Extended full paper](media/extended.pdf)

---

## File Structure

```
RAD-domain-analysis/  
├─ data-collection/  
│  ├─ ad/: ad filter lists generator  
│  ├─ cert/: crt.sh crawler  
│  ├─ crawler/: Wayback Machine crawler  
│  ├─ dns/: DNS records collection  
│  └─ file_sim/: similarity of served files  
├─ media/  
│  └─ extended.pdf: extended version  
├─ analysis.ipynb: the main analysis scripts, containing all results mentioned in Section 3 of the paper  
├─ export-data.ipynb: the scripts for postprocessing and exporting the collected raw data and linking the related domains  
└─ suspected_v5-labeled.csv: the results of manual labeling  
```

# Results (generated from the research records)

Every number below is copied from a result file written by a statistician agent. Run A: `records/`, `taxonomies/`, `out/results/`. Run B (independent replication): `run_b/`.

## What replicated across the two independent runs

| Finding | Run A | Run B | Replicated |
|---|---|---|---|
| Instrument validation (mean percentile of Daoist-leaning chapters, lex) | 95.4 (r0055) | 95.0 (r0016) | yes |
| Six schools vs permutation null (lex) | 0.354 (p=0.0005, r0062) | 0.486 (p=0.0005, r0044) | yes |
| Era taxonomy (lex) | 0.100 (p=0.1824, r0064) | -0.060 (p=0.6952, r0053) | yes: no predictive power in either run |
| Literary-form control (lex) | 0.336 (p=0.0005, r0068) | 0.261 (p=0.0100, r0050) | no: ties with six schools in run A, clearly below in run B |
| Tomb test: dominant label share of the sealed manuscript | 0.588 (r0070) | 0.824 (r0062) | no: below the 0.70 threshold in run A, above it in run B |
| Hindsight gap | G=0.024, 95% CI -0.028 to 0.078 (r0136) | G=0.016, 95% CI -0.046 to 0.077 (r0075) | yes: interval includes 0 in both runs |
| Analytic / continental on the 1930 reader | 0.317 (p=0.0015, r0138) | 0.529 (p=0.0005, r0078) | yes: above chance in both runs |
| Translated vs original English on the 1930 reader (confound control) | 0.755 (p=0.0005, r0140) | 0.755 (p=0.0005, r0080) | yes: the control beats the analytic / continental taxonomy in both runs |

## Run A

Record entries: 154 · hash chain intact: **True** · frozen taxonomies: 10 · experiment runs: 20

| record | taxonomy | lang | instrument | options | testable units | accuracy | null mean | chance-corrected | 95% CI (accuracy) | p (perm.) |
|---|---|---|---|---|---|---|---|---|---|---|
| r0140 | T_translated | en | talkie | default | 25/25 | 0.878 | 0.503 | 0.755 | 0.80-0.94 | 0.0005 |
| r0142 | T_nation | en | talkie | default | 22/25 | 0.590 | 0.136 | 0.526 | 0.47-0.71 | 0.0005 |
| r0138 | T_retro | en | talkie | default | 21/25 | 0.483 | 0.243 | 0.317 | 0.34-0.62 | 0.0015 |
| r0062 | six | zh | lex | default | 21/23 | 0.455 | 0.157 | 0.354 | 0.32-0.60 | 0.0005 |
| r0068 | genre | zh | lex | default | 22/23 | 0.448 | 0.169 | 0.336 | 0.30-0.61 | 0.0005 |
| r0066 | region | zh | lex | default | 22/23 | 0.382 | 0.166 | 0.259 | 0.24-0.54 | 0.0020 |
| r0102 | hanshu_yiwenzhi | zh | lex | default | 20/23 | 0.327 | 0.110 | 0.244 | 0.20-0.47 | 0.0010 |
| r0064 | era | zh | lex | default | 23/23 | 0.314 | 0.239 | 0.100 | 0.17-0.47 | 0.1824 |
| r0078 | genre | zh | lex_tr | default | 22/23 | 0.462 | 0.167 | 0.354 | 0.30-0.63 | 0.0005 |
| r0076 | six | zh | lex_tr | default | 21/23 | 0.430 | 0.153 | 0.327 | 0.28-0.58 | 0.0020 |

- **Recognition probe**, r0034, params {}: prober_a named the source book of 33/40 masked passages (82%); prober_b named the source book of 35/35 masked passages (100%)
- **Instrument validation (H-C2)**, r0055, instrument `lex`: mean within-book percentile of the pre-registered Daoist-leaning chapters = **95.4** (permutation p = 0.0001); Guanzi: {'Neiye': 99.3, 'Xinshushang': 93.9, 'Xinshuxia': 95.3, 'Baixin': 96.6}; Han_Feizi: {'Jielao': 95.5, 'Yulao': 91.8}
- **Instrument validation (H-C2)**, r0057, instrument `lex_tr`: mean within-book percentile of the pre-registered Daoist-leaning chapters = **97.1** (permutation p = 0.0001); Guanzi: {'Neiye': 99.3, 'Xinshushang': 98.0, 'Xinshuxia': 93.9, 'Baixin': 95.3}; Han_Feizi: {'Jielao': 99.1, 'Yulao': 97.3}
- **Tomb test (H-C3)**, r0070, taxonomy `six`, instrument `lex`, options {'taxonomy_id': 'six', 'instrument': 'lex'}: label shares of the sealed manuscript = {'Daoist': 0.588, 'Legalist': 0.176, 'School of Names': 0.235}; dominant share 0.588; margin percentile vs transmitted books 61; dominant-share percentile 57
- **Tomb test (H-C3)**, r0089, taxonomy `six`, instrument `lex`, options {'taxonomy_id': 'six', 'instrument': 'lex', 'strip_lacunae': True}: label shares of the sealed manuscript = {'Daoist': 0.647, 'Legalist': 0.176, 'School of Names': 0.176}; dominant share 0.647; margin percentile vs transmitted books 61; dominant-share percentile 61
- **Recognition probe**, r0104, params {'exclude_passages': ['zh_16_096']}: prober_a named the source book of 33/40 masked passages (82%); prober_b named the source book of 32/35 masked passages (91%)
- **Recognition probe**, r0111, params {'exclude_passages': ['zh_16_096']}: prober_a named the source book of 33/40 masked passages (82%); prober_b named the source book of 31/34 masked passages (91%)
- **Hindsight gap (H-W2)**, r0136: G = **0.024** (95% CI -0.028 to 0.078); modern-minus-1930 advantage on the retrospective taxonomy 0.028, on the 1930 taxonomy 0.004

## Run B

Record entries: 88 · hash chain intact: **True** · frozen taxonomies: 9 · experiment runs: 13

| record | taxonomy | lang | instrument | options | testable units | accuracy | null mean | chance-corrected | 95% CI (accuracy) | p (perm.) |
|---|---|---|---|---|---|---|---|---|---|---|
| r0080 | T_lang | en | talkie | default | 25/25 | 0.878 | 0.503 | 0.755 | 0.80-0.94 | 0.0005 |
| r0078 | T_retro | en | talkie | default | 25/25 | 0.687 | 0.335 | 0.529 | 0.57-0.80 | 0.0005 |
| r0082 | T_1930 | en | talkie | default | 24/25 | 0.388 | 0.167 | 0.265 | 0.26-0.52 | 0.0005 |
| r0059 | T_six | zh | lex | strip_lacunae=True, exclude_units=['Sunzi_Bingfa', 'Wuzi', 'Sima_Fa', 'Wei_Liaozi', 'Liutao'] | 16/20 | 0.657 | 0.186 | 0.579 | 0.53-0.78 | 0.0005 |
| r0044 | T_six | zh | lex | strip_lacunae=True | 21/25 | 0.583 | 0.188 | 0.486 | 0.44-0.72 | 0.0005 |
| r0047 | T_yiwenzhi_nine | zh | lex | strip_lacunae=True | 20/25 | 0.402 | 0.110 | 0.328 | 0.25-0.56 | 0.0005 |
| r0050 | T_literary_form | zh | lex | strip_lacunae=True | 21/25 | 0.401 | 0.190 | 0.261 | 0.27-0.54 | 0.0100 |
| r0053 | T_era | zh | lex | strip_lacunae=True | 21/25 | 0.140 | 0.189 | -0.060 | 0.06-0.23 | 0.6952 |

- **Instrument validation (H-C2)**, r0016, instrument `lex`: mean within-book percentile of the pre-registered Daoist-leaning chapters = **95.0** (permutation p = 0.0001); Guanzi: {'Neiye': 99.3, 'Xinshushang': 95.3, 'Xinshuxia': 93.9, 'Baixin': 98.0}; Han_Feizi: {'Jielao': 93.6, 'Yulao': 90.0}
- **Instrument validation (H-C2)**, r0041, instrument `lex_tr`: mean within-book percentile of the pre-registered Daoist-leaning chapters = **96.8** (permutation p = 0.0001); Guanzi: {'Neiye': 99.3, 'Xinshushang': 98.0, 'Xinshuxia': 93.9, 'Baixin': 95.3}; Han_Feizi: {'Jielao': 99.1, 'Yulao': 95.5}
- **Tomb test (H-C3)**, r0062, taxonomy `T_six`, instrument `lex`, options {'taxonomy_id': 'T_six', 'instrument': 'lex', 'strip_lacunae': True}: label shares of the sealed manuscript = {'Daoist': 0.824, 'Legalist': 0.176}; dominant share 0.824; margin percentile vs transmitted books 87; dominant-share percentile 57
- **Hindsight gap (H-W2)**, r0075: G = **0.016** (95% CI -0.046 to 0.077); modern-minus-1930 advantage on the retrospective taxonomy -0.010, on the 1930 taxonomy -0.026

## Measured throughput (run A)

- Net wall-clock time: 1.81 h (gross 2.67 h, of which 0.86 h infrastructure downtime)
- Rival taxonomies formalized with citations: 11 (6.07 per hour); controlled tests run: 15 (8.28 per hour)
- Human baseline: 14.63 minutes for one taxonomy (one team member who is familiar with these texts; single timed trial; labels with known answers were filled from memory and a supporting page was then looked up). Lab: 9.9 minutes per taxonomy with all other lab work included, a factor of **1.48**. Partition agreement between the human and the agent taxonomy: adjusted Rand index 0.609.

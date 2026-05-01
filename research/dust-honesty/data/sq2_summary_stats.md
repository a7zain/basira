# SQ2 summary stats — operational 228-scene set

**Input:** `sq2_dbb_operational.csv`  
**Thresholds:** V4 = +0.034 (all AOIs), V3 = +0.053 (KSP only).  
**Coverage:** 228 (aoi, year, month) rows = 3 AOIs × 76 months (2020-01 … 2026-04).

## 1. Headline numbers

| AOI | months | usable | V4 fires | V4 % of usable | V3 fires (KSP only) | V3 % | AOI cloud > 30% | cloud % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| King Salman Park | 76 | 74 | 24 | 32.4% | 22 | 29.7% | 0 | 0.0% |
| Qiddiya core | 76 | 76 | 57 | 75.0% | — | — | 0 | 0.0% |
| Diriyah Gate | 76 | 76 | 9 | 11.8% | — | — | 1 | 1.3% |

## 2. Temporal pattern

### King Salman Park

**Peak DBB:** +0.2178 on 2024-08-02 (`20240802T072619_20240802T073147_T38RPN`)

**Top 5 highest DBB:**

| rank | scene_date | DBB | V4 | cloud_aoi% | system_index |
|---:|---|---:|:-:|---:|---|
| 1 | 2024-08-02 | +0.2178 | ✓ | 0.00 | `20240802T072619_20240802T073147_T38RPN` |
| 2 | 2025-06-05 | +0.1666 | ✓ | 0.00 | `20250605T073031_20250605T073443_T38RPN` |
| 3 | 2024-06-23 | +0.1622 | ✓ | 0.00 | `20240623T072619_20240623T073149_T38RPN` |
| 4 | 2024-07-08 | +0.1540 | ✓ | 0.00 | `20240708T072621_20240708T073143_T38RPN` |
| 5 | 2025-07-03 | +0.1495 | ✓ | 0.00 | `20250703T072641_20250703T073357_T38RPN` |

**Monthly distribution of V4 fires (by calendar month):**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 1 | 1 | 3 | 5 | 4 | 3 | 4 | 3 | 0 | 0 |

### Qiddiya core

**Peak DBB:** +0.2038 on 2021-07-09 (`20210709T072619_20210709T073706_T38RPN`)

**Top 5 highest DBB:**

| rank | scene_date | DBB | V4 | cloud_aoi% | system_index |
|---:|---|---:|:-:|---:|---|
| 1 | 2021-07-09 | +0.2038 | ✓ | 14.20 | `20210709T072619_20210709T073706_T38RPN` |
| 2 | 2024-08-02 | +0.1961 | ✓ | 10.49 | `20240802T072619_20240802T073147_T38RPN` |
| 3 | 2023-08-18 | +0.1935 | ✓ | 0.00 | `20230818T072619_20230818T073626_T38RPN` |
| 4 | 2025-06-05 | +0.1879 | ✓ | 0.00 | `20250605T073031_20250605T073443_T38RPN` |
| 5 | 2021-06-14 | +0.1875 | ✓ | 6.97 | `20210614T072621_20210614T073148_T38RPN` |

**Monthly distribution of V4 fires (by calendar month):**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4 | 4 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 5 | 2 |

### Diriyah Gate

**Peak DBB:** +0.0663 on 2022-05-10 (`20220510T072621_20220510T073151_T38RPN`)

**Top 5 highest DBB:**

| rank | scene_date | DBB | V4 | cloud_aoi% | system_index |
|---:|---|---:|:-:|---:|---|
| 1 | 2022-05-10 | +0.0663 | ✓ | 0.00 | `20220510T072621_20220510T073151_T38RPN` |
| 2 | 2025-05-09 | +0.0594 | ✓ | 0.00 | `20250509T072619_20250509T074216_T38RPN` |
| 3 | 2025-06-05 | +0.0555 | ✓ | 0.00 | `20250605T073031_20250605T073443_T38RPN` |
| 4 | 2025-07-03 | +0.0471 | ✓ | 0.00 | `20250703T072641_20250703T073357_T38RPN` |
| 5 | 2022-07-04 | +0.0436 | ✓ | 0.00 | `20220704T072619_20220704T073152_T38RPN` |

**Monthly distribution of V4 fires (by calendar month):**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 2 | 2 | 3 | 2 | 0 | 0 | 0 | 0 | 0 |

## 3. Cross-check vs sq1bc_combined_calibration_confirmed.csv

- Overlap rows (calibration_subset_match=True): **57**
- Passes (|sq2_dbb − cal_dbb| < 1e-4): **55**
- Failures: **2**

| aoi | year-month | system_index | sq2_dbb | cal_dbb | delta |
|---|---|---|---:|---:|---:|
| king_salman_park | 2021-02 | `20210204T073111_20210204T073144_T38RPN` | -0.0884834192 | -0.1049705190 | +0.0164870997 |
| king_salman_park | 2026-02 | `20260213T074301_20260213T074302_T38RPN` | 0.0068750259 | 0.0107541146 | -0.0038790887 |

## 4. Self-reference test

Performed at start of `sq2_apply_flag.py` run: pick KSP, set `test_scene = ref_scene`, compute DBB, assert `|DBB| < 1e-9`.
Run aborts if the test fails. Successful completion of the operational sweep implies the test passed.

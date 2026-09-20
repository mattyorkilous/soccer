# Does the match dataset cover the 2026 World Cup?

Research for [#2](https://github.com/mattyorkilous/world-cup-predictor/issues/2), part of [#1](https://github.com/mattyorkilous/world-cup-predictor/issues/1).

**Date of investigation:** 2026-09-20.
**Verified firsthand** means: downloaded and queried on this machine on 2026-09-20. **Read** means: taken from a cited page.

---

## Answers in one paragraph

Coverage is **not** the problem — the 2026 World Cup is there, complete, all 104 matches. Venue granularity **is** the problem: `patateriedata/all-international-football-results` has no city and no coordinates, only host country, so **travel distance cannot be derived from it at all**. Rest days *can* (they need only date + team, which we have). The fix is cheap and does not require leaving Kaggle: the upstream dataset `martj42/international-football-results-from-1872-to-2017` is the same data **with a `city` column**, 100% populated, CC0, and it also covers both held-out World Cups exactly. The tradeoff is freshness — martj42 is hand-maintained and currently ~3.5 weeks stale, where patateriedata is automated and current to 2 days ago.

---

## 1. Coverage — verified firsthand

Downloaded with the project's own dependency, no credentials required:

```
kagglehub.dataset_download('patateriedata/all-international-football-results')
→ .../versions/1747   (version 1747, downloaded 2026-09-20)
```

The download works **anonymously**. There is no `~/.kaggle/kaggle.json` on this machine and `KAGGLE_USERNAME`/`KAGGLE_KEY` are unset; `force_download=True` still succeeded. So CI/fresh clones will not hit a credentials wall for this dataset.

| Check | Result |
|---|---|
| Files | `all_matches.csv` (3.36 MB), `countries_names.csv` (10.5 KB) |
| Rows | 51,766 |
| Date range | 1872-11-30 → **2026-09-18** (2 days before this investigation) |
| 2026 World Cup rows | **104** — `2026-06-11` → `2026-07-19` |
| 2022 World Cup rows | 64 |
| 2026 host countries | United States, Canada, Mexico |

104 is exactly right for the 48-team format (72 group + 32 knockout). The tournament is present end to end, including the final: `2026-07-19 | Spain 1–0 Argentina`.

**Conclusion: the headline evaluation test (2022 + 2026 World Cups held out) is fully supported by the data as it stands.** Both tournaments are complete.

### Cross-validation

The independent `martj42` dataset agrees exactly: 104 matches in 2026, 64 in 2022, same final (`Spain 1–0 Argentina`, 2026-07-19). Two independently-published datasets agreeing on counts and on the final is decent evidence the 2026 records are real and complete rather than padded or projected.

---

## 2. Update cadence and mechanism

**Mechanism — read.** The Kaggle page's own description is: *"An automatically updated dataset of international football results since 1872"* ([dataset page](https://www.kaggle.com/datasets/patateriedata/all-international-football-results), `<meta name="description">`). A Kaggle search result titles the notebook page *"International Football Results: Daily Updates"*. So: automated, publisher-run, not hand-curated.

**Cadence — verified firsthand, from this machine's kagglehub cache.** The cache retains a `.complete` marker per downloaded version, and the marker's mtime bounds when that version was current:

| Version | Seen on this machine |
|---|---|
| 505 | 2025-06-16 |
| 507 | 2025-06-18 |
| 699 | 2026-01-17 |
| **1747** | **2026-09-20** |

That is **1,048 versions published between 2026-01-17 and 2026-09-20** — roughly 4 per day. Whatever the job is, it runs multiple times daily and has done so continuously for at least 15 months.

**Will it keep pace through 2030 qualification?** On the evidence, yes — this is the dataset's single clearest strength. It is automated, it has a multi-year unbroken track record, and it is currently within 2 days of live. The standing risk is the ordinary one for a single-maintainer Kaggle dataset: it is a personal publication with no SLA, and if the publisher stops, it stops silently. Worth a cheap staleness assertion in the pipeline (fail if `max(date)` is older than ~N weeks) rather than a mitigation plan.

---

## 3. Full schema — verified firsthand

### `all_matches.csv` — 8 columns, all of them

| Column | Type | Consumed by `clean_data.py`? |
|---|---|---|
| `date` | String | yes → cast to `Date` |
| `home_team` | String | yes → `team_home` |
| `away_team` | String | yes → `team_away` |
| `home_score` | Int64 | yes → `goals_for_home` |
| `away_score` | Int64 | yes → `goals_for_away` |
| `tournament` | String | yes → `classify_tournament` + `importance` |
| `country` | String | name-normalised only; **otherwise unused** |
| `neutral` | Boolean | **not consumed** |

### `countries_names.csv` — 4 columns

`original_name`, `current_name`, `color_code`, `secondary_color_code` (290 rows).
`clean_data.py` takes only the two `*_name` columns (via `cs.ends_with('name')`). The two colour columns are unused — they are presentation hex codes, potentially handy for the Altair visuals in #1, nothing more.

### The critical finding: venue granularity

**There is no city column and no coordinates anywhere in this dataset.** The only geographic field is `country`, the host nation, plus the `neutral` boolean. That is the entire geographic content of both files.

Consequences for the two features #1 wants:

- **Rest days — already derivable, no new data needed.** Rest days are a function of `date` and team identity only: per team, sort matches by date and diff. `patateriedata` supports this today. This is worth separating from travel distance, because the ticket bundles them and only one is actually blocked.
- **Travel distance — not derivable at any useful resolution.** Country-level is far too coarse for the very tournaments this project cares about. In 2026 the USA alone hosts matches in Seattle, Inglewood, Santa Clara, Arlington, Houston, Kansas City, Atlanta, Miami Gardens, Foxborough, Philadelphia and East Rutherford — a Seattle→Miami leg is ~4,400 km and is indistinguishable from a zero-km move under a `country`-only model. The same objection applies to 2030 across Spain/Portugal/Morocco plus the South American centenary matches.

**Travel distance is blocked on this dataset. It needs a source with venue city or coordinates.**

### Secondary finding, unrelated to the ticket but worth a line

`classify_tournament` in `src/soccer/clean_data.py` matches tournament labels against hardcoded lists, with `.otherwise('Friendly')` as the fallback. **399 matches from 2024 onward are labelled as real competitions but fall through to `Friendly` (importance 10)** — including `Southeast Asian Champ` (53), `COSAFA Cup` (44), `CONCACAF Series` (35), `FIFA Series` (33), and `Friendly tournament` (92). Miscategorised match importance feeds directly into the elo update weighting. Not this ticket's question; flagging it because the rebuild in #1 touches exactly this code.

---

## 4. Alternatives

The dataset is not short on coverage, so the alternatives question reduces to: **what is the cheapest route to venue city/coordinates?** Assessed in that light.

### Recommended: `martj42/international-football-results-from-1872-to-2017` — verified firsthand

This is the well-known upstream of this data family, published both on [Kaggle](https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017) and [GitHub](https://github.com/martj42/international_results).

Downloaded and queried on 2026-09-20 (also anonymous, no credentials):

| Check | Result |
|---|---|
| `results.csv` | 49,547 rows × **9 columns** |
| Columns | `date, home_team, away_team, home_score, away_score, tournament, **city**, country, neutral` |
| `city` nulls | **0** — zero blanks in every decade checked (1970s–2020s) |
| Distinct cities | 2,093 |
| Date range | 1872-11-30 → 2026-08-26 |
| 2026 World Cup | 104 matches, 17 cities (Arlington, Atlanta, Dallas, East Rutherford, Foxborough, Guadalupe, Houston, Inglewood, Kansas City, Mexico City, Miami Gardens, Philadelphia, Santa Clara, Seattle, Toronto, Vancouver, Zapopan) |
| 2022 World Cup | 64 matches |
| Licence | **CC0-1.0** (GitHub repo metadata) |
| Bonus files | `goalscorers.csv` (47,914 rows: scorer, minute, own_goal, penalty), `shootouts.csv` (683 rows: winner, first_shooter), `former_names.csv` (date-scoped historical renames) |

**Provenance — read.** The README states: *"The data is gathered from several sources including but not limited to Wikipedia, rsssf.com, and individual football associations' websites."* Inclusion criteria: men's full internationals only, excluding Olympics, B-teams, U-23 and league selects. So martj42 is *already* the curated aggregation of two of the four alternatives the ticket names (RSSSF, Wikipedia) — hand-checked over ~9 years and 523 stars. Adopting it is strictly cheaper than re-doing that scrape.

**Cost to switch — moderate, and confined to one file.** `clean_data.py` would need:
- `classify_tournament`'s label lists rewritten. The vocabularies are disjoint: `'World Cup'` → `'FIFA World Cup'`, `'World Cup qualifier'` → `'FIFA World Cup qualification'`, etc. (202 distinct labels vs patateriedata's 231). This is the bulk of the work, and it is the same code already flagged as buggy above — so the rewrite pays down existing debt rather than adding new.
- `countries_names.csv` → `former_names.csv`. Different shape (`current, former, start_date, end_date`) but *date-scoped*, which is more correct than the current flat rename map.
- `swap_underscore` and everything downstream work unchanged — the column names are identical.

**Cost to switch — the real tradeoff is freshness.** Verified via the GitHub API: 88 commits in the 12 months to 2026-09-20, **bursty rather than steady** — 35 commits in June 2026 and 22 in July (the World Cup), but only 1 in August, and a **maximum gap of 58 days**. Last push 2026-08-26, so the September 2026 international window is not yet in it. martj42 lags patateriedata by ~3 weeks right now.

For this project that lag is close to irrelevant: the headline test is two *completed* tournaments, and 2030 qualification needs periodic refreshes, not same-day results. But it should be a conscious choice, and a staleness assertion is worth more here than against patateriedata.

### Rejected: enrich patateriedata by joining martj42's `city` — verified firsthand, does not work well enough

Tested directly, joining on `(date, home_team, away_team)` and retrying unmatched rows with home/away swapped (neutral-venue fixtures are stored in either orientation):

| Era | City matched |
|---|---|
| All time | 42,382 / 51,766 = **81.9%** |
| 1990+ | 88.9% |
| 2000+ | 89.6% |
| 2010+ | 89.6% |
| 2020+ | 90.5% |
| 2024+ | 89.2% |

**~10% of modern matches get no city even after the orientation retry.** The residue is partly team-name divergence (e.g. the Ireland / Northern Ireland split dominates the pre-1920 misses) and partly that patateriedata genuinely carries ~2,200 matches martj42 excludes under its stricter criteria. Carrying two Kaggle datasets, a fuzzy join and a permanent 10% null rate in a travel-distance feature is worse in every dimension than simply using martj42 directly, which is 100% populated by construction.

### The other named alternatives

| Source | Verdict | Cost |
|---|---|---|
| **football-data.co.uk** | **Disqualified — wrong sport scope.** Covers *domestic club leagues only*: England E0–EC, Scotland SC0–SC3, Germany D1/D2, plus Italy, Spain, France, Netherlands, Belgium, Portugal, Turkey, Greece. No national-team fixtures at all. ([data page](https://www.football-data.co.uk/data.php), [notes](https://www.football-data.co.uk/notes.txt)) | n/a |
| **RSSSF** | The archival primary source, and genuinely authoritative — but published as *ASCII and HTML pages* with **no API and no bulk download**; navigation is per-page. ([rsssf.org](https://www.rsssf.org/)) | **High.** A bespoke parser per tournament series, against inconsistent decades-old text. Already done for us by martj42. |
| **Wikipedia** | Per-tournament articles do carry venue and city reliably, and are the most complete venue source for recent World Cups. | **High.** Infobox/table parsing across hundreds of articles, unstable markup, name reconciliation. Also already done for us by martj42. |
| **ESPN** | Has fixtures, results and venues, but no documented public bulk API; would mean scraping undocumented JSON endpoints, with ToS risk and no stability guarantee. | **High**, plus ongoing breakage. |

Every remaining alternative is a scrape whose output would be *a less-checked version of martj42*. That is the decisive point: martj42 is not merely one more option, it is the finished form of two of them.

### If coordinates (not just city) are wanted

`city` is a name, not a lat/long, so a great-circle travel distance needs one more step: geocode the distinct city names once and cache the result. The cardinality makes this trivial — **2,093 distinct cities all-time**, and only **17 for the 2026 World Cup**. A one-off static lookup table committed to the repo (the same shape as the existing `lookup/confederation_mapping.csv`) is sufficient; no geocoding API needs to run at pipeline time. Note one cleaning wrinkle spotted in the 2026 data: both `Dallas` and `Arlington` appear for the same metro venue, so the lookup wants a small alias map.

---

## Recommendation

1. **Coverage is fine — do not change source on coverage grounds.** 2022 and 2026 are both complete. Close the coverage question.
2. **Split the two features.** Rest days are unblocked today on the current dataset. Only travel distance is blocked.
3. **If travel distance is wanted, switch to `martj42/international-football-results-from-1872-to-2017`.** It is the upstream, it is CC0, it has 100%-populated `city`, it covers both held-out tournaments exactly, and it throws in goalscorers and shootouts. The cost is a rewrite of `classify_tournament`'s label lists — code that needs rewriting anyway (see the 399 misclassified matches above).
4. **Accept the freshness tradeoff explicitly**, or keep patateriedata as a freshness check. Do not attempt the two-dataset join — it was tested and leaves ~10% of modern matches without a city.
5. **Geocode once into a committed lookup table**, not at pipeline time. 2,093 cities all-time.

---

## Sources

Verified firsthand on 2026-09-20 (downloaded and queried locally):
- `patateriedata/all-international-football-results` v1747 — schema, row counts, date range, 2026/2022 World Cup counts, absence of city/coordinates
- `martj42/international-football-results-from-1872-to-2017` v137 — schema incl. `city`, null counts, World Cup counts, bonus files
- The join-rate experiment between the two
- kagglehub cache version markers (cadence)
- `classify_tournament` fallthrough count, run against the project's own `src/soccer/clean_data.py`

Read:
- [Kaggle — Updated International football matches since 1872](https://www.kaggle.com/datasets/patateriedata/all-international-football-results) — "automatically updated" description
- [Kaggle — International football results from 1872 to 2026](https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017)
- [GitHub — martj42/international_results](https://github.com/martj42/international_results) — README provenance, CC0-1.0 licence, commit cadence via API
- [football-data.co.uk data page](https://www.football-data.co.uk/data.php) and [notes](https://www.football-data.co.uk/notes.txt) — club-only scope
- [RSSSF](https://www.rsssf.org/) — format and absence of bulk access
- [Wikipedia — RSSSF](https://en.wikipedia.org/wiki/RSSSF)

# Goals-model implementation landscape: Dixon-Coles, bivariate Poisson, XGBoost

Research for [issue #3](https://github.com/mattyorkilous/world-cup-predictor/issues/3). Settled beforehand
(issue #1): one unified goals model, results falling out of the predicted scoreline. Only the
implementation route was open.

Sources are libraries' own source code, package registries, and papers. Blog posts appear only where
the blog *is* the primary source (the package author's own benchmark; an author replicating a paper's
numbers).

---

## TL;DR — recommendation

1. **Use `penaltyblog.models.DixonColesGoalModel`.** It clears all three gates — actively maintained
   (release 1.12.2, 2026-09-13), fits 50k matches in **3.2 s**, and takes per-match `weights` — plus a
   per-match `neutral_venue` flag this project would otherwise have had to add by hand. Zero MLE code.
2. **Expect to outgrow it in exactly one place**, and only one: it has no per-match covariate slot, so
   the settled decision to keep Elo as a feature cannot be expressed through its API. When that bites,
   hand-roll the likelihood (~40 lines) and keep penaltyblog installed as the characterization-test
   oracle — same data, assert same log-likelihood. That is the strangler pattern the map already picked.
3. **Skip the bivariate Poisson.** Its correlation parameter is provably incapable of changing
   win/draw/loss probabilities (§4), it ranks last in the package author's own backtest, and it cost
   11× the fit time in my benchmark.
4. **Keep the Dixon-Coles tau correction.** One parameter, free in the library, gain ≈ 0.0001 RPS —
   tiny but non-negative. Do not build anything around it.
5. **Half-life: start at 3 years, tune over 1–6. Drop the 8-year guess** — the literature contradicts
   it (§3). Adopt Ley et al.'s published FIFA importance weights (1 / 2.5 / 3 / 4) rather than inventing a scale.
6. **XGBoost: long format, one `count:poisson` model with an `is_home` flag**, `sample_weight` =
   decay × importance. Do not attempt multi-output. Fix score-grid correlation post hoc if at all.

The strongest single finding across all five questions: **the model class barely matters; the features
and the weighting do.** Three independent backtests below put logistic, Poisson, XGBoost and ensembles
within ~0.01 RPS of each other, while a feature change moved RPS by 0.08.

---

## 1. Is there a maintained Python library, or is hand-rolling the realistic path?

**There is exactly one library, and it is a good one: [penaltyblog](https://github.com/martineastwood/penaltyblog).**

### Judged against the three gates

| Gate | Verdict | Evidence |
|---|---|---|
| Actively maintained | **Pass** | MIT, 227 stars, 0 open issues. Latest commit `chore: release v1.12.2` on 2026-09-13. Releases roughly every 4–8 weeks through 2025–2026 (v1.6.2 → v1.12.2). Requires Python ≥ 3.10. ([repo](https://github.com/martineastwood/penaltyblog), [PyPI](https://pypi.org/project/penaltyblog/)) |
| ~50k matches | **Pass, comfortably** | Measured: 3.2 s (§1.3). Loss and analytic gradient are Cython; optimisation is `scipy.optimize.minimize` with `jac` supplied. |
| Per-sample weights | **Pass, first-class** | `weights` is a constructor argument on every goal model, applied per match inside the likelihood. |

### What the source actually does

The constructor signature ([`penaltyblog/models/dixon_coles.py`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/dixon_coles.py)):

```python
DixonColesGoalModel(
    goals_home, goals_away, teams_home, teams_away,
    weights=None,        # per-match weight
    neutral_venue=None,  # per-match 0/1; when 1, home advantage is excluded
)
```

The weight enters the likelihood per match, which is precisely what "exponential decay × match
importance" needs ([`loss.pyx`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/loss.pyx)):

```python
total_llk += ((llk_home + llk_away) + adjustment) * weights[i]
```

Two things worth noticing that are not advertised in the docs:

- **`neutral_venue` is per match, not per model.** `lambda_home = exp(hfa * (1 - neutral_venue[i]) + ...)`.
  For an international dataset — where World Cups, most finals and many qualifiers are on neutral ground —
  this is exactly the right shape, and it is the part that would be most annoying to retrofit onto a hand-roll.
  There is even a guard that pins home advantage to 0 when every training match is neutral, because the
  parameter is otherwise unidentified.
- **There is a weight helper**, matching the Dixon-Coles paper's decay
  ([`utils.py`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/utils.py)):
  `dixon_coles_weights(dates, xi=0.0018, base_date=None)` → `exp(-xi * days_ago)`. See §3 for why
  `0.0018` is the wrong default for *this* project.

The same signature covers `BivariatePoissonGoalModel`, `NegativeBinomialGoalModel`,
`ZeroInflatedPoissonGoalsModel`, `WeibullCopulaGoalsModel`, `PoissonGoalsModel` and Bayesian/hierarchical
variants — so the model slate in issue #1 (Dixon-Coles, Poisson GLM) is one import, not two projects.

### 1.3 Measured: does it really handle 50k?

Run locally against penaltyblog 1.12.2, 50,000 synthetic matches, 250 teams (502 free parameters),
weights = 3-year half-life decay × FIFA importance, random per-match neutral-venue flags:

```
DixonColes:        fit  3.2s   n_params=502   rho=-0.011   predict 0.001s
BivariatePoisson:  fit 36.4s   n_params=502   lambda3=0.050  predict 0.001s
```

Scale is a non-issue. *Caveat:* synthetic data — the timings are real, the parameter values are not a
claim about real football. (`rho ≈ -0.011` on data generated as genuinely independent is a sanity check
that the estimator is not inventing dependence.)

### The competition

- **No other Python library exists.** A GitHub search for Python repos mentioning Dixon-Coles pushed
  since mid-2025 returns only one-off project repos — top result 32 stars, all of them somebody's
  personal World Cup predictor, none of them installable libraries.
- **`goalmodel` ([opisthokonta/goalmodel](https://github.com/opisthokonta/goalmodel)) is R, not Python.**
  It is the best-documented implementation in the space, but it is on the wrong side of the stack decision.
- **`statsmodels` GLM** gets you a weighted Poisson but not the tau correction or the bivariate form;
  it is the hand-roll path wearing a library's clothes.

### Where hand-rolling still wins — and it matters here

**penaltyblog's goal models take team identities and weights. They do not take per-match covariates.**
There is no slot for Elo, no slot for tournament-stage dummies, no slot for anything. Issue #1 settled
that Elo stays as a feature alongside attack/defence strengths — that decision **cannot be expressed
through penaltyblog's API**.

This does not change the recommendation, it schedules it. The hand-roll is genuinely small: a negative
log-likelihood over `exp(hfa*(1-neutral) + attack[h] - defence[a])`, the four tau cells, a `weights[i]`
multiplier, and `scipy.optimize.minimize`. Roughly 40 lines. The genuinely fiddly part — the analytic
gradient — is already written in penaltyblog's `gradients.pyx` as a line-by-line reference, and once
you have your own version, `penaltyblog` becomes the oracle for a characterization test: fit both on the
same data with the same weights, assert the same log-likelihood to 6 decimals. That is the migration
pattern the map already committed to.

So: **library first, hand-roll when Elo-as-covariate forces it, library stays installed as the test oracle.**

---

## 2. The low-score (tau) correction — what it is, and does it still earn its place?

### What it is, exactly

From Michels, Ötting & Karlis, *Extending the Dixon and Coles model* (arXiv:[2307.02139](https://arxiv.org/abs/2307.02139), §2.1) —
Karlis being the author of the bivariate Poisson football model itself:

$$P(X_1 = x_1, X_2 = x_2) = \tau_{\lambda_1,\lambda_2}(x_1,x_2)\cdot\frac{\lambda_1^{x_1}e^{-\lambda_1}}{x_1!}\cdot\frac{\lambda_2^{x_2}e^{-\lambda_2}}{x_2!}$$

$$\tau_{\lambda_1,\lambda_2}(x_1,x_2) = \begin{cases}
1 - \lambda_1\lambda_2\omega & x_1 = 0,\ x_2 = 0\\
1 + \lambda_1\omega & x_1 = 0,\ x_2 = 1\\
1 + \lambda_2\omega & x_1 = 1,\ x_2 = 0\\
1 - \omega & x_1 = 1,\ x_2 = 1\\
1 & \text{otherwise}
\end{cases}$$

subject to $\max(-1/\lambda_1, -1/\lambda_2) \le \omega \le \min(1/\lambda_1\lambda_2, 1)$.

It is a **single extra parameter that moves probability mass between four cells** (0-0, 0-1, 1-0, 1-1)
and leaves everything else as the product of two independent Poissons. penaltyblog's Cython loss
implements exactly this, with `rho` playing the role of `ω`.

### Does it still earn its place?

Three lines of evidence, in increasing order of discomfort:

**(a) It helps, barely.** The package author's own rolling time-based backtest — Eredivisie 2015-16
through 2024-25, evaluated from 2023-24 on, scored on RPS
([pena.lt/y, 2025-03-10](https://pena.lt/y/2025/03/10/which-model-should-you-use-to-predict-football-matches/)):

| Model | RPS |
|---|---|
| **Dixon and Coles** | **0.1914** |
| Weibull Count | 0.1914 |
| Poisson | 0.1915 |
| Zero-inflated Poisson | 0.1915 |
| Negative Binomial | 0.1916 |
| Bivariate Poisson | 0.1916 |

Dixon-Coles wins — by 0.0001 RPS. For scale, FiveThirtyEight's own accounting of what their
upgrades bought (§5) puts *adding expected goals to SPI* at 0.0018 RPS. The tau correction is worth
roughly a twentieth of that.

**(b) The pattern it corrects has drifted.** Petretta, Schiavon & Diquigiovanni
(arXiv:[2103.07272](https://arxiv.org/abs/2103.07272)) replicated Dixon & Coles' own Section 3 diagnostic on
9,130 top-five-European-league matches from 2014–2019. Their Table 1 reports observed/independent
frequency ratios (×100, grey = significant at 0.05):

```
Home \ Away    0        1        2        3        4
  0          99.47    92.95   100.68   114.96   139.57
  1          94.46   102.11   102.75   103.21   107.72
  2          99.01   103.40   102.69    89.23    84.39
  3         108.13   101.23    91.24    99.11    59.27
  4         121.20    98.78    88.63    68.19    52.58
```

The 0-0 cell — tau's headline case — sits at 99.47 and is **not** significant. The 0-1 and 1-0 cells are.
But the biggest deviations by far are in the *high*-score corners (0-4 at 139.6, 4-4 at 52.6, 3-4 at 59.3),
which is exactly where tau is defined to do nothing. They separately reject conditional independence
outside the four cells at p < 0.001.

**(c) Purpose-built replacements barely beat it.** The same paper's Mar-Co model, designed specifically
to fix that, beat Dixon-Coles on cumulative RPS across five leagues and five seasons — at a permutation
test p-value of **0.14**. Their own conclusion: "it cannot be excluded that the two models are identical
in terms of performance."

### Verdict

**Take it, because in penaltyblog it costs nothing. Do not build anything around it, and do not treat
it as a source of accuracy.** The honest expectation is ≈ 0.0001 RPS.

One caveat specific to this project: tau is calibrated on club football, where 0-0 and 1-1 dominate.
International football has a fatter blowout tail, and the headline held-out test in issue #1 is the
2022 and 2026 World Cups. The four cells tau touches are a smaller share of that distribution.
Worth checking `rho`'s fitted value and confidence on the real dataset rather than assuming.

---

## 3. Time decay — and the 8-year half-life

### The convention

Two equivalent parameterisations, both exponential:

- **Dixon & Coles (1997):** $\phi(t) = \exp(-\xi t)$.
- **Ley, Van de Wiele & Van Eetvelde (2019):** $w_{\text{time}}(x_m) = (1/2)^{x_m/\text{HalfPeriod}}$,
  with $x_m$ in days — "a match played HalfPeriod days ago only contributes half as much as a match
  played today."

Half-life $= \ln 2 / \xi$. The half-period form is the one to use: it is directly interpretable,
directly tunable, and it is how the international-football literature reports results.

### What Dixon-Coles themselves found

Dixon & Coles optimised $\xi = 0.0065$ **in half-weeks**, on English top-four-tier league and FA Cup
data from the 1990s. Converting: $0.0065 / 3.5 = 0.00186$ per day → **half-life ≈ 373 days, about one
year**. The author of `goalmodel` replicated the exercise on 2005–2014 league data and landed on
$\xi \in [0.0018, 0.0023]$ per day — a half-life of 300–385 days
([opisthokonta.net](https://opisthokonta.net/?p=1013)). penaltyblog's `xi=0.0018` default encodes exactly
this club-football consensus.

### But this project is international football, and international football is different

**Ley, Van de Wiele & Van Eetvelde (2019)**, *Ranking soccer teams on the basis of their current
strength* (arXiv:[1705.09575](https://arxiv.org/abs/1705.09575), *Statistical Modelling*) is the closest
published analogue to this project: 4,268 competitive international matches 2008–2017, weighted maximum
likelihood, weights = **time depreciation × match importance**. They grid-searched half period from half
a year to six years:

| Model class | Optimal half period | RPS |
|---|---|---|
| **Bivariate Poisson** | **3 years** | **0.1651** |
| Independent Poisson | 3 years | 0.1653 |
| Independent Poisson Def. & Att. | 3.5 years | 0.1656 |
| Bivariate Poisson Def. & Att. | 3 years | 0.1656 |
| Thurstone-Mosteller | 3.5 years | 0.1658 |
| Bradley-Terry | 4 years | 0.1659 |

For the Premier League in the same paper, the optima are 390 and 360 days — consistent with Dixon-Coles.
**The international/club gap is real and it is a factor of about three.**

**Groll et al. (2018)** (arXiv:[1806.03208](https://arxiv.org/abs/1806.03208)) independently reproduced this
on *all* international matches 2002–2017 rather than only European ones, Table 3:

| Rank | Model | Half period | avg RPS |
|---|---|---|---|
| 1 | Bivariate Poisson | 1095 d (3 y) | 0.17366 |
| 2 | Bivariate Poisson | 730 d (2 y) | 0.17369 |
| 3 | Bivariate Poisson | 1460 d (4 y) | 0.17382 |
| 4 | Independent Poisson | 1095 d | 0.17382 |
| 7 | Bivariate Poisson | 1825 d (5 y) | 0.17398 |
| 9 | Bivariate Poisson | 365 d (1 y) | 0.17555 |

RPS is already degrading by 5 years, and 1 year is clearly too short.

### So: does the literature corroborate ~8 years?

**No — it contradicts it.** Two independent studies on international football converge on **3 years**,
with a curve that is already worsening at 5 and was never evaluated past 6. Nothing in this literature
supports 8.

There is a plausible origin for the 8-year number, worth naming so it does not come back: **both papers
estimate parameters over an eight-year training window** ("the parameters are estimated by maximum
likelihood on a period of eight years"; "taking into account all matches in the previous 8 years"). Eight
years is the *window*, three years is the *half-life*. Easy to conflate.

### Recommendation

- **Default half-life: 3 years.** Tune over roughly 1–6 years in the walk-forward backtest; treat > 6
  years as out of family and require evidence before accepting it.
- **Adopt Ley et al.'s importance weights** rather than inventing a scale. They are the FIFA
  coefficients, published and defensible: **friendly = 1, confederation or World Cup qualifier = 2.5,
  confederation tournament or Confederations Cup = 3, World Cup = 4.**
- **Consequence worth flagging for the perf work in issue #1:** at a 3-year half-life, an 1872 match
  carries weight $2^{-51} \approx 4\times10^{-16}$. Training "since 1872" is nominal — the *effective*
  training set is roughly the last 15 years. Any parquet-cache or incremental-fit design can lean on
  that, and any claim in the README about a 150-year training set should be phrased honestly.

---

## 4. XGBoost `count:poisson` with two correlated outputs

### What XGBoost actually offers

- `count:poisson` is **univariate**: "Poisson regression for count data, output mean of Poisson
  distribution". `max_delta_step` defaults to 0.7 for it, "used to safeguard optimization"
  ([parameters](https://xgboost.readthedocs.io/en/stable/parameter.html)).
- Multi-output is **not a joint model**. From the
  [multi-output tutorial](https://xgboost.readthedocs.io/en/stable/tutorials/multioutput.html):
  "By default, XGBoost builds one model for each target similar to sklearn meta estimators"; and,
  as of XGBoost 3.0, "the feature is experimental and has limited features… The feature is still under
  development with limited support from objectives and metrics." `multi_strategy=multi_output_tree`
  shares tree *structure* across targets; the loss stays separable per target.

**So there is no route inside XGBoost that models the joint distribution of (home goals, away goals).**
The question is only whether that loss matters.

### Does discarding the correlation matter? Mostly no — and there is a proof

The sharpest evidence is algebraic, from Ley et al. §2.3.2. Under the Karlis-Ntzoufras bivariate Poisson,
$G_i = X_i + X_C$ and $G_j = X_j + X_C$, so:

$$P(GD_m = x) = P(G_i - G_j = x) = P(X_i + X_C - (X_j + X_C) = x) = P(X_i - X_j = x)$$

**The shared component cancels out of the goal difference.** The bivariate Poisson's correlation
parameter *cannot change win/draw/loss probabilities at all* — it only shifts mass between scorelines
of the same margin. Since issue #1 settled that results fall out of the scoreline, this is the single
most load-bearing fact in this document: for the 1X2 outcome, modelling the correlation buys literally
nothing.

Supporting evidence, all pointing the same way:

- Groll et al.: "the bivariate Poisson distribution can only account for (positive) dependencies" —
  and football's low-score dependence is *negative*. They further report that when Groll, Kneib, Mayr &
  Schauberger ran a boosting model selection over EURO data, "the dependency parameter of the bivariate
  Poisson distribution was never updated by the boosting algorithm" — two conditionally independent
  Poissons were sufficient once informative covariates were present.
- penaltyblog's Eredivisie backtest (§2) ranks bivariate Poisson **last** of six.
- My benchmark (§1.3): bivariate Poisson took 11× longer to fit for identical parameter count.
- FiveThirtyEight explicitly chose independence plus a post-hoc patch (§5).

Note the asymmetry worth keeping straight: **the Dixon-Coles tau *does* change 1X2 probabilities**
(it reshapes the 0-0/1-1 draw cells relative to 1-0/0-1), whereas **the bivariate Poisson's λ_C does not**.
That is why tau survives in practice and λ_C does not, even though λ_C looks like the more principled
construction.

### Practical recommendation for the XGBoost slate entry

- **Long format, one model, not two.** One row per team-per-match with an `is_home` flag and the
  opponent's features; predict that team's goals with `count:poisson`. Half the code of two models, and
  the attack/defence signal is shared rather than split. `sample_weight` (sklearn API) / `weight`
  (DMatrix) carries the decay × importance weighting, so the era-weighting decision applies unchanged.
- **Do not attempt `multi_strategy`.** Experimental, no Poisson support guaranteed, and it would not
  model the correlation anyway.
- **If the score grid needs a correlation fix, apply it to the grid, not the learner.** Take the two
  predicted λs, build the outer-product matrix, then either multiply the four cells by a fitted
  Dixon-Coles tau, or inflate the diagonal 538-style. Both are a handful of lines downstream of the
  model and neither disturbs training.

---

## 5. What serious published forecasters actually use

### FiveThirtyEight (legacy SPI, last edited 2020-07-02)

The methodology page is offline — ABC News shut FiveThirtyEight down — but is archived, and the
[SPI data repo](https://github.com/fivethirtyeight/data/tree/master/soccer-spi) is live and confirms
the fields (`proj_score1/2`, `importance1/2`, `xg1/2`, `nsxg1/2`, `adj_score1/2`). From the archived
[methodology](https://web.archive.org/web/20240301000000/https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/):

> "Using our projected match scores and the assumption that goal-scoring in soccer follows a Poisson
> process … we generate two Poisson distributions around those scores… We take the two Poisson
> distributions and turn them into a matrix of all possible match scores, from which we can calculate
> the likelihood of a win, loss or draw."

And, directly on the question in §4:

> "There has been some debate about what kind of distribution best models scoring in soccer. We've found
> that **two independent Poisson distributions work well with the addition of diagonal inflation**. That
> is, we generate the two distributions independently, but increase the value of each cell in the matrix
> where the scores are equal by some constant (somewhere around 9 percent, but this differs by league…)."

So: independent Poissons, correlation handled as a **post-hoc ~9% diagonal inflation on the score
matrix** — not Dixon-Coles tau, not bivariate Poisson. Other points of contact with issue #1's settled
decisions: match importance is an explicit model input; ratings are updated from adjusted goals + shot xG
+ non-shot xG rather than raw scorelines; and season forecasts are 20,000 Monte Carlo sims run "hot",
meaning ratings move *within* a simulation — the same choice this project made for mid-tournament Elo.

Their own accounting of what the upgrades bought, in RPS: expected goals −0.0018, market values −0.0011,
match importance −0.0006, to a final 0.1957. **This is the best available scale for "how big is a real
improvement in this domain."** It is the yardstick against which §2's 0.0001 should be read.

### Opta

Opta publishes only that the model "estimates the probability of each match outcome (win, draw or loss)
by using betting market odds and the Opta Power Rankings", then "simulates the remaining fixtures…
thousands of times" ([theanalyst.com](https://theanalyst.com/articles/opta-football-predictions)). No goals
model, no distributional assumption, no parameters. Academic work that needs to compare against it fits
its own bivariate Poisson to mimic the published forecasts. **Not a reproducible target and not a useful
design reference** — and note that market odds are an input, which is a different game from this project's.

### Academia

- **Ley et al. (2019)** — bivariate Poisson with **one strength parameter per team** wins on RPS at both
  club and international level. Note the parsimony finding: the single-parameter version beat the separate
  attack/defence version in both case studies. "So parsimony in terms of parameters to estimate is
  important."
- **Groll et al. (2018)** — a random forest alone roughly matches a Poisson ranking model (RPS 0.192 vs
  0.190; bookmakers 0.188). But feeding the Poisson ranking model's **ability estimates in as a covariate**
  improves the random forest to RPS 0.187 — better than the bookmakers — and the abilities are "by far
  the most important predictor", ahead of FIFA rank, odds, GDP and squad variables. **The hybrid beats
  either half.** This is a direct endorsement of issue #1's "Elo stays as a feature alongside
  attack/defence strengths."
- **Rezaei & Samadi (2026)**, *Predicting the 2026 FIFA World Cup with Sufficient Dimension Reduction of
  Elo Rating Histories* (arXiv:[2606.24171](https://arxiv.org/abs/2606.24171)) — the most recent and the
  most directly relevant, since it backtests on **WC2018 + WC2022** exactly as issue #1 proposes:

  | Model | Combined RPS | Acc |
  |---|---|---|
  | M1: Elo-logistic | 0.219 | 0.508 |
  | M2: Full logistic | 0.217 | 0.523 |
  | M3: Poisson (current Elo) | 0.212 | 0.516 |
  | M6: XGBoost | 0.215 | 0.531 |
  | M7: Ensemble (M1–M3, M6) | 0.209 | 0.547 |
  | **M8–M11: SDR-Poisson (reduced Elo history)** | **0.127–0.129** | **0.68–0.70** |

  Their own summary: "Logistic regression, Poisson regression, ARIMA and NNAR variants, XGBoost, and
  the ensemble all perform similarly." The 0.08 RPS jump came from **replacing the current Elo rating
  with a dimension-reduced summary of its recent history** — a feature change, inside the same Poisson
  double-regression.

### Where the field has landed

**A time-weighted double-Poisson goals model is the settled backbone**, whether the λs come from
attack/defence MLE, from Elo, or from a tree ensemble. Refinements to the *joint distribution*
(bivariate Poisson, copulas, Sarmanov extensions) are academically interesting and empirically
marginal. Real gains come from **features** (xG, rating histories, market value, match importance),
from **correct weighting**, and from **ensembling** — never from the score distribution.

---

## What would change these conclusions

- **penaltyblog going stale.** The whole §1 recommendation hangs on one maintainer. Mitigation is
  already in the plan: the hand-roll is small and the library doubles as its test oracle. Re-check
  release cadence before the model work starts.
- **A fitted `rho` that is large and well-determined on the real international dataset.** §2 assumes it
  will be small. If it is not, tau is worth more than 0.0001 here.
- **Evidence for long memory in international football specifically.** §3's 3-year finding comes from
  2008–2017 data. A 150-year dataset with a tuned half-life could in principle land higher — but the
  backtest, not the prior, should decide, and the search range should go to 6 years before anyone
  argues for 8.
- **Needing scoreline-conditional bets or exact-score accuracy** (not currently in scope). §4's
  "correlation doesn't matter" holds for 1X2 and margin; it does *not* hold for exact scorelines or
  over/under markets, where the joint distribution is the whole question.

## Sources

**Libraries and docs**
- penaltyblog — [repo](https://github.com/martineastwood/penaltyblog) · [PyPI](https://pypi.org/project/penaltyblog/) · [docs](https://docs.pena.lt/y/models/dixon_coles.html) · source: [`dixon_coles.py`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/dixon_coles.py), [`loss.pyx`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/loss.pyx), [`utils.py`](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/models/utils.py)
- penaltyblog author's model benchmark — https://pena.lt/y/2025/03/10/which-model-should-you-use-to-predict-football-matches/
- `goalmodel` (R) — https://github.com/opisthokonta/goalmodel
- Dixon-Coles time weighting, replicated — https://opisthokonta.net/?p=1013
- XGBoost [parameters](https://xgboost.readthedocs.io/en/stable/parameter.html) · [multi-output tutorial](https://xgboost.readthedocs.io/en/stable/tutorials/multioutput.html)

**Papers**
- Dixon & Coles (1997), *Modelling Association Football Scores and Inefficiencies in the Football Betting Market*, JRSS-C 46(2):265–280 — https://doi.org/10.1111/1467-9876.00065 (paywalled; tau and ξ figures taken from the replications above and from arXiv:2307.02139 §2.1)
- Ley, Van de Wiele & Van Eetvelde (2019), *Ranking soccer teams on the basis of their current strength* — https://arxiv.org/abs/1705.09575
- Groll, Ley, Schauberger & Van Eetvelde (2018), *Prediction of the FIFA World Cup 2018 — A random forest approach* — https://arxiv.org/abs/1806.03208
- Michels, Ötting & Karlis (2023), *Extending the Dixon and Coles model* — https://arxiv.org/abs/2307.02139
- Petretta, Schiavon & Diquigiovanni (2022), *On the dependence in football match outcomes* — https://arxiv.org/abs/2103.07272
- Rezaei & Samadi (2026), *Predicting the 2026 FIFA World Cup with Sufficient Dimension Reduction of Elo Rating Histories* — https://arxiv.org/abs/2606.24171

**Forecasters**
- FiveThirtyEight club soccer methodology (archived) — https://web.archive.org/web/20240301000000/https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/
- FiveThirtyEight SPI data — https://github.com/fivethirtyeight/data/tree/master/soccer-spi
- Opta football predictions — https://theanalyst.com/articles/opta-football-predictions

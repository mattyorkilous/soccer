# Context

International football match prediction, and Monte Carlo simulation of a World Cup.

## Glossary

**Match** — an international game that has been played and has a result.
_Avoid_: game, fixture (for played games).

**Fixture** — a scheduled game with no result yet. Only a fixture can be predicted.
_Avoid_: match (for unplayed games).

**Scoreline** — an exact result, such as 2–1.
_Avoid_: score (ambiguous between one side's goals and the pair).

**Rating** — a team's elo at a point in time.
_Avoid_: elo (as a noun for the value), strength.

**Qualified teams** — the teams in a tournament: those that have actually qualified, plus the highest-rated teams filling each confederation's remaining quota.
_Avoid_: field.

**Goals model** — something that turns a fixture into a probability for every scoreline.
Win, draw and loss probabilities are derived from those scoreline probabilities; they are never predicted directly.

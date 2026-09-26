# Coding standards

## Style

- Functional: immutable data, strictly use comprehensions over loops.
- A loop is permitted *only* for reduce/accumulate where no pure-polars
  solution exists, and its body is a single function call.
- Never bind the same name to two different objects. Prefer a method
  chain or give the object a new name.
- Pure functions; side effects confined to thin I/O boundaries.
- Name the return value, then return it — never return an expression
  directly.

## Naming

- Functions are `[verb]_[returnval]`: `get_matches()`,
  `create_tournament()` / `build_tournament()` when the function takes
  no arguments.
- A bare verb is fine where it reads — `simulate()`. A bare participle
  never is.
- Objects are nouns, never bare adjectives or participles.
- Adjectives attach as suffixes, not prefixes: `matches_cleaned`, not
  `cleaned_matches`.
- Dataframes are named at the level they are at: `matches`,
  `matches_cleaned`.
- Module-internal functions take a leading underscore:
  `_get_match_result()`.
- Modules that *do* a pipeline step get bare verb names (`load.py`,
  `simulate.py`). A module that *is* a thing — frozen dataclasses
  with no methods — gets a noun name.

## Polars

- Polars-native rather than loops as a strong preference.
- For method chains longer than a line, one method per line, indented
  one level relative to the object it acts on. Every chain carries
  `# fmt: skip`.
- `fmt: skip` chains still aim for 72 columns; the lint only catches
  them at 79.

```python
matches_cleaned = (
    matches
        .with_row_index('match_id')
        .with_columns(
            pl.col('date').cast(pl.Date)
        )
        .pipe(get_scores_processed)
)  # fmt: skip
```

## Types

- Annotate signatures only, never bodies.
- Rewrite rather than reach for `# type: ignore`.

## Docstrings and Comments

- Never on private functions or tests.
- Few public functions, each deep.
- Where the *why* needs saying, comment the line, don't pad the
  docstring.
- Extremely limited comments otherwise.

## Tests

- Test at the seams: behaviour, not implementation.
- Never write a test that fundamentally tests a third-party library.
- A test earns its place by protecting behaviour we could legitimately
  break. Coverage is not the goal.
- Test names document themselves.

# Contributing

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sanif/kata.git
cd kata
uv sync --extra dev
```

Optionally install the pre-commit hooks (ruff + pytest on commit):

```bash
uv run pre-commit install
```

## Running tests

```bash
uv run pytest
```

## Linting and type checking

```bash
uv run ruff check .
uv run ruff format .
uv run mypy kata
```

## Branches

Branch off `main`:

```
feature/<name>
fix/<name>
hotfix/<name>
chore/<name>
```

Never commit directly to `main`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

## Pull requests

Keep PRs focused on one change. Make sure `pytest`, `ruff check`, and `mypy` pass before opening one.

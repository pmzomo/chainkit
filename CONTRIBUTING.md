# Contributing

Thanks for helping. chainkit is small on purpose: every change should keep it easy to audit.

1. Open an issue first for anything beyond a small fix, so we can agree on the approach.
2. Fork, create a branch, and add tests: new behaviour needs tests, and coverage must stay at 95% or above.
3. Run the checks before opening a pull request:

   ```bash
   pip install -e ".[dev]"
   ruff check . && mypy && pytest --cov
   ```

4. Keep money as integers, never floats, and keep runtime dependencies to `solders` and `requests`.
5. Note user-visible changes in `CHANGELOG.md`.

By contributing you agree that your contributions are licensed under the Apache License 2.0.

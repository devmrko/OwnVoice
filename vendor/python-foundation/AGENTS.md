# Repository development rules

- Keep one distributable python_foundation package and an application-owned example.
- Write/update docs/design before changing public contracts; document validation and limitations.
- Use Router -> Service -> Repository. Never commit from a repository or share Sessions across tasks.
- Use typed DTOs and safe ErrorSpec/BusinessError. Never expose credentials, SQL or raw provider messages.
- Authentication and CSRF changes require session/token/mixed boundary tests. No implicit token issuance.
- Run uv run ruff check ., uv run ruff format --check ., uv run mypy, uv run pytest.
- Packaging changes also require uv build and uv run python scripts/verify_wheel.py.
- Keep package/application dependencies pinned through uv.lock. Do not commit .env, DBs, keys, virtualenvs or caches.
- Python and Java share HTTP contracts, not source or release cycles. Oracle/live-provider claims require actual tests.
- Keep unfinished capabilities explicit in docs; do not call in-process background work durable.

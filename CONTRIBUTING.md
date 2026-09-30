# Contributing

Thanks for taking the time to contribute.

## Development workflow

1. Create a focused branch from `main`.
2. Keep changes small and add or update tests when behavior changes.
3. Run `pytest -q`; for frontend changes, also run `npm run test` and `npm run build` from `frontend/`.
4. Open a pull request explaining the user impact and verification performed.

## Security

Never commit API keys, `.env` files, real customer documents, database dumps, or generated files from `storage/documents/`. Please report vulnerabilities privately instead of opening a public issue.

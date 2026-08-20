# Development Safety

This repository is the formal long-term development workspace. The course archive is kept in a separate location and is not part of this Git working tree.

- Do not copy course reports, real identity materials, videos, ZIP archives, or other private coursework files into this repository.
- Do not commit `.env` files, API keys, access tokens, database passwords, or other credentials.
- Real or raw Arena data is excluded by default. Before adding any data, check its license, privacy implications, and redistribution conditions.
- Generated artifacts should normally be treated as reproducible outputs rather than source files.
- Small synthetic or demo fixtures may be versioned only after their contents and purpose have been explicitly reviewed.
- Before running `git add .`, inspect `git status` and review the proposed paths.
- New data sources require a license, privacy, and redistribution review before entering the repository.

The repository currently contains historical tracked outputs, data files, and a model artifact inherited from the public baseline. Their retention or removal is deferred to Phase 1B; this phase does not untrack or delete them.

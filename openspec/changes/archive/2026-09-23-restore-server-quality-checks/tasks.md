## 1. Runtime maintenance

- [x] 1.1 Make logger setup idempotent and preserve stderr/custom-handler behavior; verify repeated Adapter construction, single emitted output, level updates, and configured handlers in tests.
- [x] 1.2 Narrow the validated SQLite URI, exclude only parked adapters from mypy discovery, and remove confirmed unused imports; verify full mypy and Ruff commands pass.

## 2. Enforced checks and documentation

- [x] 2.1 Add clean static checks to the existing CI matrix and a local Make shortcut; verify job names, triggers, matrix, and coverage floor remain intact and Make executes both checks.
- [x] 2.2 Update development instructions, current diagnostic behavior, roadmap progress, and backlog 027/051/054; verify local links and ownership alignment.
- [x] 2.3 Run the full coverage-gated server suite, strict OpenSpec validation, and whitespace checks; record evidence, synchronize verified specs, and archive this change.

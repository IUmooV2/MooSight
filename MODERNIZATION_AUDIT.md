# MooSight Repository Modernization Audit

This document is a repository-wide modernization plan for the SpiderFoot-based MooSight codebase. It prioritizes correctness, security, evidence quality, maintainability, compatibility, and performance. Changes should be delivered in small reviewable phases with regression tests rather than as a single rewrite.

## Executive summary

The project is functional but carries a substantial amount of 2020-2023-era technical debt across runtime support, dependency constraints, CI, container images, frontend libraries, HTTP/TLS behavior, global mutable state, error handling, packaging, and OSINT result semantics.

The highest-value work is not cosmetic. The first modernization phase should make the project safer to run and easier to test before broad dependency or UI upgrades.

## Priority 0: correctness and security foundations

### 1. Restore TLS verification by default

`sflib.py` globally replaces Python's HTTPS context with an unverified context and suppresses `InsecureRequestWarning`. Individual modules also historically use unverified requests because OSINT targets may have invalid certificates.

Modernization:
- Never globally disable TLS verification.
- Default normal third-party API and dataset requests to certificate verification enabled.
- Allow a narrowly scoped per-request `verify=False` only for modules whose purpose explicitly requires observing invalid target certificates.
- Log that a request was intentionally unverified without suppressing all warnings process-wide.
- Add tests proving secure requests remain verified by default.

Why: a process-wide insecure TLS default weakens every API/dataset/configuration download, not only target reconnaissance.

### 2. Separate network result states

Network operations should represent at least:
- positive match
- negative match
- blocked/rate-limited
- timeout/network failure
- parser/service changed
- authentication/API-key missing
- indeterminate

Do not silently convert indeterminate service behavior into "not found." This is especially important for username and account discovery.

### 3. Evidence-aware OSINT events

The current SpiderFoot event vocabulary can overstate identity certainty, particularly `ACCOUNT_EXTERNAL_OWNED`.

Modernization:
- Preserve compatibility with legacy events internally where necessary.
- Add evidence metadata and an explicit confidence/status layer in MooSight.
- Distinguish exact profile detection from search-page leads, username reuse, heuristic correlation, and permutation matches.
- Never infer that two accounts belong to the same human solely from a matching username.

### 4. Input and URL validation

Create shared validators for:
- usernames
- email addresses
- hostnames/domains
- URLs
- IPs/CIDRs
- proxy settings
- local file references
- remote configuration URLs

Avoid module-specific ad hoc validation where common behavior is possible.

### 5. Secrets and sensitive logging

Audit all logging paths so API keys, proxy credentials, tokens, authorization headers, cookies, and sensitive request bodies are redacted. Proxy strings currently risk being logged with embedded credentials.

## Priority 1: supported runtime and dependency modernization

### 6. Establish a modern Python baseline

Current CI stops at Python 3.10 while the codebase still advertises older Python support.

Recommended migration strategy:
1. First prove compatibility on Python 3.10 and 3.11.
2. Fix deprecations and dependency blockers.
3. Add 3.12, then 3.13 and 3.14 when the dependency set passes.
4. Once stable, choose a maintained minimum such as Python 3.11 or 3.12 rather than carrying unsupported runtime compatibility indefinitely.

Do not simply change the version badge without running the suite.

### 7. Replace legacy dependency caps deliberately

`requirements.txt` pins several libraries to old major/minor lines. High-priority examples include:
- PyPDF2 `<2`
- pyOpenSSL `<22`
- cryptography `<4`
- networkx `<2.7`
- python-docx `<0.9`
- python-pptx `<0.7`
- python-whois `<0.8`
- netaddr `<1`
- ipwhois `<1.2`

Modernization approach:
- Inventory actual APIs used by MooSight before changing each bound.
- Upgrade one dependency family at a time with tests.
- Replace abandoned dependencies where practical rather than forcing old packages onto new Python.
- Use a lock/constraints strategy for reproducible installs.
- Add Dependabot or Renovate-style automated update PRs only after tests are dependable.

### 8. Adopt modern project metadata

The repository lacks a modern `pyproject.toml`-centered project definition.

Add:
- `pyproject.toml`
- explicit supported Python versions
- project metadata and optional dependency groups (`test`, `dev`, `full`)
- formatter/linter/test configuration where supported
- build/install metadata if MooSight becomes installable as a package

Keep transition compatibility with existing launch scripts until packaging is proven.

## Priority 2: CI/CD and quality gates

### 9. Replace obsolete GitHub Actions

Current workflows use old major versions of checkout/setup-python/CodeQL actions and only trigger on `master`.

Modernization:
- Update GitHub Actions to supported current majors.
- Run CI on feature branches through pull requests.
- Include Windows, Linux, and macOS where practical.
- Add a modern Python version matrix.
- Cache pip downloads safely.
- Separate fast unit tests from integration/network tests.
- Make required checks visible before merge.

### 10. Modern linting and static analysis

The current test stack contains many older Flake8 plugins plus darglint/dlint.

Evaluate consolidation to a smaller modern toolchain, for example:
- Ruff for linting/import sorting and many Flake8-equivalent rules
- Black or Ruff formatting
- mypy or pyright incrementally for type checking
- Bandit and CodeQL for security analysis
- pytest for unit/integration testing

Do not introduce strict type checking across all legacy modules at once. Start with new and heavily modified code.

### 11. Coverage that measures meaningful behavior

Set coverage expectations for core infrastructure and changed modules, not merely total line percentage. Important areas:
- target parsing
- event propagation
- DB migrations/queries
- HTTP fetch behavior
- web API endpoints
- scan lifecycle
- account/result validation
- correlation engine

## Priority 3: core architecture

### 12. Reduce global process mutation

Current code modifies process-wide state in several places, including:
- global TLS context
- DNS resolver override
- multiprocessing start method
- mutable class-level containers

Refactor toward instance-scoped dependencies. This improves parallel scans, testing, and predictable cleanup.

### 13. Introduce typed configuration objects

Large dictionaries with magic keys such as `_maxthreads`, `_fetchtimeout`, `__database`, and SOCKS fields are difficult to validate and refactor.

Create typed configuration models/dataclasses with:
- validation
- defaults
- serialization compatibility
- secrets marked/redacted
- clear ownership between global, scan, and module configuration

### 14. Centralize the HTTP client

Build one well-tested network layer responsible for:
- sessions/connection pooling
- TLS policy
- proxies
- user agent
- finite connect/read timeouts
- redirects
- response size limits
- rate limiting/backoff
- retry policy
- compression
- normalized result/error states
- metrics/debug logging with secret redaction

Modules should describe what they want fetched rather than each inventing transport behavior.

### 15. Scan lifecycle and concurrency

Audit thread/process ownership and cancellation.

Modernization goals:
- explicit cancellation tokens/events
- bounded queues
- deterministic worker shutdown
- no leaked threads/processes after abort
- graceful server shutdown
- concurrency limits per target/service where appropriate
- no uncontrolled nested thread pools

Do not chase maximum request throughput at the expense of reliability or external-service friendliness.

### 16. Replace mutable class-level containers

Patterns such as class-level `list()`/`dict()` state should become instance state unless intentionally shared. This avoids state leakage between scans/tests.

### 17. Narrow exception handling

Replace `except BaseException` and overly broad `except Exception` where specific failure types are known. Never swallow `KeyboardInterrupt`/`SystemExit` unintentionally. Preserve useful error context while keeping individual module failures isolated.

## Priority 4: data/storage and correlation

### 18. Database layer modernization

Review SQLite access for:
- context-managed connections/transactions
- WAL mode where appropriate
- busy timeout
- parameterized SQL everywhere
- indexes based on actual result-query patterns
- explicit schema versioning/migrations
- pagination for large result sets
- bounded memory when exporting large scans

Do not replace SQLite merely for novelty. It remains a good default for a local single-user tool if the access layer is disciplined.

### 19. Correlation confidence/provenance

Correlation results should retain:
- source modules
- source event IDs
- timestamps
- exact rules triggered
- confidence/evidence metadata

This makes conclusions auditable instead of opaque.

### 20. Cache modernization

Use namespaced cache keys, schema/version tags, bounded lifetime/size, atomic writes, and clear handling of corrupted cache entries. Avoid cache semantics that silently make stale service definitions look current.

## Priority 5: web application and API

### 21. Strengthen authentication and deployment boundaries

Loopback-only remains the safe default. Network-facing operation should require explicit configuration and authentication.

Modernization:
- clear local-only mode
- strong session/authentication mode for remote binding
- CSRF protection for state-changing endpoints
- secure cookie attributes
- request size limits
- explicit allowed CORS origins
- no wildcard CORS by accident
- rate limits for expensive operations

### 22. Tighten Content Security Policy

Current CSP allows `unsafe-inline` for scripts/styles. Remove this progressively using nonces/hashes and external static assets. Keep a migration period if templates depend heavily on inline code.

### 23. Replace overloaded HTML sanitization

`cleanUserInput()` explicitly contains a TODO noting overloaded usage. Separate:
- input validation
- canonicalization
- HTML escaping
- SQL/query parameters
- display formatting

Escaping must occur at the output/context boundary, not as a substitute for validation.

### 24. Define a stable internal API

Separate web presentation from scan services. Create a service/API layer for scans, results, settings, exports, and modules. This will make a future UI replacement much safer.

## Priority 6: frontend modernization

### 25. Stop committing `node_modules`

The repository currently vendors `spiderfoot/static/node_modules`.

Modernization:
- remove vendored dependencies from Git history going forward
- commit a lockfile
- build reproducibly in CI/release packaging
- ship only built static assets when needed

### 26. Upgrade legacy UI libraries

Current frontend dependencies include Bootstrap 3, D3 3, and Sigma 1.

Do not perform blind major upgrades because APIs changed substantially. Recommended sequence:
1. inventory templates and JavaScript usage
2. add frontend smoke tests
3. isolate graph/table components behind wrappers
4. migrate Bootstrap layout/components
5. migrate visualization code separately

A new framework is optional. MooSight can remain server-rendered and still become modern, accessible, responsive, and maintainable.

### 27. Accessibility and responsive design

Add keyboard navigation, visible focus states, semantic form labels, sufficient contrast, accessible tables/modals, and responsive layouts. Treat accessibility as a feature rather than cosmetic cleanup.

## Priority 7: container and deployment

### 28. Replace obsolete Alpine base images

Current Docker images use Alpine 3.12/3.13-era bases.

Modernization:
- use a currently supported base image
- pin by digest for releases when practical
- minimize build dependencies in final stage
- add healthcheck
- maintain non-root runtime
- define writable data/cache/log volumes clearly
- add graceful signal handling
- scan built images for known vulnerabilities

### 29. Reproducible container builds

Avoid unbounded package installs and obsolete build chains. Lock Python dependencies and document full vs minimal images.

## Priority 8: module ecosystem

### 30. Machine-readable module health

With hundreds of external integrations, broken services are inevitable. Add module/service metadata such as:
- maintained/experimental/deprecated
- last validation date
- requires API key
- passive/direct-contact behavior
- expected rate limit
- supported target/event types
- known limitations

### 31. Automated integration health checks

Run scheduled, rate-limited canary tests against safe test data and vendor-provided test endpoints where available. Do not perform uncontrolled scans of third parties from CI.

### 32. Standard module transport/parser patterns

Provide helpers/base classes for common patterns:
- JSON API
- HTML profile existence
- DNS API
- paginated API
- API-key validation
- retry-after handling

This removes hundreds of slightly different implementations of the same behavior.

### 33. Deprecate dead modules cleanly

A module that no longer has a viable service should be marked deprecated/disabled rather than generating errors indefinitely. Preserve historical code in Git history instead of carrying it as default scan noise.

## Priority 9: observability and user experience

### 34. Structured logging

Keep human-readable logs but support structured fields for:
- scan ID
- module
- target type (avoid logging sensitive target values unless needed)
- service
- duration
- result state
- retry/rate-limit status

### 35. Scan summary quality

At completion, report:
- confirmed/strong findings
- possible leads
- indeterminate checks
- services skipped for missing keys
- services blocked/rate-limited
- services that failed because their integration appears stale

This is more useful than presenting only successful events and a noisy raw log.

### 36. Better first-run experience

Continue the Windows launcher work and later add:
- preflight dependency check
- clear update path
- diagnostics bundle with secrets redacted
- one-click local launch
- version display that distinguishes upstream SpiderFoot base from MooSight version

## Priority 10: project/release hygiene

### 37. MooSight versioning

`VERSION` still reports SpiderFoot 4.0.0 even though the fork has its own changes and tracks later upstream master commits.

Introduce semantic MooSight versions while retaining upstream provenance, for example:
- MooSight version
- upstream SpiderFoot commit/tag
- build date/commit SHA

### 38. Changelog and migration notes

Add a changelog for user-visible changes and explicit migration notes for breaking configuration/database changes.

### 39. Dependency/security automation

After CI is trustworthy, add:
- dependency update automation
- dependency vulnerability scanning
- SBOM generation for releases
- secret scanning
- CodeQL on PRs and default branch

### 40. Release artifacts

Eventually publish reproducible Windows and container artifacts from CI so normal users do not need a Python development environment.

## Recommended implementation order

### Phase A: safety and testability
- TLS policy
- logging secret redaction
- modern CI
- Windows CI
- account-finder tests
- shared network result model
- narrow global state

### Phase B: runtime/dependencies
- Python 3.11/3.12 compatibility
- `pyproject.toml`
- dependency-by-dependency upgrades
- modern lint/type tooling

### Phase C: core architecture
- HTTP client abstraction
- typed configuration
- concurrency/cancellation cleanup
- DB migrations and indexes
- provenance/confidence model

### Phase D: frontend/deployment
- remove committed node_modules
- frontend dependency migration
- CSP/CSRF/session hardening
- modern containers

### Phase E: module ecosystem
- module health metadata
- scheduled integration health checks
- standardized module helpers
- deprecate dead integrations

## Rule for all modernization work

Do not modernize merely to make version numbers newer. Every change must improve one or more of: correctness, security, maintainability, performance, compatibility, evidence quality, accessibility, or user experience, and should have a test or other objective validation appropriate to its risk.

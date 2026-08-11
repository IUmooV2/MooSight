# MooSight Engineering Standards

MooSight changes should favor correctness, evidence quality, maintainability, safety, and predictable behavior over cleverness or raw feature count.

## Required principles

1. **Correctness before optimization.** A fast incorrect result is worse than a slower defensible result.
2. **Evidence must match the label.** OSINT findings must not claim ownership, identity, or certainty beyond what the underlying evidence establishes. Heuristic matches should be represented as such.
3. **Validate every boundary.** Treat usernames, URLs, files, configuration, API responses, downloaded datasets, and network responses as untrusted input.
4. **Fail safely and locally.** One malformed service, timeout, unavailable API, or parsing error should not terminate an otherwise useful scan.
5. **Secure defaults.** Bind local services to loopback by default, do not log secrets, do not hard-code credentials, and keep potentially intrusive behavior opt-in.
6. **Readable code.** Prefer small focused functions, descriptive names, straightforward control flow, and comments explaining non-obvious decisions rather than restating code.
7. **Minimize side effects.** Network requests, cache writes, event emission, and mutations should be explicit and easy to reason about.
8. **Respect external services.** Use finite timeouts, bounded concurrency, caching, and conservative retries. Avoid unnecessary requests.
9. **Deterministic output where practical.** Sort unordered result collections before presenting or testing them.
10. **Backward compatibility.** Preserve SpiderFoot interfaces and event contracts unless a deliberate migration is documented and tested.
11. **Dependencies require justification.** Prefer the standard library for small tasks. New packages should be maintained, necessary, and version-managed.
12. **Tests accompany behavior changes.** Add unit tests for parsing, validation, edge cases, regressions, and important failure paths. Network-dependent tests should be isolated from deterministic unit tests.
13. **No silent exceptions.** Recoverable failures may be debug-logged and skipped; unexpected failures must retain enough context to diagnose without exposing sensitive data.
14. **Configuration over hard-coding.** Values likely to vary by environment or usage belong in configuration when doing so improves maintainability.
15. **Small reviewable commits.** Experimental work belongs on branches and should reach the primary branch only after review/testing.
16. **Privacy-conscious output.** Collect and retain only information necessary for the intended OSINT result. Avoid unnecessary reproduction of sensitive personal information.
17. **Document limitations.** Detection heuristics, known false-positive conditions, unsupported platforms, and important operational assumptions should be stated clearly.

## OSINT result-quality rules

- A reachable URL alone does not prove that an account exists.
- A matching username alone does not prove that accounts belong to the same person.
- Search-result pages are leads, not confirmed account profiles.
- Prefer service-specific positive/negative fingerprints over HTTP status alone.
- Random nonexistent-username checks should be used to identify services that return misleading universal positives.
- Results derived from permutations must remain distinguishable from exact username matches.
- Broken, rate-limited, blocked, or indeterminate services should not be silently converted into negative findings.

## Definition of done

A change is ready for the primary branch when its behavior is understandable, relevant tests exist and pass, important failure modes are handled, security/privacy implications have been considered, user-facing behavior is documented when necessary, and the change does not knowingly reduce evidence quality merely to produce more results.

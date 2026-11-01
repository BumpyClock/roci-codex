# Rust CI changed-path checks

`python3 .github/scripts/test_rust_ci_changed_paths.py` executes the actual
workflow Bash bodies in disposable repositories. It requires Git, Python 3 and
Linux Bash with `mapfile -d` support. No Rust builds, credentials or runners are
needed for this regression suite.

The detector checks the diff producer's status before parsing NUL-separated
paths. A missing base/head fails the detection job without emitting skip outputs.
The required aggregate rejects failed detection and missing/invalid outputs.
Only `docs/*.md` paths can skip the fast Rust bundle; all other changes broaden
to the full bundle, including unknown paths, root configuration and hidden Rust
sources. Renames inspect both old and new paths via `--no-renames`.

The regression step belongs to the existing reusable detection job. This change
does not activate imported CI, provision runner pools or change the postmerge
matrix. Imported runner availability and CI ownership remain owner gates.

# Boat runner selection

Compatible jobs that previously selected `ubuntu-latest` now select `boat`,
including small metadata/aggregate/release jobs. This source change does not
dispatch imported CI, publish artifacts, change billing or repair provider API
access. Existing trust guards, environments, permissions and credential fallbacks
remain unchanged. Owner-only public execution was approved/configured separately;
outside contributors and bots remain blocked by that account policy.

Tokenless npm publishing remains on `ubuntu-latest`. npm trusted publishing
currently requires GitHub-hosted runners. Existing OIDC/provenance and publication
guards remain intact; no long-lived token is added to force migration.

Pinned Ubuntu, native macOS, Windows and ARM64 job contracts remain unchanged.
Boat is x86_64 Linux in the inspected sandbox. Its Ubuntu 24.04 receipt is not
native Windows/ARM64/macOS qualification, nor proof of full Bazel/V8/release
capability. Do not repurpose those native lanes as Linux jobs.

Inherited Linux x64 pools have an additive Boat option.

- Reusable `sdk.yml` accepts boolean `use_boat`, default false. `blocking-ci.yml`
  passes true only when repository variable `CI_LINUX_RUNNER` equals `boat`.
- `rust-ci-full.yml` accepts `use_boat` through reusable/manual inputs. Its Linux
  x64 lint/build rows and nextest archive/test caller preserve matrix identity,
  artifact names, profiles, remote-environment flags and self-hosted fallback.
  `postmerge-ci.yml` forwards the same optional repository-variable choice.
- `rust-ci-full-nextest-platform.yml` applies the option only to
  `x86_64-unknown-linux-*` targets. Native Windows archive overrides, Windows
  shards and Linux ARM64 retain their current runners.
- Linux x64 Rust release builds accept the same `CI_LINUX_RUNNER=boat` option.
  With no such value, existing `*-linux-x64-xl` labels remain in effect. ARM64
  release labels and all signing/publication guards are unchanged.

No variable, setting, runner pool or secret is changed by these edits. Maintainers
must qualify Docker/Bazel/V8/sandbox/native voice dependencies and runner sizing
before using the optional heavy Linux lanes. Required-check names and existing
postmerge platform coverage remain intact. No speedup is claimed.

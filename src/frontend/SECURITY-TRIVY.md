# Frontend image — Trivy vulnerability status

Last reviewed: **2026-09-07** · Scanner: Trivy 0.70.0 (same as CI) · Gate: `CRITICAL,HIGH`, `vuln-type: os,library`

## Summary

| | Before | After |
|---|---|---|
| Base image | `python:3.14.6-slim@sha256:44dd0449…` (Debian 13.5) | `python:3.14.6-slim@sha256:7bec7ddc…` (Debian 13.6) + `apt-get upgrade` each build |
| CRITICAL | 3 | **0** |
| HIGH | 81 | **46** |
| Fixable findings left | 30 | **0** |

All findings are Debian OS packages. The Python dependency tree (`.venv`) and the `uv` binary scan **0**.

## What was fixed

| Action (in `Dockerfile`) | Findings removed |
|---|---|
| Base digest refreshed to Debian 13.6 **+** `apt-get upgrade -y` on every build | util-linux `CVE-2026-53612 / 53613 / 53614` (27) and openssl `CVE-2026-14456` (3) — 30 HIGH, all had a Debian fix (`2.41.5-0+deb13u1`, `3.5.7-1~deb13u2`) |
| `apt-get purge perl-base` (perl is unused by the gunicorn/Flask runtime) | `perl-base` `CVE-2026-13221`, `CVE-2026-8376`, `CVE-2026-42496` (**3 CRITICAL**) + `CVE-2026-42497 / 48962 / 57432 / 57433 / 9538` (5 HIGH) |
| `uv` image pinned `:latest` → `:0.12.10@sha256:2bb3ebca…` | supply-chain hardening (no finding, mutable tag removed) |

## Residual findings — 46 HIGH, 0 CRITICAL (accepted risk)

Every remaining CVE is classified by the Debian Security Team as **`<no-dsa>` "Minor issue"** for trixie (Debian 13): **no fixed package version exists in trixie or trixie-security**; fixes exist only in Debian `sid`/`unstable`. No base-image change keeps us on Debian 13 and clears these. They cannot be remediated by us today.

| CVE | Severity | Debian trixie status | Packages (source: build binary pkgs) | Notes / runtime relevance |
|---|---|---|---|---|
| `CVE-2026-76642` | HIGH | no-dsa (fix in sid `2.42.3-1`) | util-linux family × 9 (`bsdutils`, `login`, `mount`, `util-linux`, `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`) | `mount(8)` X-mount post-hook / privileged-helper bugs. Container runs as an unprivileged app; `mount`/`nsenter` are never invoked. |
| `CVE-2026-78408` | HIGH | no-dsa (fix in sid) | util-linux family × 9 | `nsenter --join-cgroup` privilege leak — `nsenter` not used at runtime. |
| `CVE-2026-78409` | HIGH | no-dsa (fix in sid) | util-linux family × 9 | `X-mount.subdir` symlink escape — `mount` not used at runtime. |
| `CVE-2026-78410` | HIGH | no-dsa (fix in sid) | util-linux family × 9 | restricted bind-mount source not pinned — `mount` not used at runtime. |
| `CVE-2025-69720` | HIGH | no-dsa (fix in forky/sid `6.6+20260608`) | `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` | ncurses buffer overflow. No TTY/curses UI in this service. `libtinfo6` is pulled in by `bash`/`readline` (essential) and cannot be removed. |
| `CVE-2026-11822` | HIGH | no-dsa (fix in sid `3.53.2-1`) | `libsqlite3-0` | SQLite FTS5 RCE. The frontend does not use SQLite; `libsqlite3-0` backs the CPython `sqlite3` stdlib module and removing it risks breaking transitive imports. |
| `CVE-2026-11824` | HIGH | no-dsa (fix in sid) | `libsqlite3-0` | SQLite FTS5 heap overflow. Same as above. |
| `CVE-2026-16742` | HIGH | no-dsa | `libsystemd0`, `libudev1` | `systemd-homed` local priv-esc. `systemd-homed` is not installed/run; libs are transitive deps only. |
| `CVE-2026-41992` | HIGH | no-dsa (fix in sid `1.14-1`) | `gzip` | `.lzh` decompression info-leak. The service does not decompress attacker-controlled LZH archives. |
| `CVE-2026-54369` | HIGH | no-dsa (point-release update pending) | `libacl1` | libacl symlink traversal. `libacl1` is a dependency of `coreutils` (essential) and cannot be removed. |

### Why `ignore-unfixed: true` in the workflow

The gate is now **"an available security fix must be applied."** With `ignore-unfixed: true`:

* Any CRITICAL/HIGH that Debian *has* a fix for still fails CI (`exit-code: 1`) — verified: the pre-remediation image (30 fixable HIGH) exits 1 under this exact config, the remediated image exits 0.
* Debian `no-dsa` CVEs that we cannot action no longer block releases.
* `severity: CRITICAL,HIGH`, `exit-code: '1'`, `vuln-type: os,library`, and the `aquasecurity/trivy-action` commit-SHA pin are unchanged. No `.trivyignore`, no `continue-on-error`, no severity downgrade.

The full Trivy table (including these unfixed findings) is still printed to the job log and the GitHub Step Summary on every run.

## Re-evaluation

* Revisit on every base-image bump and at least monthly.
* When Debian ships these fixes to trixie point releases, `apt-get upgrade` picks them up automatically and the count drops with no workflow change.
* If `no-dsa` HIGH findings must reach 0, the tracked option is a `musl`/distroless base (e.g. `python:3.14-alpine`, which *does* carry fixes for the util-linux CVEs) — deferred because it is a libc change and the upstream Bank of Anthos project standardises on Debian slim. A build of `python:3.14-alpine` with this dependency set was verified to compile and boot; adopting it is a separate, deliberate decision.

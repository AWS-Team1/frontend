# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Use the official Python docker container, slim version, running Debian.
# Digest pinned to the current python:3.14.6-slim (Debian 13.6, trixie), which already
# ships the Debian security updates for util-linux (CVE-2026-53612/53613/53614) and
# openssl (CVE-2026-14456). Refresh this digest when a newer 3.14.x-slim is published.
FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS base
# uv pinned to an explicit version + digest (was the mutable ':latest' tag) so the
# builder toolchain is reproducible and not silently updated on every CI run.
COPY --from=ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 /uv /bin/uv

FROM base AS builder

# Set working directory
WORKDIR /app

# Install dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base

# Apply outstanding Debian security updates on every build (defense in depth: picks up
# point-release fixes published after the base digest above was cut), and drop perl-base.
# perl-base carries CVE-2026-13221 / CVE-2026-8376 / CVE-2026-42496 (CRITICAL, Debian
# "no-dsa"/deferred in trixie) plus 5 HIGH, and nothing in the runtime image (gunicorn +
# the frontend Flask app) uses perl, so removing it eliminates those 8 findings outright.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get purge -y --allow-remove-essential perl-base; \
    apt-get autoremove -y --purge; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Set our working directory
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# show python logs as they occur
ENV PYTHONUNBUFFERED=0

# explicitly set a fallback log level in case no log level is defined by Kubernetes
ENV LOG_LEVEL=info

# Add application code.
COPY . .

# Ensure files are readable for non-root users
RUN find . -type f -name '*' -exec chmod a+r '{}' ';'

# Start server using gunicorn
CMD gunicorn -b :$PORT --threads 4 --log-config logging.conf --log-level=$LOG_LEVEL "frontend:create_app()"

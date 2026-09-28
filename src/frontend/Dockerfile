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
# Pin Python 3.14.7 to Debian 12 (bookworm) for a reproducible runtime base.
# Refresh the digest only after the replacement image passes the same Trivy gate.
FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS base
# uv pinned to an explicit version + digest (was the mutable ':latest' tag) so the
# builder toolchain is reproducible and not silently updated on every CI run.
COPY --from=ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 /uv /bin/uv
# uv로 가상환경을 구성하므로 취약한 패키지를 포함한 시스템 pip는 제거
RUN python -m pip uninstall -y pip

FROM base AS builder

# Set working directory
WORKDIR /app

# Install dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base

# Apply outstanding Debian security updates on every build. SECURITY_REFRESH is
# supplied by CI so BuildKit cannot reuse a stale apt upgrade layer.
ARG SECURITY_REFRESH=manual

RUN set -eux; \
    echo "security refresh: ${SECURITY_REFRESH}"; \
    apt-get update; \
    apt-get upgrade -y; \
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

# Fail the image build if the runtime virtual environment or Gunicorn launcher
# was overwritten by files from the Docker build context.
RUN /app/.venv/bin/gunicorn --version

# Ensure files are readable for non-root users
RUN find . -type f -name '*' -exec chmod a+r '{}' ';'

# Start server using gunicorn
CMD /app/.venv/bin/gunicorn -b :$PORT --threads 4 --log-config logging.conf --log-level=$LOG_LEVEL "frontend:create_app()"

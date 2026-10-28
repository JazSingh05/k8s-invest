
# Base image pinned by DIGEST, not just tag: the tag can be repointed, the digest can't.
ARG PYTHON_IMAGE=python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f

# ---- deps: install runtime packages into an isolated venv ----
FROM ${PYTHON_IMAGE} AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install -r requirements.txt

# ---- test: `docker build --target test .` runs the unit tests ----
FROM deps AS test
WORKDIR /src
COPY requirements.txt requirements-dev.txt ./
RUN /venv/bin/pip install -r requirements-dev.txt
COPY . .
RUN /venv/bin/python -m pytest -q

# ---- runtime: only the venv + app code, running as non-root ----
FROM ${PYTHON_IMAGE} AS runtime
# Links the GHCR package to the repo (shows on the package page; lets CI push later).
LABEL org.opencontainers.image.source=https://github.com/JazSingh05/k8s-invest
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/venv/bin:$PATH"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=deps /venv /venv
COPY app ./app
COPY data ./data
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

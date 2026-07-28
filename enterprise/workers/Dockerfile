# Workers image: LangGraph finance approver + Service Bus consumers (SCOPING §11, §14).
#
# Build from the REPO ROOT so the sibling `core-engine` package is in context:
#   docker build -f workers/Dockerfile -t expense-workers .
#
# Pick the consumer at runtime with WORKER_CONSUMER=finance|ingestion (see workers/__main__).

# --- builder: install the workspace deps into a venv -------------------------------------- #
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /build

# expense-core is a path dependency of workers; install it first (with its azure extra).
COPY core-engine ./core-engine
RUN pip install "./core-engine[azure]"

# Then the workers package with the [azure] extra (Service Bus, Search, Blob, Defender, httpx).
COPY workers ./workers
RUN pip install "./workers[azure]"

# --- runtime: copy the venv, run as non-root ---------------------------------------------- #
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    WORKER_CONSUMER=finance

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 10001 worker
USER worker
WORKDIR /home/worker

# __main__ reads WORKER_CONSUMER (finance | ingestion) to choose the consumer to launch.
CMD ["python", "-m", "workers"]

FROM python:3.13-trixie

ENV PYTHONUNBUFFERED=1
# Install the workspace into the system environment (instead of a .venv inside
# the bind-mounted /code) so `uv run` is fast and doesn't pollute the host tree.
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# uv ships as a standalone binary in this image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY entrypoint.sh /

WORKDIR /code

RUN apt update && \
    apt install -y postgresql-client-17

ENTRYPOINT ["/entrypoint.sh"]

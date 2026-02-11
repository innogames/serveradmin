FROM python:3.13-trixie

ENV PYTHONUNBUFFERED=1

COPY entrypoint.sh /

WORKDIR /code

RUN apt update && \
    apt install -y postgresql-client-17 && \
    python -m pip install pipenv

ENTRYPOINT ["/entrypoint.sh"]

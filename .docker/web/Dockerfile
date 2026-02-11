FROM python:3.13-trixie

ENV PYTHONUNBUFFERED=1

COPY entrypoint.sh /

WORKDIR /code

RUN echo "deb http://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt update && \
    apt install -y postgresql-client-17 && \
    pip3 install --upgrade pip pipenv

ENTRYPOINT ["/entrypoint.sh"]
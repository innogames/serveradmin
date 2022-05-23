# Pipenv seems to not work with bullseye (yet)
FROM python:3.7-buster

ENV PYTHONUNBUFFERED=1

COPY entrypoint.sh /

WORKDIR /code

RUN echo "deb http://apt.postgresql.org/pub/repos/apt buster-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt update && \
    apt install -y pipenv postgresql-client-14

ENTRYPOINT ["/entrypoint.sh"]
FROM python:3.9-slim

RUN apt-get -y update
RUN apt-get -y upgrade

RUN apt-get -y install \
    make gcc g++ python3 python3-dev libc-dev

RUN apt-get -y install git

WORKDIR /app
COPY app_scraper app_scraper
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
COPY app.conf app.conf

RUN pip install poetry 
RUN poetry install --no-dev

# CMD ["sh", "-c", "tail -f /dev/null"]

ENTRYPOINT ["poetry", "run"]
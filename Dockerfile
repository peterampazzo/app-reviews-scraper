# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9-slim
RUN apt-get update
RUN apt-get install -y git procps

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

WORKDIR /app
ENV DATA_ROOT=/data
COPY app.conf /app
COPY scraper_backend /app/scraper_backend
COPY scraper.py /app
COPY migrate_data.py /app
ENTRYPOINT ["python", "scraper.py"]

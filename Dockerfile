FROM --platform=linux/amd64 python:3.10.4-slim-buster

WORKDIR /app
COPY . .
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

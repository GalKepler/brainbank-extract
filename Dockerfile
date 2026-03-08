FROM python:3.11-slim

RUN pip install brainbank-extract

ENTRYPOINT ["bb-extract"]

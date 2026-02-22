FROM python:slim AS base

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV PYTHONUNBUFFERED 1

FROM base as builder

WORKDIR /builder

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry &&\
    python -m venv /venv &&\
    poetry export -f requirements.txt |\
    /venv/bin/pip install --no-cache-dir -r /dev/stdin

COPY . .
RUN poetry build && /venv/bin/pip install --no-cache-dir dist/*.whl

FROM base as final

ENV PATH "/venv/bin:${PATH}"
ENV VIRTUAL_ENV "/venv"

COPY --from=builder /venv /venv

WORKDIR /pypoe

COPY export.bash ./
RUN mkdir ./out ./temp &&\
    pypoe_exporter config set out_dir ./out &&\
    pypoe_exporter config set temp_dir ./temp &&\
    pypoe_exporter setup perform

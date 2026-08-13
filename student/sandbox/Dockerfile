FROM python:3.10-slim

RUN useradd --create-home --uid 1000 sandbox

WORKDIR /workspace

RUN chown sandbox:sandbox /workspace

USER sandbox

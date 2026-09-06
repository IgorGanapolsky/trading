# Harbor eval fixture. Image is digest-pinned. No pip install: Scorecard flags
# unhashed pipCommand, and the previous install lines already swallowed errors.
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

WORKDIR /evals
COPY tests/evals/harbor_configs/. .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0

ENTRYPOINT ["python", "-m", "pytest"]

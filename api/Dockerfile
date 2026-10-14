FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/base /app/uploads

# Tests automatiques : l'image n'est produite que s'ils passent
FROM base AS test
RUN pip install --no-cache-dir pytest && ENV=test python -m pytest && touch /tmp/tests-ok

FROM base
COPY --from=test /tmp/tests-ok /tmp/tests-ok
# Numéro de version (calculé par la CI à partir des tags, scripts/version.sh) et
# commit de l'image ; après les tests pour garder leur cache
ARG APP_VERSION=0.0.0-dev
ARG GIT_SHA=dev
ENV AQUAS_VERSION=$APP_VERSION AQUAS_BUILD=$GIT_SHA

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

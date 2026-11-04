# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm
WORKDIR /app
COPY --chown=10001:10001 requirements.lock pyproject.toml model-sources.json e5-assets.sha256.json download_e5.py /app/
COPY --chown=10001:10001 src /app/src
# Keep dependency/model installation in one filesystem layer. The build CA is
# supplied only by the managed build environment and is never baked into it.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock && \
    python /app/download_e5.py /models/e5 && \
    install -d -o 10001 -g 10001 -m 0700 /data
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
USER 10001:10001
EXPOSE 18350
ENTRYPOINT ["python","-m","agents_memory_collab.cli"]
CMD ["serve","--host","0.0.0.0","--port","18350","--public-url","http://127.0.0.1:18350","--e5-dir","/models/e5","--e5-manifest","/app/e5-assets.sha256.json"]

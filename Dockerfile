FROM python:3.13-slim

# no .pyc files (fs will be read-only in k8s), and unbuffered so logs show up right away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# non-root user (uid/gid 10001), no home dir or login shell
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv

# deps first so this layer stays cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY app/ app/

USER 10001:10001
# 8443 when TLS_CERT_FILE/TLS_KEY_FILE are set, plain http on 8080 otherwise
EXPOSE 8443
CMD ["python", "-m", "app"]

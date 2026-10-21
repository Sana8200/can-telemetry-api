FROM python:3.13-slim

# No .pyc files (Kubernetes will make the filesystem read-only later), and logs appear at once.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# An unprivileged user and group, both id 10001, with no home directory and no login shell.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv

# Dependencies first: this layer stays cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# The only code the server needs.
COPY app/ app/

USER 10001:10001
# HTTPS when TLS_CERT_FILE and TLS_KEY_FILE are set (plain HTTP on 8080 without them)
EXPOSE 8443
CMD ["python", "-m", "app"]
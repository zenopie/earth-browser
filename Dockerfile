FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir rns

COPY earthserv.py .
COPY www/ ./www/
COPY config/server.conf ./rns_config/config

# Identity file gets mounted as a volume to persist the .ret address
VOLUME /app/identity

EXPOSE 4243

CMD ["python3", "-u", "earthserv.py", "./www", "-i", "/app/identity/earthserv.id", "-c", "./rns_config"]

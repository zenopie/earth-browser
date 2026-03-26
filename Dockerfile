FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir rns

COPY earthserv.py .
COPY entrypoint.sh .
COPY www/ ./www/
COPY config/server.conf ./rns_config/config

RUN chmod +x entrypoint.sh

EXPOSE 4243

ENTRYPOINT ["./entrypoint.sh"]

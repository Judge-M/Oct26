FROM python:3.12-slim
WORKDIR /app
COPY app/ /app/
USER 10001:10001
EXPOSE 8080
CMD ["python", "server.py", "--host", "0.0.0.0", "--root", "/public", "--state", "/state", "--credentials", "/run/secrets/credentials"]

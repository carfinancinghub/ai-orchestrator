# Path: Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml* requirements*.txt* ./
RUN pip install --no-cache-dir fastapi uvicorn \
    && if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -r requirements-dev.txt; fi
COPY . .
ENV AIO_PROVIDER=echo AIO_DRY_RUN=false
EXPOSE 8000
CMD ["python","-m","uvicorn","app.server:app","--host","0.0.0.0","--port","8000","--log-level","warning"]

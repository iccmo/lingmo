FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends calibre && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY novel_writer/ novel_writer/
COPY tests/ tests/
COPY data/ data/
COPY frontend/dist/ frontend/dist/
ENV LINGMO_HOST=0.0.0.0 LINGMO_PORT=8000
EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "novel_writer.server:app", "--host", "0.0.0.0", "--port", "8000"]

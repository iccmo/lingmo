FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY novel_writer/ novel_writer/
COPY frontend/dist/ frontend/dist/
ENV LINGMO_HOST=0.0.0.0 LINGMO_PORT=8000
EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "novel_writer.server:app", "--host", "0.0.0.0", "--port", "8000"]

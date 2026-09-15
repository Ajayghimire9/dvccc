FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY pyproject.toml requirements-portfolio.txt ./
RUN pip install --no-cache-dir -r requirements-portfolio.txt uvicorn
COPY artifactguard ./artifactguard
COPY artifactguard.py ./artifactguard.py

RUN useradd --create-home --uid 10001 appuser && mkdir -p /var/lib/artifactguard && chown -R appuser:appuser /var/lib/artifactguard
ENV ARTIFACTGUARD_ROOT=/var/lib/artifactguard
USER appuser

EXPOSE 8000
CMD ["uvicorn", "artifactguard.api:app", "--host", "0.0.0.0", "--port", "8000"]

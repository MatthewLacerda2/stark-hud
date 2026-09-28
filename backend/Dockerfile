FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg makes the board-ready copy of the background video — once per
# background, never per play; see services/background.py. First, because it
# changes least: this layer is built once and every later build reuses it.
# Without it the board still works and plays the original, as it did before.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so the dependency layer is cached across code changes.
# The cache mount keeps the downloaded wheels between builds, so adding one
# package re-resolves that package rather than fetching all of them again.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy the application package.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

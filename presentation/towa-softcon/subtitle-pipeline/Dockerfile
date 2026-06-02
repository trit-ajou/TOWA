FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      ffmpeg \
      fontconfig \
      fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir faster-whisper tqdm

WORKDIR /workspace

ENTRYPOINT ["python3", "presentation/towa-softcon/subtitle-pipeline/presentation_subtitles.py"]
CMD ["--help"]

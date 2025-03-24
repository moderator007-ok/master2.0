FROM python:3.10.8-slim-buster

# Update and install required system packages
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev ffmpeg aria2 python3-pip git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the application code (including the N_m3u8DL-RE binary) to /app/
COPY . /app/
WORKDIR /app/

# Ensure the N_m3u8DL-RE binary is executable and available in PATH.
RUN if [ -f "./N_m3u8DL-RE" ]; then chmod +x ./N_m3u8DL-RE; fi \
    && export PATH="/app:$PATH"

# Install Python dependencies from requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

# Run both the Gunicorn app and the main bot concurrently.
CMD ["sh", "-c", "gunicorn app:app & python3 main.py"]

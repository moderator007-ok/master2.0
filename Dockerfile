FROM python:3.10.8-slim-buster

# Update and install required system packages
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       gcc libffi-dev musl-dev ffmpeg aria2 python3-pip git wget curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/

# Download the N_m3u8DL-RE binary from GitHub
# (Ensure the URL points to the correct Linux binary; here we use the raw URL from your repo)
RUN wget -O N_m3u8DL-RE https://raw.githubusercontent.com/moderator007-ok/master2.0/main/N_m3u8DL-RE \
    && chmod +x N_m3u8DL-RE

# Copy the rest of your application code into the container
COPY . /app/

# Install Python dependencies from requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

# Run both the Gunicorn app (for your Flask application) and your main bot concurrently.
CMD ["sh", "-c", "gunicorn app:app & python3 main.py"]

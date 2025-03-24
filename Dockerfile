FROM ubuntu:22.04

# Set non-interactive mode for apt
ENV DEBIAN_FRONTEND=noninteractive

# Update and install required system packages including Python 3.10, pip, gcc, etc.
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
       python3.10 python3.10-distutils python3.10-dev python3-pip \
       gcc libffi-dev ffmpeg aria2 git wget curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create symlinks for ease of use
RUN ln -s /usr/bin/python3.10 /usr/bin/python && ln -s /usr/bin/pip3 /usr/bin/pip

# Set working directory
WORKDIR /app/

# Download the N_m3u8DL-RE binary from your repository and set executable permission.
RUN wget -O N_m3u8DL-RE https://raw.githubusercontent.com/moderator007-ok/master2.0/main/N_m3u8DL-RE \
    && chmod +x N_m3u8DL-RE

# Copy the rest of your application code into the container.
COPY . /app/

# Install Python dependencies from requirements.txt.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Run both the Gunicorn app (for your Flask application) and your main bot concurrently.
CMD ["sh", "-c", "gunicorn app:app & python3 main.py"]

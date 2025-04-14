FROM python:3.12-alpine
WORKDIR /code

# Install ffmpeg and other build dependencies
RUN apk update && apk add --no-cache ffmpeg

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


COPY main.py ./
COPY src ./src
COPY dep ./dep

CMD ["python", "-u", "main.py"]


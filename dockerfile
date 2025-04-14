FROM python:3.12-alpine
WORKDIR /code

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y ffmpeg && pip install


COPY main.py ./
COPY src ./src
COPY dep ./dep

RUN useradd app
USER app

CMD ["python", "-m", "main", "--host", "0.0.0.0", "--reload"]


FROM balenalib/raspberrypi3-ubuntu-python:bionic

RUN apt-get update \
	&& apt-get install -yq --no-install-recommends \
	build-essential \
	libasound2-dev \
	libjack0 \
	libjack-dev \
	python3.6 \
	python3.6-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt

COPY . /usr/src/app

CMD ["python", "main.py"]
FROM balenalib/raspberrypi3-ubuntu-python:bionic

RUN apt-get update \
	&& apt-get install -yq --no-install-recommends \
	build-essential \
	libasound2-dev \
	libjack0 \
	libjack-dev \
	python3.6 \
	python3.6-dev \
	python3-pip \
	fluidsynth \
	fluid-soundfont-gm \
	&& rm -rf /var/lib/apt/lists/*

RUN python3.6 -m pip install --upgrade pip

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN python3.6 -m pip install setuptools
RUN python3.6 -m pip install -r requirements.txt

COPY . /usr/src/app

ENV SOUNDFONT_PATH /usr/share/sounds/sf2/FluidR3_GM.sf2

CMD ["python3.6", "main.py"]

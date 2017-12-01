#!/bin/bash
# AWS Ubuntu linux bootstrap
sudo apt-get update
sudo apt-get -y install \
    gcc \
    golang-go \
    libasound2 \
    libffi-dev \
    libgtk-3-0 \
    libssl-dev \
    libxt6 \
    p7zip-full \
    python \
    python-dev \
    python-pip

# The virtualenv package is not consistently named across distros
sudo apt-get -y install virtualenv \
	|| sudo apt-get -y install python-virtualenv

sudo apt-get remove python-six  # Native six module causes version conflict

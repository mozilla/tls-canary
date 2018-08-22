#!/bin/bash
# AWS Ubuntu linux bootstrap
sudo apt-get update
sudo apt-get -y install \
    gcc \
    golang-1.9-go \
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

# Fix go environment for using go 1.9
sudo update-alternatives --remove-all go
sudo update-alternatives --remove-all gofmt
sudo update-alternatives --install /usr/bin/go go /usr/lib/go-1.9/bin/go 20
sudo update-alternatives --install /usr/bin/gofmt gofmt /usr/lib/go-1.9/bin/gofmt 20
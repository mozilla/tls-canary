#!/bin/bash
# AWS Ubuntu 18.4 linux bootstrap
sudo apt-get update
sudo apt-get -y install \
    gcc \
    golang-go \
    libasound2 \
    libdbus-glib-1-2 \
    libffi-dev \
    libgtk-3-0 \
    libssl-dev \
    libxt6 \
    p7zip-full \
    python3 \
    python3-dev \
    python3-pip

# The virtualenv package is not consistently named across distros
sudo apt-get -y install virtualenv \
    || sudo apt-get -y install python3-virtualenv


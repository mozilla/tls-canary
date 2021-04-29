FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# pkgs from bootstrap/linux_bootstrap.sh + curl + git
RUN apt-get update && \
    apt-get -y install \
            curl \
            gcc \
            git \
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
            python3-pip \
            python3-virtualenv \
            libx11-xcb-dev

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

RUN pip3 install --upgrade git+git://github.com/mozilla/tls-canary.git

ENTRYPOINT [ "tlscanary" ]

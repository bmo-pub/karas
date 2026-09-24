FROM debian:stable

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
#   sudo \
    gosu \
    jq \
    ripgrep \
    fd-find \
    less \
    tree \
    make \
    patch \
    unzip \
    7zip \
    procps \
    curl \
    wget \
    tzdata \
    ca-certificates \
    openssh-client \
    far2l \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    nodejs \
    npm \
&&  rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 worker && useradd -m -u 1000 -g 1000 -s /bin/bash worker # && usermod -aG sudo worker
WORKDIR /home/worker/workspace
CMD []

ARG base=karas/base
FROM ${base}

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    g++ \
    clang \
    lld \
    cmake \
    gdb \
    valgrind \
    clang-tidy \
    clang-format \
    cppcheck \
    libboost-all-dev \
&&  rm -rf /var/lib/apt/lists/*

USER worker

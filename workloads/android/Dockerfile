ARG base=karas/base
FROM ${base}

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    default-jdk \
&&  rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    PATH="/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:$PATH"

RUN mkdir -p "/opt/android-sdk/cmdline-tools" \
&&  curl -fsSL -o /tmp/cmdline-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
&&  unzip -q /tmp/cmdline-tools.zip -d /tmp/cmdline-tools \
&&  mv /tmp/cmdline-tools/cmdline-tools "/opt/android-sdk/cmdline-tools/latest" \
&&  rm -rf /tmp/cmdline-tools.zip /tmp/cmdline-tools

RUN yes | sdkmanager --licenses > /dev/null && sdkmanager --install \
    "platform-tools" \
    "platforms;android-36" \
    "build-tools;36.0.0"

USER worker

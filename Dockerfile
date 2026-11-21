# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04 AS dependencies

ARG TARGETARCH
ARG DEBIAN_FRONTEND=noninteractive
ENV VCPKG_ROOT=/opt/vcpkg

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential ca-certificates cmake curl git libtool \
    ninja-build pkg-config python3 tar unzip zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY vcpkg.json vcpkg-configuration.json ./
COPY vcpkg-registry ./vcpkg-registry
COPY cmake/triplets ./cmake/triplets
RUN baseline="$(python3 -c 'import json; print(json.load(open("vcpkg.json"))["builtin-baseline"])')" \
    && git init "$VCPKG_ROOT" \
    && git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git \
    && git -C "$VCPKG_ROOT" fetch --depth 1 origin "$baseline" \
    && git -C "$VCPKG_ROOT" checkout --detach FETCH_HEAD \
    && "$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics

RUN --mount=type=cache,id=zathroth-vcpkg-downloads-${TARGETARCH},target=/opt/vcpkg/downloads,sharing=locked \
    case "$TARGETARCH" in \
      amd64) triplet=x64-linux-release ;; \
      arm64) triplet=arm64-linux-release ;; \
      *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && printf '%s\n' "$triplet" > /opt/vcpkg-triplet \
    && VCPKG_MAX_CONCURRENCY=3 "$VCPKG_ROOT/vcpkg" install \
        --triplet="$triplet" --host-triplet="$triplet" --x-install-root=/opt/vcpkg_installed \
        --clean-buildtrees-after-build --clean-packages-after-build

FROM dependencies AS build

ARG ZATHROTH_BUILD_JOBS=3

COPY . .
RUN triplet="$(cat /opt/vcpkg-triplet)" \
    && cmake --preset linux-release -DCMAKE_BUILD_TYPE=Release -DTOGGLE_BIN_FOLDER=ON \
        -DOPTIONS_ENABLE_IPO=OFF -DOPTIONS_ENABLE_SCCACHE=OFF \
        -DVCPKG_HOST_TRIPLET="$triplet" -DVCPKG_TARGET_TRIPLET="$triplet" \
        -DVCPKG_MANIFEST_INSTALL=OFF -DVCPKG_INSTALLED_DIR=/opt/vcpkg_installed \
    && cmake --build --preset linux-release --parallel "$ZATHROTH_BUILD_JOBS" \
    && strip build/linux-release/bin/canary

FROM ubuntu:24.04 AS runtime

LABEL org.opencontainers.image.title="ZATHROTH" \
      org.opencontainers.image.description="ZATHROTH game server and SQLite account manager" \
      org.opencontainers.image.source="https://github.com/Lord1Egypt/ZATHROTH" \
      org.opencontainers.image.licenses="GPL-2.0"

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libargon2-1 libatomic1 libgomp1 libstdc++6 python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --user-group --uid 10001 --no-create-home zathroth \
    && install -d -o zathroth -g zathroth /opt/zathroth /var/lib/zathroth

WORKDIR /opt/zathroth
COPY --from=build /src/build/linux-release/bin/canary /usr/local/bin/zathroth
COPY LICENSE config.lua.dist schema.sql key.pem ./
COPY data ./data
COPY data-canary ./data-canary
COPY account_manager ./account_manager
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/zathroth-start

USER zathroth
ENV ZATHROTH_DB_PATH=/var/lib/zathroth/zathroth.sqlite3 \
    PYTHONUNBUFFERED=1
EXPOSE 7171/tcp 7172/tcp 8088/tcp
ENTRYPOINT ["/usr/local/bin/zathroth-start"]

FROM mcr.microsoft.com/devcontainers/go:1.22

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    procps \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get update \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

RUN node --version && npm --version && go version

ENV GOMODCACHE=/workspaces/taxmate-australia/.cache/gomod
ENV GOCACHE=/workspaces/taxmate-australia/.cache/gocache

WORKDIR /workspaces/taxmate-australia


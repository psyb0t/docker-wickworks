---
title: "Install and run"
description: "Run the psyb0t/wickworks Docker image with docker run or docker compose: ports, image tags, platforms, healthcheck, workers, scaling and upgrades."
nav_order: 2
---

# Install and run

wickworks ships as one Docker image, `psyb0t/wickworks`, on Docker Hub. It is a single stateless HTTP process on port 8000. There is nothing to install on the host besides Docker, no volume to mount and no database to start.

## docker run

```bash
docker run --rm -p 127.0.0.1:8000:8000 psyb0t/wickworks:latest
```

That binds the port to loopback, which is what you want: wickworks has no authentication (see [Security](security.md)). Check it is up:

```bash
curl -s http://localhost:8000/health
```

Pass [configuration](configuration.md) as environment variables:

```bash
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -e MAX_BARS=10000 \
  -e WORKERS=4 \
  psyb0t/wickworks:latest
```

## docker compose

```yaml
services:
  wickworks:
    image: psyb0t/wickworks:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      LOG_LEVEL: INFO
      MAX_BARS: "5000"
      MIN_BARS: "50"
      WORKERS: "2"
```

The repository's [`docker-compose.yml`](https://github.com/psyb0t/docker-wickworks/blob/main/docker-compose.yml) is the same service with each value read from your shell (`PORT`, `LOG_LEVEL`, `MAX_BARS`, `MIN_BARS`, `WORKERS`), a container name and a build context, so `docker compose up --build` in a clone builds the image from source. It publishes the port on every interface; put `127.0.0.1:` in front of the port mapping if the host is reachable from a network you do not trust.

## Image tags and platforms

| Tag | What it is |
| --- | --- |
| `latest` | The newest build of `main` |
| `vX.Y.Z` | A release. Points at the exact image that `main` built for the tagged commit |
| `sha-<commit>` | The build of one `main` commit |

Every tag is a multi-platform image for `linux/amd64` and `linux/arm64`. Pin a `vX.Y.Z` tag in production; `latest` moves with every push to `main`.

## What runs inside

The image is `python:3.12-slim-bookworm` with the service installed into `/opt/venv`. The process runs as the unprivileged user `wickworks`, with `TZ=UTC`, and starts:

```bash
uvicorn wickworks.server:app --host 0.0.0.0 --port 8000 --workers ${WORKERS}
```

The container listens on port 8000 inside. Change the host side of the port mapping to move it, not the container side.

A Docker `HEALTHCHECK` calls `GET /health` every 30 seconds (5 second timeout, 5 second start period, 3 retries), so `docker ps` shows the container as `healthy` once it answers.

## Scaling

Each request is self-contained, so there is no session affinity to worry about. Scale up with `WORKERS` (uvicorn worker processes in one container) or out with more replicas behind a load balancer. Two replicas given the same bars return the same bytes; the test suite checks that.

The work per request is CPU bound (pandas, numba). The first request that needs SMC objects or summaries in a new container takes several seconds, because numba compiles the accelerated SMC functions on first use. numba caches the compiled code inside the container, so a restart of the same container skips most of that wait; a freshly created container pays it again. Send one warm-up request after a deploy if the first caller should not wait.

## Upgrades

There is no state, so an upgrade is pulling the new tag and replacing the container:

```bash
docker pull psyb0t/wickworks:latest
docker compose up -d
```

Read the [CHANGELOG](https://github.com/psyb0t/docker-wickworks/blob/main/CHANGELOG.md) before moving across a minor version. Before 1.0, a minor release may change the request or response shape, and the CHANGELOG says so when it does.

## Run from source

A clone with Docker and Make is enough. `make run` builds the development image and runs uvicorn on port 8000 with the source mounted from your checkout:

```bash
git clone https://github.com/psyb0t/docker-wickworks.git
cd docker-wickworks
make run
```

`PORT=9000 make run` changes the host port. In this mode `/health` reports the version `0.0.0+unknown`, because the development image runs the source directly instead of installing the package. See [Development](development.md) for the rest of the targets.

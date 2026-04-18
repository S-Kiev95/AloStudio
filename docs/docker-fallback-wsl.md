# Plan B: Docker Engine in WSL2 (no Docker Desktop)

If Docker Desktop ever becomes unrecoverable on this host, this doc is the
escape hatch. It replaces Docker Desktop with native Docker Engine running
inside a WSL2 Ubuntu distribution. The same `docker-compose.yml` works,
the same ports are exposed to Windows, and the Inference Manager bug
simply does not exist because Docker Engine does not ship that component.

## Why this is the right plan B

- Docker Engine is the OSS daemon that Docker Desktop wraps. No Inference
  Manager, no Model Runner, no `dockerInference` socket.
- WSL2 network is shared with Windows by default — containers bound to
  `0.0.0.0` inside WSL are reachable at `localhost:<port>` from Windows.
- Our `docker-compose.yml` is plain Compose v2 — no Docker Desktop-only
  features.
- Setup is a one-time ~10 minute install.

## One-time setup

Run these in an elevated PowerShell on the Windows host (once), then the
rest in Ubuntu WSL:

```powershell
# Install WSL2 with Ubuntu (skip if already installed)
wsl --install -d Ubuntu
wsl --set-default-version 2
```

Then open the Ubuntu shell (`wsl -d Ubuntu`) and install Docker Engine:

```bash
# Official Docker repository + engine
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# Run without sudo
sudo usermod -aG docker $USER
newgrp docker

# Start the daemon (WSL doesn't use systemd by default on older images;
# enable it via /etc/wsl.conf or run dockerd manually)
echo -e "[boot]\nsystemd=true" | sudo tee /etc/wsl.conf
# Then from Windows PowerShell: `wsl --shutdown` and reopen Ubuntu
sudo systemctl enable --now docker

# Smoke test
docker run --rm hello-world
```

## Using it for AloStudio

The project directory is accessible from WSL at
`/mnt/c/Users/Zeek/Desktop/AloStudio`.

```bash
cd /mnt/c/Users/Zeek/Desktop/AloStudio
docker compose up -d postgres redis mailhog minio
```

Ports are exposed to Windows automatically:

| Service   | Port (WSL → Windows) |
|-----------|----------------------|
| postgres  | 5433                 |
| redis     | 6380                 |
| mailhog   | 1025 / 8025          |
| minio     | 9100 / 9101          |

The FastAPI app (running on Windows) talks to `localhost:5433` etc. —
nothing in `.env` needs to change.

## Running Windows-side `docker` CLI against the WSL daemon (optional)

If you prefer typing `docker compose` from PowerShell instead of inside
WSL, expose the daemon over TCP and point `DOCKER_HOST` at it:

```bash
# In Ubuntu WSL — override the systemd unit to also listen on TCP localhost
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/tcp.conf > /dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// -H tcp://127.0.0.1:2375 \
  --containerd=/run/containerd/containerd.sock
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

Then in Windows:

```powershell
$env:DOCKER_HOST = "tcp://localhost:2375"
docker ps    # now talks to the WSL daemon
```

Add that line to `$PROFILE` for persistence. **Only bind to
`127.0.0.1`** — Docker over TCP without TLS must never be reachable from
the LAN.

## Rolling back to Docker Desktop

Unset `DOCKER_HOST` and start Docker Desktop again. WSL Docker keeps
running in parallel; they don't conflict.

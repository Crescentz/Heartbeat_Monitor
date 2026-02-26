set -euo pipefail

echo "[start] example_service"

docker rm -f example_service >/dev/null 2>&1 || true
docker run -d --name example_service -p 18080:18080 example_service:latest

echo "[start] ok"

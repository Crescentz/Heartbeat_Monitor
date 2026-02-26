set -euo pipefail

echo "[stop] example_service"

docker rm -f example_service >/dev/null 2>&1 || true

echo "[stop] ok"

set -euo pipefail

echo "[restart] example_service"

bash "$(dirname "$0")/stop.sh"
bash "$(dirname "$0")/start.sh"

echo "[restart] ok"

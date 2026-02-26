docker restart xinf >/dev/null 2>&1 || true
running="$(docker inspect -f '{{.State.Running}}' xinf 2>/dev/null || true)"
if [ "$running" != "true" ]; then
  docker rm -f xinf >/dev/null 2>&1 || true
  docker run --name xinf -d -p 9997:9997 -e XINFERENCE_HOME=/data -v /root/models:/data --gpus all xprobe/xinference xinference-local -H 0.0.0.0
fi

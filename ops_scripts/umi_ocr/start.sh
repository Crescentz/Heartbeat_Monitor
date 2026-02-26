docker rm -f umi-ocr >/dev/null 2>&1 || true
docker run -d --name umi-ocr -e HEADLESS=true -p 54003:1224 umi-ocr-paddle

#!/bin/bash
# towa-app 개발용 nginx reverse proxy + systemd service 설정
# Vite dev server (5173) -> nginx (80)
# 인스턴스 재부팅 시 자동 시작

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# ── nginx 설치 및 설정 ──
if ! command -v nginx &> /dev/null; then
    echo "nginx 설치 중..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq nginx
fi

sudo tee /etc/nginx/sites-available/towa-dev > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/towa-dev /etc/nginx/sites-enabled/towa-dev
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# ── systemd service 설정 ──
sudo cp "$SCRIPT_DIR/towa-dev.service" /etc/systemd/system/towa-dev.service
sudo systemctl daemon-reload
sudo systemctl enable towa-dev
sudo systemctl restart towa-dev

echo ""
echo "완료!"
echo "  - towa-dev 서비스: systemctl status towa-dev"
echo "  - 로그 확인: journalctl -u towa-dev -f"
echo "  - http://<외부IP> 로 접속 가능"

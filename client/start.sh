#!/bin/sh
if [ -z "$CONF" ]; then
    echo "【错误】请在 docker-compose.yml 的 environment 中填入服务端生成的明文配置！"
    exit 1
fi

mkdir -p /etc/wireguard
echo "$CONF" > /etc/wireguard/wg0.conf

echo 1 > /proc/sys/net/ipv4/ip_forward

wg-quick down wg0 2>/dev/null
wg-quick up wg0

echo "✅ Own-VPN异地组网 客户端已成功加入 10.0.0.0/8 虚拟内网。"
tail -f /dev/null

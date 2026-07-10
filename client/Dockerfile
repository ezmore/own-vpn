FROM alpine:latest

RUN apk add --no-cache wireguard-tools iproute2 iptables

WORKDIR /vpn
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]

FROM alpine:latest

RUN apk add --no-cache \
    wireguard-tools \
    iproute2 \
    iptables \
    python3 \
    py3-flask

WORKDIR /app
COPY app.py .

EXPOSE 41090 51820/udp

CMD ["python3", "app.py"]

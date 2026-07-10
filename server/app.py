import os
import subprocess
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

CLIENTS = {}
AVAILABLE_IPS = [f"10.0.0.{i}" for i in range(2, 254)]
SERVER_IP = "10.0.0.1"

def init_wg_interface():
    os.system("echo 1 > /proc/sys/net/ipv4/ip_forward")
    
    if subprocess.call(["wg", "show", "wg0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        os.makedirs("/etc/wireguard", exist_ok=True)
        os.system("wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub")
        os.system("ip link add dev wg0 type wireguard")
        os.system(f"ip address add {SERVER_IP}/8 dev wg0")
        os.system("ip link set mtu 1420 up dev wg0")
        
        os.system("tc qdisc del dev wg0 root 2>/dev/null")
        os.system("tc qdisc add dev wg0 root handle 1: htb default 10")
        os.system("tc class add dev wg0 parent 1: classid 1:10 htb rate 200mbit")

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Own-VPN异地组网后台</title><meta charset="utf-8">
    <style>body{font-family:-apple-system,sans-serif;margin:40px;background:#fafafa;color:#333;}
    .box{background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.05);margin-bottom:20px;}
    input,button{padding:8px 12px;margin:5px;border:1px solid #ddd;border-radius:4px;}
    button{background:#0070f3;color:#fff;border:none;cursor:pointer;} table{width:100%;border-collapse:collapse;}
    th,td{padding:12px;text-align:left;border-bottom:1px solid #eee;} th{background:#f0f0f0;}</style>
    </head>
    <body>
        <h2>🌐 虚拟自组网控制台 (Alpine 极简版)</h2>
        <div class="box">
            <form action="/api/client" method="POST">
                <input type="text" name="name" placeholder="节点名称(如: CN_Server_1)" required>
                <input type="number" name="speed" placeholder="限速上限 (Mbps)" value="100">
                <input type="number" name="conn" placeholder="连接数上限" value="1000">
                <input type="text" name="ports" placeholder="开放端口(如: 80,443 / 空代表全开)">
                <button type="submit">接入新节点</button>
            </form>
        </div>
        <div class="box">
            <table>
                <tr><th>节点名</th><th>虚拟内网IP</th><th>带宽限速</th><th>最大并发数</th><th>开放端口</th><th>下发配置</th></tr>
                {% for id, c in clients.items() %}
                <tr>
                    <td><b>{{ c.name }}</b></td><td><code>{{ c.ip }}</code></td><td>{{ c.speed }} Mbps</td><td>{{ c.conn }}</td><td>{{ c.ports or '全部开放' }}</td>
                    <td><a href="/api/client/{{ id }}/config" target="_blank">获取明文配置</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, clients=CLIENTS)

@app.route('/api/client', methods=['POST'])
def create_client():
    name = request.form.get('name')
    speed = request.form.get('speed', '100')
    conn = request.form.get('conn', '1000')
    ports = request.form.get('ports', '')

    if not AVAILABLE_IPS:
        return "IP池已满", 400

    client_ip = AVAILABLE_IPS.pop(0)
    client_id = str(len(CLIENTS) + 1)

    c_private = subprocess.check_output("wg genkey", shell=True).decode().strip()
    c_public = subprocess.check_output(f"echo '{c_private}' | wg pubkey", shell=True).decode().strip()
    s_public = subprocess.check_output("cat /etc/wireguard/server.pub", shell=True).decode().strip()

    os.system(f"wg set wg0 peer {c_public} allowed-ips {client_ip}/32")

    class_id = int(client_id) + 10
    os.system(f"tc class add dev wg0 parent 1: classid 1:{class_id} htb rate {speed}mbit ceil {speed}mbit")
    os.system(f"tc filter add dev wg0 protocol ip parent 1:0 prio 1 u32 match ip dst {client_ip} flowid 1:{class_id}")

    if conn:
        os.system(f"iptables -I FORWARD -i wg0 -s {client_ip} -m connlimit --connlimit-above {conn} -j REJECT")
    
    if ports:
        os.system(f"iptables -A FORWARD -i wg0 -s {client_ip} -j REJECT")
        for port in ports.split(','):
            p = port.strip()
            os.system(f"iptables -I FORWARD -i wg0 -s {client_ip} -p tcp --dport {p} -j ACCEPT")
            os.system(f"iptables -I FORWARD -i wg0 -s {client_ip} -p udp --dport {p} -j ACCEPT")

    CLIENTS[client_id] = {
        "name": name, "ip": client_ip, "speed": speed, "conn": conn, "ports": ports,
        "private_key": c_private, "server_public": s_public
    }
    return jsonify({"status": "success", "ip": client_ip})

@app.route('/api/client/<client_id>/config', methods=['GET'])
def get_config(client_id):
    client = CLIENTS.get(client_id)
    if not client: return "未找到该节点", 404
    vps_ip = request.host.split(':')[0]
    config = f"""[Interface]
PrivateKey = {client['private_key']}
Address = {client['ip']}/8
DNS = 114.114.114.114

[Peer]
PublicKey = {client['server_public']}
Endpoint = {vps_ip}:51820
AllowedIPs = 10.0.0.0/8
PersistentKeepalive = 25
"""
    return config, 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    init_wg_interface()
    app.run(host='0.0.0.0', port=41090)

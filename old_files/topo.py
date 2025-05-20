from flask import Flask, request, jsonify
from threading import Thread
from werkzeug.serving import make_server
from mininet.topo import Topo
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel

# Flask app
app = Flask(__name__)
net = None  # Global Mininet object

# ──────────────────────────────
# Flask API Endpoints
# ──────────────────────────────

@app.route('/exec', methods=['POST'])
def exec_cmd():
    data = request.json
    cmd = data.get("cmd", "")
    if not cmd:
        return jsonify({"error": "Missing 'cmd' in body"}), 400

    tokens = cmd.strip().split()
    if len(tokens) < 2:
        return jsonify({"error": "Command must include host and action"}), 400

    host_name = tokens[0]
    host_cmd = " ".join(tokens[1:])
    try:
        host = net.get(host_name)
        result = host.cmd(host_cmd)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/set_bw', methods=['POST'])
def set_bandwidth():
    data = request.json
    node1 = net.get(data['node1'])
    node2 = net.get(data['node2'])
    bw = data['bw']  # Mbps

    link = net.linksBetween(node1, node2)[0]
    link.intf1.config(bw=bw)
    link.intf2.config(bw=bw)

    return jsonify({"status": "ok", "link": f"{data['node1']}<->{data['node2']}", "bw": bw})

# ──────────────────────────────
# Flask server in background thread
# ──────────────────────────────

class FlaskThread(Thread):
    def __init__(self, app):
        super().__init__()
        self.server = make_server('0.0.0.0', 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print("[INFO] Starting Flask API on http://0.0.0.0:5000")
        self.server.serve_forever()

    def shutdown(self):
        print("[INFO] Stopping Flask API...")
        self.server.shutdown()

# ──────────────────────────────
# Mininet Topology
# ──────────────────────────────

class SimpleTopo(Topo):
    def build(self):
        # Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')

        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        # Host to switch links
        self.addLink(h1, s1, cls=TCLink, bw=100)
        self.addLink(h2, s2, cls=TCLink, bw=100)
        self.addLink(h3, s3, cls=TCLink, bw=100)

        # Inter-switch links
        self.addLink(s1, s2, cls=TCLink, bw=100)
        self.addLink(s1, s3, cls=TCLink, bw=100)
        self.addLink(s2, s3, cls=TCLink, bw=100)
        self.addLink(s1, s4, cls=TCLink, bw=100)
        self.addLink(s2, s4, cls=TCLink, bw=100)
        self.addLink(s3, s4, cls=TCLink, bw=100)

# ──────────────────────────────
# Main Runner
# ──────────────────────────────

def run():
    global net
    topo = SimpleTopo()
    controller = RemoteController('c0', ip='127.0.0.1', port=6633)
    net = Mininet(topo=topo, controller=controller, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    net.start()

    # Start Flask in a background thread
    flask_thread = FlaskThread(app)
    flask_thread.start()

    print("[INFO] Mininet is running. Type CLI commands or POST to http://localhost:5000")
    try:
        CLI(net)
    finally:
        net.stop()
        flask_thread.shutdown()

if __name__ == '__main__':
    setLogLevel('info')
    run()

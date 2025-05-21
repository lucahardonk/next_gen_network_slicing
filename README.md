# Dynamic SDN Slicing System

This project includes a complete Mininet + Ryu + Python-based system for dynamic flow slicing, visualization, and bandwidth enforcement.

## 🚀 How to Run the System

You will need **4 terminals** open to run the full system. Follow these steps in order:

### 🔹 Terminal 1 – Launch Mininet
```bash
sudo python3 mininet_runner.py
```

> ⚠️ When you're done, run this to **clean up the network**:
```bash
./stop_net.sh
```

---

### 🔹 Terminal 2 – Start the Ryu Controller
```bash
ryu-manager dynamic_sliced_tunnel_controller.py
```

This handles flow slicing, tunnel setup, and dynamic path installation.

---

### 🧠 (Optional) Terminal 3 – Run Flow Allocator
```bash
python3 main.py
```

This CLI tool lets you allocate flows dynamically using shortest paths or other algorithms.

---

## 📁 File Overview

- `mininet_runner.py` – Starts the Mininet network and Flask API.
- `stop_net.sh` – Stops and cleans Mininet.
- `dynamic_sliced_tunnel_controller.py` – Ryu controller for slicing/tunnels.
- `main.py` – CLI flow allocator.
- `visualize_initial_topology.py` – Plots static topology.
- `visualize_running_topology.py` – Live topology monitor.

---


## Manual Testing 
given for example this allocated flow "h1,s1,s4,s2,h2,8,1,5002"

# On h2 (server):
h2 iperf -s -p 5002 &

# On h1 (client):
h1 iperf -c 10.0.0.2 -p 5002 -t 10

# On h1 (server):
h1 iperf -s -p 5002 &

# On h2 (client):
h2 iperf -c 10.0.0.1 -p 5002 -t 10



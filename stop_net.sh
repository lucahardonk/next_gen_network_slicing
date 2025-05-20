#!/usr/bin/env bash

# stop_net.sh: Fully clean Mininet + OVS + Ryu + tc + QoS + flow state + flow DB

set -euo pipefail

echo "[stop_net] 🧹 Stopping Mininet and clearing its state..."
sudo mn -c > /dev/null 2>&1 || true

echo "[stop_net] 🔌 Killing any running Ryu controllers..."
pkill -f ryu-manager 2>/dev/null || true

echo "[stop_net] 🔎 Detecting all OVS bridges..."
BRIDGES=$(sudo ovs-vsctl list-br)

echo "[stop_net] 🧼 Deleting OpenFlow flows and bridges..."
for br in $BRIDGES; do
    echo "  - Cleaning bridge: $br"
    sudo ovs-ofctl -O OpenFlow13 del-flows "$br" 2>/dev/null || true
    sudo ovs-vsctl del-br "$br" 2>/dev/null || true
done

echo "[stop_net] 🧽 Removing all OVS QoS and Queue configs..."
sudo ovs-vsctl -- --all destroy QoS -- --all destroy Queue

echo "[stop_net] 🧵 Clearing all 'tc' qdiscs on relevant interfaces..."
ALL_INTF=$(ip -o link show | awk -F': ' '{print $2}' | grep -E '^s[0-9]+-eth[0-9]+$' || true)

for intf in $ALL_INTF; do
    echo "  - Clearing tc on $intf"
    sudo tc qdisc del dev "$intf" root 2>/dev/null || true
done

CSV_FILES=("data/running_network.csv" "data/initial_topology.csv" "data/allocated_flow.csv")

echo "[stop_net] 📄 Truncating CSV files to reset state..."
for file in "${CSV_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -n > "$file"
        echo "  - Reset: $file"
    else
        echo "  - Skipped (not found): $file"
    fi
done

JSON_LIST_FILES=("data/allocated_flows.json")

echo "[stop_net] 📘 Resetting JSON list-based state files..."
for file in "${JSON_LIST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "[]" > "$file"
        echo "  - Reset: $file"
    else
        echo "  - Skipped (not found): $file"
    fi
done

echo "[stop_net] ✅ Cleanup complete. Environment is fully reset."

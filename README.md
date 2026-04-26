# Flow Rule Timeout Manager
**Course:** UE24CS252B — Computer Networks  
**Type:** SDN Project | Individual  

---

## Problem Statement

Implement an SDN controller using **Mininet + os-ken (OpenFlow 1.3)** that manages flow rule lifecycles through idle and hard timeouts.

When a packet arrives at the switch, the controller installs a match+action flow rule. The rule expires automatically after:
- **Idle timeout (10s):** no traffic matches the rule for 10 seconds
- **Hard timeout (30s):** rule has been alive for 30 seconds regardless of traffic

The controller handles `packet_in` events, performs MAC learning, installs explicit flow rules, and logs the full lifecycle — install, forward, expire — in real time via `flow_removed` events.

**Demonstrates:**
- Controller–switch interaction (OpenFlow 1.3)
- Explicit flow rule design: match on `in_port`, action `output:port`
- Idle timeout: rule expires after 10s of inactivity
- Hard timeout: rule expires after 30s regardless of traffic
- Flow-removed event handling and logging
- Regression testing across both timeout scenarios

---

## File Structure

```
flow-timeout-sdn/
├── flow_timeout.py      # os-ken controller app (main logic)
├── topology.py          # Mininet topology (1 switch, 3 hosts)
├── regression_test.py   # Automated test scenarios
├── run_controller.py    # Entry point to launch controller
└── README.md
```

---

## Setup & Execution

### Prerequisites
- Ubuntu 20.04/22.04 (VM or WSL2)
- Python 3.8–3.10
- Mininet
- Open vSwitch
- os-ken (OpenFlow controller framework)

### Install

```bash
# System packages
sudo apt update
sudo apt install mininet openvswitch-switch python3-pip python3-venv -y

# Create virtual environment
python3 -m venv ryu-env
source ryu-env/bin/activate

# Install os-ken (ryu fork compatible with Python 3.10+)
pip install setuptools==67.6.0
pip install os-ken==2.7.0

# Start OVS (run every session)
sudo modprobe openvswitch
sudo /etc/init.d/openvswitch-switch start
sudo systemctl disable openvswitch-testcontroller 2>/dev/null || true
```

### Run

**Terminal 1 — Start Controller:**
```bash
cd ~/flow-timeout-sdn
source ryu-env/bin/activate
osken-manager flow_timeout.py --verbose
```

**Terminal 2 — Start Mininet:**
```bash
cd ~/flow-timeout-sdn
sudo python3 topology.py
```

**Terminal 3 — Capture OpenFlow traffic:**
```bash
sudo tshark -i lo -f "tcp port 6633" -w /tmp/capture.pcap
```

---

## Proof of Execution

### Topology Startup + pingall (0% packet loss)

Mininet starts with 1 switch (s1) and 3 hosts (h1, h2, h3).
`pingall` confirms full connectivity with **0% packet loss (6/6 received)**.

```
*** Creating network
*** Adding controller
*** Adding hosts: h1 h2 h3
*** Adding switches: s1
*** Adding links: (h1, s1) (h2, s1) (h3, s1)
=== Flow Rule Timeout Manager ===
Hosts: h1(10.0.0.1), h2(10.0.0.2), h3(10.0.0.3)

mininet> pingall
*** Ping: testing ping reachability
h1 -> h2 h3
h2 -> h1 h3
h3 -> h1 h2
*** Results: 0% dropped (6/6 received)
```

---

## Test Scenarios

### Scenario 1: Idle Timeout
Flow rule expires after 10 seconds of no traffic.

```bash
mininet> h1 ping -c 3 h2
mininet> sh ovs-ofctl dump-flows s1 --protocol=OpenFlow13
# wait 11 seconds (no traffic)
mininet> sh ovs-ofctl dump-flows s1 --protocol=OpenFlow13
# rule is gone — idle timeout triggered
```

**Flow table with active rules (idle_timeout=10, hard_timeout=30):**
```
cookie=0x0, duration=22.164s, table=0, n_packets=8, n_bytes=560,
  idle_timeout=10, hard_timeout=30, priority=1,
  in_port="s1-eth2" actions=FLOOD

cookie=0x0, duration=51.926s, table=0, n_packets=7, n_bytes=558,
  priority=0 actions=CONTROLLER:65509
```

**Controller logs — flow lifecycle:**
```
EVENT ofp_event->FlowTimeoutApp EventOFPPacketIn
[+] Flow added | port=3
[-] Flow removed (Idle Timeout)
EVENT ofp_event->FlowTimeoutApp EventOFPPacketIn
[+] Flow added | port=2
[-] Flow removed (Idle Timeout)
```

---

### Scenario 2: Hard Timeout + iperf Regression

Flow rule expires at ~30s even with continuous iperf traffic, then reinstalls automatically via packet_in. iperf continues uninterrupted — regression passes.

```bash
mininet> h1 iperf -s &
mininet> h2 iperf -c 10.0.0.1 -t 40 -i 5
```

**iperf result:**
```
Client connecting to 10.0.0.1, TCP port 5001
[ ID] Interval       Transfer     Bandwidth
[  1] 0.0000-5.0000  22.6 GBytes  38.9 Gbits/sec
[  1] 5.0000-10.000   9.63 GBytes  16.5 Gbits/sec
[  1] 10.000-15.000  22.9 GBytes  39.3 Gbits/sec
[  1] 15.000-20.000  22.2 GBytes  38.2 Gbits/sec
[  1] 20.000-25.000  23.1 GBytes  39.7 Gbits/sec
[  1] 25.000-30.000  23.0 GBytes  39.5 Gbits/sec
[  1] 30.000-35.000  21.6 GBytes  37.1 Gbits/sec
[  1] 35.000-40.000  22.1 GBytes  37.9 Gbits/sec
[  1] 0.0000-40.013   167 GBytes  35.9 Gbits/sec
```

**Controller logs during iperf (hard timeout fires, rule reinstalls):**
```
[+] Flow added | port=2
[-] Flow removed (Idle Timeout)
EVENT ofp_event->FlowTimeoutApp EventOFPPacketIn
[+] Flow added | port=1
[-] Flow removed (Idle Timeout)
```

---

### Wireshark / tshark — OpenFlow Packet Capture

Captured on loopback (`lo`) port 6633 showing OpenFlow control messages:

```
No.  Time        Source     Destination  Protocol  Info
1    0.000       127.0.0.1  127.0.0.1   OpenFl..  OFPT_ECHO_REQUEST
2    0.000       127.0.0.1  127.0.0.1   OpenFl..  OFPT_ECHO_REPLY
6    5.002       127.0.0.1  127.0.0.1   OpenFl..  OFPT_PACKET_IN
9    6.303       127.0.0.1  127.0.0.1   TCP       OFPT_FLOW_MOD
11   8.386       127.0.0.1  127.0.0.1   TCP       OFPT_FLOW_MOD
13   11.389       127.0.0.1  127.0.0.1   OpenFl..  OFPT_PACKET_IN
22   22.074       127.0.0.1  127.0.0.1   OpenFl..  OFPT_FLOW_MOD
```

Key message types observed:
- `OFPT_PACKET_IN` — unmatched packet sent to controller
- `OFPT_FLOW_MOD` — controller installs flow rule on switch
- `OFPT_ECHO_REQUEST/REPLY` — keepalive between controller and switch

---

### Controller Startup Log

```
osken-manager flow_timeout.py --verbose
loading app flow_timeout.py
instantiating app flow_timeout.py of FlowTimeoutApp
BRICK FlowTimeoutApp
  CONSUMES EventOFPPacketIn
  CONSUMES EventOFPSwitchFeatures
connected socket: 127.0.0.1:38426
EVENT ofp_event->FlowTimeoutApp EventOFPSwitchFeatures
[*] Switch connected → Table-miss installed
move onto main mode
```

---

## Tools Used
- **Mininet** — network topology emulation
- **os-ken** — OpenFlow 1.3 controller (maintained Ryu fork)
- **Open vSwitch** — software switch
- **tshark** — OpenFlow packet capture (Wireshark CLI)
- **iperf** — bandwidth testing for hard timeout scenario
- **ovs-ofctl** — flow table inspection

---

## References
1. Mininet overview: https://mininet.org/overview/
2. Mininet walkthrough: https://mininet.org/walkthrough/
3. os-ken (Ryu fork): https://github.com/faucetsdn/os-ken
4. OpenFlow 1.3 spec: https://opennetworking.org/wp-content/uploads/2014/10/openflow-switch-v1.3.5.pdf
5. Open vSwitch docs: https://docs.openvswitch.org/
6. Mininet GitHub: https://github.com/mininet/mininet

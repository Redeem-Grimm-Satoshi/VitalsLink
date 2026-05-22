# VitalsLink — Distributed Temperature Monitoring (Demo)

A small end-to-end medical-style telemetry demo:

```
 ┌───────────────────┐                                    ┌──────────────────────────┐
 │  Raspberry Pi     │   HTTP POST  /api/temperature      │  Laptop                  │
 │  ─────────────    │ ─────────────────────────────────► │  ─────                   │
 │  DS18B20 sensor   │     {"temperature_c": 36.8, ...}    │  Flask + Socket.IO       │
 │  pi_publisher.py  │      every 1 second over LAN       │  server.py               │
 └───────────────────┘                                    │                          │
                                                         │  WebSocket push          │
                                                         │       │                  │
                                                         │       ▼                  │
                                                         │  templates/dashboard.html │
                                                         └──────────┬───────────────┘
                                                                    │  public URL via
                                                                    │  cloudflared / ngrok
                                                                    ▼
                                                          🌐 your Zoom audience
```

## Files

| File | Where it runs | Purpose |
|------|---------------|---------|
| `pi_publisher.py` | Raspberry Pi | Reads DS18B20 every second, POSTs JSON to the laptop. |
| `server.py` | Laptop | Flask + Socket.IO. Receives readings and pushes them to every connected browser. |
| `templates/dashboard.html` | Laptop (served by `server.py`) | The medical dashboard. Big live reading, status banner, live chart, session stats. |
| `requirements.txt` | Laptop | Python deps for the server. |

---

## 1 · Raspberry Pi setup (sensor side)

### Wire the DS18B20
Use the standard 3-wire DS18B20 wiring with a **4.7 kΩ pull-up resistor between DATA and 3.3 V**:

| DS18B20 pin | Pi pin (BCM)        | Pi physical pin |
|-------------|---------------------|-----------------|
| VDD (red)   | 3.3 V               | pin 1           |
| DATA (yellow) | GPIO 4            | pin 7           |
| GND (black) | GND                 | pin 6 or 9      |
| (pull-up)   | 4.7 kΩ between DATA and 3.3 V |        |

### Enable 1-Wire (one-time)
```bash
sudo raspi-config
# → Interface Options → 1-Wire → Enable → reboot
```
(or add `dtoverlay=w1-gpio` to `/boot/config.txt` and reboot)

Verify the sensor shows up:
```bash
ls /sys/bus/w1/devices/
# expect a folder named like 28-3c01a8164d2c
```

### Install Python dependency
```bash
pip3 install requests
# (or: sudo apt install python3-requests)
```

### Copy `pi_publisher.py` to the Pi
Easiest path:
```bash
# from your laptop, in this folder:
scp pi_publisher.py pi@<RASPBERRY_PI_LAN_IP>:~
```

### Edit the laptop IP
Open `pi_publisher.py` and set `LAPTOP_IP` to your laptop's LAN IP. To find it:

* **macOS / Linux:** `ifconfig` (or `ip a`) — look at the LAN interface bound to your switch.
* **Windows:** `ipconfig` — find the IPv4 address on the Ethernet adapter.

You can also pass it on the command line: `python3 pi_publisher.py 192.168.1.42`.

### Run
```bash
python3 pi_publisher.py
# Expect:
#   Publishing to http://192.168.1.42:5000/api/temperature  (patient=PT-0427)
#   12:01:14   36.78 °C   -> 200 OK
#   12:01:15   36.81 °C   -> 200 OK
```

---

## 2 · Laptop setup (server + dashboard)

```bash
# from this folder
python3 -m venv venv && source venv/bin/activate    # optional but recommended
pip install -r requirements.txt
python server.py
```

You should see:
```
  Dashboard:   http://localhost:5000/
  Pi posts to: http://<your-laptop-LAN-IP>:5000/api/temperature
```

Open **http://localhost:5000/** in your browser. The dashboard will say "Awaiting sensor stream…" until the Pi connects.

### Allow incoming connections on port 5000
Your OS firewall will probably prompt the first time. Say **Allow**, otherwise the Pi's POSTs never arrive.
* macOS: System Settings → Network → Firewall → allow `python`.
* Windows: when prompted by Windows Defender, allow on **Private** networks.
* Linux (ufw): `sudo ufw allow 5000/tcp`.

Once the Pi script is running you should see lines in the server terminal:
```
[12:01:14] 36.78°C  (PT-0427)
```
and the dashboard goes live.

---

## 3 · Public link for your Zoom audience

Pick **one** of these.

### Option A — Cloudflare Tunnel (recommended, no signup)
```bash
# macOS:    brew install cloudflared
# Windows:  https://github.com/cloudflare/cloudflared/releases  (pick *windows-amd64.exe)
# Linux:    https://pkg.cloudflare.com/

cloudflared tunnel --url http://localhost:5000
```
It prints a URL like `https://<random-words>.trycloudflare.com`. **That's the link you paste in Zoom chat.** Works with WebSockets out of the box — the live chart will update for everyone.

### Option B — ngrok (needs free signup)
```bash
# macOS: brew install ngrok
# Then: sign up at https://dashboard.ngrok.com, copy your authtoken, run:
ngrok config add-authtoken <YOUR_TOKEN>
ngrok http 5000
```
Use the `https://...ngrok-free.app` URL.

### Sanity check before the meeting
Open the public URL on your phone over **cellular** (not Wi-Fi). If you see the dashboard update live, your audience will too.

---

## 4 · Presentation tips

* **Open the dashboard in two windows:** one local (low-latency, looks great when you point at the screen) and one on the public URL (so you can show the audience what they're seeing). Share the public-URL window in Zoom.
* **Warm-up first.** Tuck the sensor under your armpit ~2 minutes before you go live so it's already showing realistic body temp (~36.5–37 °C). Cold-start from room temp looks unrealistic.
* **Cue the demo moment.** Have the sensor *out* of your armpit at first — show room temp (~22 °C, will flash red as "hypothermia"). Then place it under your armpit; the audience watches the line climb in real time toward normothermia. Great pacing.
* **Talking points it lets you hit:**
  * Edge sensing (Pi + DS18B20 via 1-Wire)
  * LAN telemetry (HTTP transport, JSON payload)
  * Real-time fan-out (Socket.IO / WebSocket)
  * Clinical decision logic (axillary thresholds, status classification)
  * Remote access for distributed care teams (the tunnel)
  * Extensibility hooks for AI: anomaly detection, sepsis early-warning scoring, fever-pattern classification.
* If asked "is this HIPAA-compliant?" — say no, this is a demo: in production you'd add TLS end-to-end, auth on the ingest endpoint, signed device identity, and audit logs. Shows you know what's missing.

---

## 5 · Troubleshooting

**Pi: `No DS18B20 detected at /sys/bus/w1/devices/28-*`**
1-Wire isn't enabled, or wiring is off. Re-check the pull-up resistor.

**Pi: `network error: Connection refused`**
Server isn't running, wrong `LAPTOP_IP`, or firewall is blocking. Test with `curl`:
```bash
curl -X POST http://<LAPTOP_IP>:5000/api/temperature \
     -H 'Content-Type: application/json' \
     -d '{"temperature_c": 36.5}'
```
Run that **from the Pi**. If it fails, the network path is wrong, not the script.

**Dashboard says "Disconnected" even though server is up**
The browser couldn't open a WebSocket. If you opened the dashboard via `file://` instead of `http://localhost:5000/`, it won't work — always use the HTTP URL.

**Tunnel works but chart doesn't update for remote viewers**
Some restrictive corporate networks block WebSockets. Cloudflare Tunnel handles WS well; if a viewer is on a locked-down network, the page still loads (HTTP polling fallback) but updates may be delayed.

**Readings look noisy / jumpy**
DS18B20 is ±0.5 °C. To smooth, change `read_temp_c()` in `pi_publisher.py` to average 3 consecutive reads, or apply a simple moving average on the server side before broadcasting.

**You want to fake data without the sensor (rehearsal)**
On the laptop:
```bash
python -c "
import time, requests, random
t = 36.5
while True:
    t += random.uniform(-0.05, 0.08)
    t = max(35.5, min(38.8, t))
    requests.post('http://localhost:5000/api/temperature',
                  json={'temperature_c': round(t,2), 'patient_id':'PT-0427','sensor_id':'DS18B20-01'})
    time.sleep(1)
"
```
Useful for testing the tunnel and the dashboard look before the Pi is wired up.

---

Good luck with the presentation 🩺

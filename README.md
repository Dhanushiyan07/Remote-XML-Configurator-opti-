# Remote XML Configurator

A desktop GUI tool for remotely editing XML configuration files on edge devices over SSH — with XSD-driven validation, live device health monitoring, and a full audit trail. Built primarily for the **NVIDIA Jetson Orin NX**, but works with any Windows or Linux machine reachable over SSH.

!\[Python](https://img.shields.io/badge/Python-3.10%2B-blue)
!\[PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
!\[Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Jetson-orange)

## Overview

Engineers working with embedded edge devices often need to tweak XML configuration values — camera settings, network parameters, sensor thresholds — without physically connecting a keyboard and monitor to the device. This tool replaces manual SSH text-editing with a clean, validated, auditable desktop application.
Connect once with SSH credentials, then browse XML files, edit parameters with type-aware input widgets, validate every change against the XSD schema before saving, and watch the device's CPU, RAM, disk, network, and (on Jetson) GPU and thermal stats update live — all from one window.


## Features

* **SSH connection with auto-reconnect** — the tool silently reconnects if the connection drops mid-session
* **XSD-driven validation** — every value is checked against schema rules (type, range, enum, pattern, length) before it's written to the device
* **Type-aware edit widgets** — checkbox for booleans, dropdown for enums, spin box for numbers with min/max bounds, text field for strings
* **Live diff preview** — see exactly what will change before you save, debounced so typing stays smooth
* **Backup before save** — optionally create a timestamped backup on the device before overwriting
* **Full audit log** — every change recorded with timestamp, old value, new value; filterable, sortable, exportable to CSV
* **Real-time device monitor** — CPU, RAM, disk, and network usage shown as live pie charts
* **Jetson Orin NX support** — GPU utilisation, per-core CPU loads, power rail monitoring (mW), unified memory, and all thermal zones with colour-coded status
* **Consistent UI** — every dialog and popup uses the same custom card-style design, no native OS dialogs
* **Non-blocking architecture** — all SSH and file operations run on background threads; the UI never freezes

## Architecture

```
remote-xml-configurator/
│
├── main.py                      # Entry point
│
├── core/                        # Business logic — no UI imports
│   ├── session.py                # Shared session state (credentials, audit log)
│   ├── ssh\_manager.py             # Paramiko SSH/SFTP wrapper, auto-reconnect
│   ├── validator.py               # XSD rule-based value validation
│   ├── xsd\_parser.py              # Parses XSD schema into rule dictionaries
│   └── xml\_parser.py              # XML read/write utility
│
└── ui/                          # PyQt5 interface layer
    ├── login\_window.py            # SSH login screen
    ├── main\_window.py             # App shell: tabs, sidebar, status bar
    ├── xml\_editor\_panel.py        # XML viewer + parameter editor
    ├── device\_monitor\_panel.py    # Real-time metrics, pie charts, Jetson panel
    ├── audit\_log\_panel.py         # Change history table, CSV export
    ├── styled\_dialogs.py          # Shared dialog components
    └── flow\_layout.py             # Custom wrapping layout for chip badges
```

The codebase follows a strict **two-layer split**: `core/` contains zero UI imports and can be unit-tested independently; `ui/` contains all PyQt5 widgets and calls into `core/` but never the reverse.

A single `Session` dataclass is created on login and passed by reference to every panel — there is no global state and no duplicated SSH connections.


## Requirements

* Python 3.10+
* PyQt5
* Paramiko

```bash
pip install PyQt5 paramiko
```

The target device needs an SSH server running (OpenSSH on Linux/Jetson, OpenSSH or another SSH server on Windows) and must be reachable on the network. For full Jetson features, `tegrastats` must be available (included by default in the Jetson SDK).



## Installation

```bash
git clone https://github.com/Dhanushiyan07/Remote-XML-Configurator-opti-.git
cd remote-xml-configurator
pip install -r requirements.txt
python main.py
```

Make sure `core/\_\_init\_\_.py` and `ui/\_\_init\_\_.py` exist (even empty) so Python treats them as packages.


## Usage

1. Launch the app with `python main.py`
2. Enter the device IP address, SSH username, and password, then click **Connect**
3. The sidebar populates with all `.xml` files found in the remote config directory
4. Click a file to open it in the **XML Editor** tab
5. Select a parameter from the searchable list on the left
6. Edit the value using the type-appropriate widget on the right
7. Click **Save to device** — choose whether to create a backup first
8. Switch to **Device Monitor** to see live CPU/RAM/Disk/Network (and GPU/thermal on Jetson)
9. Switch to **Audit Log** to review every change made this session, filter, or export to CSV

### Remote directory configuration

By default, the tool looks for XML files in `C:/xml\_configs/` on the remote device. To change this for a Linux/Jetson deployment, edit `REMOTE\_DIR` in `core/session.py`:

```python
REMOTE\_DIR: str = "/home/user/xml\_configs"
```

XSD schema files must live in the same directory with the same base name as the XML file (e.g. `network.xml` pairs with `network.xsd`). If no matching XSD is found, the tool offers to let you browse for one manually, or falls back to inferring types from the values themselves.


## How the Device Monitor Works

The monitor auto-detects the connected OS with a single SSH command and switches between two completely different command sets:

**Windows** (used during development/testing) — avoids WMI/CIM entirely since those commands fail silently over non-interactive SSH sessions. Uses `typeperf` for CPU, `Get-CimInstance` for RAM, `Get-PSDrive` for disk, `TickCount64` for uptime, and `tasklist`/`Get-Process` for the process list.

**Linux / Jetson Orin NX** (production target) — reads directly from `/proc/stat`, `/proc/meminfo`, `/proc/net/dev`, and `/proc/loadavg`. When `tegrastats` is detected, a dedicated dark-themed panel appears showing GPU utilisation, per-core CPU loads, unified memory, GPU power draw, VDD power rails, swap usage, and every thermal zone with colour-coded status (cool/warm/hot/critical).

All four core metrics (CPU, RAM, Disk, Network) are rendered as donut-style pie charts using pure `QPainter` — no external charting library required.



## Performance Notes

Background metric polling is designed to complete in under 3 seconds per cycle so it never blocks file save operations. Slow commands (`systeminfo`, sampled `Get-Counter`, blocking `sleep()` calls) were deliberately avoided in favour of instant WMI/CIM one-liners and server-side shell sleeps that don't hold up the SSH channel.



## Known Limitations

* Single XML file edited at a time (no multi-tab editing yet)
* No undo/redo — only Discard reverts to the last loaded value
* Password-only SSH authentication (no key-based login yet)
* Load average is not available on Windows (Windows has no equivalent concept)

See the project report for the full list of planned future improvements.



## Tech Stack

|Component|Technology|
|-|-|
|Language|Python 3.10+|
|GUI|PyQt5|
|SSH / SFTP|Paramiko|
|XML parsing|`xml.etree.ElementTree`|
|GPU monitoring|`tegrastats` (Jetson SDK)|
|Thermal monitoring|`/sys/class/thermal/`|

\---

## Contributing

This was built as an internship project. Suggestions and pull requests are welcome — see the **Future Improvements** section in the project report for ideas already on the roadmap (multi-file editing, undo/redo, SSH key auth, live trend graphs, alert thresholds).

\---


## Acknowledgements

Built during an internship project focused on remote configuration management for the NVIDIA Jetson Orin NX edge device platform.


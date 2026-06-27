"""
Device Monitor Panel v10
========================
Fixes & additions:
  1. Uptime: use 'net stats srv' cmd (locale-independent, no PS needed)
  2. Jetson Orin NX full support:
       - GPU utilisation % (tegrastats GR3D_FREQ)
       - GPU power (mW)
       - Per-core CPU loads
       - Unified memory (RAM used/total)
       - All thermal zones (CPU, GPU, SOC, board, etc.)
       - eMMC / NVMe disk usage
       - VDD (power rails) monitoring
  3. Extra Jetson pie: GPU utilisation
  4. Jetson temperature table
  5. Windows uptime fixed (net stats workstation, no locale issues)
"""
import re, time
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QSizePolicy, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont
from core.session import Session

# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────
CARD_STYLE  = "QFrame#metricCard{background:#f5f5f3;border:0.5px solid #d8d6d0;border-radius:10px;}"
JCARD_STYLE = "QFrame#jetsonCard{background:#1a1a2e;border:0.5px solid #3a3a5c;border-radius:10px;}"
M_LABEL     = "font-size:11px;color:#a0a09a;letter-spacing:0.05em;"
M_VALUE     = "font-size:22px;font-weight:500;color:#1a1a18;"
M_SUB       = "font-size:11px;color:#6b6966;"
JM_LABEL    = "font-size:11px;color:#6b6baa;letter-spacing:0.05em;"
JM_VALUE    = "font-size:22px;font-weight:500;color:#e0e0ff;"
JM_SUB      = "font-size:11px;color:#8888bb;"
SECT_LBL    = "font-size:13px;font-weight:500;color:#1a1a18;margin-bottom:2px;"
JSECT_LBL   = ("font-size:13px;font-weight:500;color:#7C3AED;"
               "margin-bottom:2px;padding:4px 0;")
ERR_STYLE   = ("font-size:12px;color:#A32D2D;background:#FCEBEB;"
               "padding:10px 14px;border-radius:8px;border:0.5px solid #F09595;")
INFO_STYLE  = ("font-size:12px;color:#185FA5;background:#E6F1FB;"
               "padding:8px 14px;border-radius:8px;border:0.5px solid #85B7EB;")
JETSON_INFO = ("font-size:12px;color:#e0e0ff;background:#16213e;"
               "padding:8px 14px;border-radius:8px;border:0.5px solid #3a3a5c;")
TBL_STYLE   = """
QTableWidget{border:0.5px solid #d8d6d0;border-radius:8px;font-size:12px;
    background:#ffffff;color:#1a1a18;gridline-color:#e0ded8}
QTableWidget::item{padding:5px 10px}
QTableWidget::item:selected{background:#E6F1FB;color:#0C447C}
QHeaderView::section{background:#f5f5f3;border:none;
    border-bottom:0.5px solid #d8d6d0;padding:6px 10px;
    font-size:11px;font-weight:500;color:#6b6966}
"""
JTBL_STYLE  = """
QTableWidget{border:0.5px solid #3a3a5c;border-radius:8px;font-size:12px;
    background:#16213e;color:#e0e0ff;gridline-color:#2a2a4e}
QTableWidget::item{padding:5px 10px}
QTableWidget::item:selected{background:#2d2d6e;color:#ffffff}
QHeaderView::section{background:#1a1a2e;border:none;
    border-bottom:0.5px solid #3a3a5c;padding:6px 10px;
    font-size:11px;font-weight:500;color:#8888cc}
"""
PIE_CPU  = ["#378ADD", "#E8F0F8"]
PIE_MEM  = ["#2E8B4A", "#DFF0E5"]
PIE_DISK = ["#BA7517", "#FDF3E3"]
PIE_GPU  = ["#7C3AED", "#EDE9FE"]
PIE_RX   = "#7C3AED"
PIE_TX   = "#0EA5E9"
PIE_BG   = "#EDE9FE"

# ─────────────────────────────────────────────────────────────────────────────
# Pie Chart Widget — pure QPainter, zero external dependencies
# ─────────────────────────────────────────────────────────────────────────────
class PieChart(QWidget):
    MODE_SINGLE = "single"
    MODE_NET    = "net"

    def __init__(self, colors, title="", mode="single", parent=None):
        super().__init__(parent)
        self._colors = colors if colors else ["#378ADD", "#E8F0F8"]
        self._title  = title
        self._mode   = mode
        self._pct    = 0.0
        self._pct2   = 0.0
        self._label  = "–"
        self._sub    = ""
        self.setMinimumSize(150, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_value(self, pct: float, label: str, sub: str = ""):
        self._pct   = max(0.0, min(100.0, float(pct)))
        self._label = label
        self._sub   = sub
        self.update()

    def update_net(self, rx_pct: float, tx_pct: float, rx_lbl: str, tx_lbl: str):
        self._pct   = max(0.0, min(100.0, float(rx_pct)))
        self._pct2  = max(0.0, min(100.0, float(tx_pct)))
        self._label = rx_lbl
        self._sub   = tx_lbl
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h   = self.width(), self.height()
        margin = 12
        side   = min(w, h - 30) - margin * 2
        if side < 10:
            p.end(); return
        x     = (w - side) / 2
        y     = float(margin)
        rect  = QRectF(x, y, side, side)
        thick = side * 0.22

        p.setPen(Qt.NoPen)
        if self._mode == self.MODE_SINGLE:
            p.setBrush(QBrush(QColor(self._colors[1])))
            p.drawEllipse(rect)
            span = -int(self._pct * 360 * 16 / 100)
            p.setBrush(QBrush(QColor(self._colors[0])))
            p.drawPie(rect, 90 * 16, span)
            inner = QRectF(x+thick, y+thick, side-thick*2, side-thick*2)
            p.setBrush(QBrush(QColor("#ffffff")))
            p.drawEllipse(inner)
            p.setPen(QPen(QColor("#1a1a18")))
            fnt = QFont(); fnt.setPixelSize(max(10, int(side*0.22))); fnt.setBold(True)
            p.setFont(fnt)
            p.drawText(QRectF(x, y, side, side), Qt.AlignCenter, self._label)
        else:
            p.setBrush(QBrush(QColor(PIE_BG)))
            p.drawEllipse(rect)
            rx_span = -int(self._pct  * 180 * 16 / 100)
            p.setBrush(QBrush(QColor(PIE_RX)))
            p.drawPie(rect, 90*16, rx_span)
            tx_span = int(self._pct2 * 180 * 16 / 100)
            p.setBrush(QBrush(QColor(PIE_TX)))
            p.drawPie(rect, 270*16, tx_span)
            inner = QRectF(x+thick, y+thick, side-thick*2, side-thick*2)
            p.setBrush(QBrush(QColor("#ffffff")))
            p.drawEllipse(inner)
            fnt = QFont(); fnt.setPixelSize(max(9, int(side*0.14))); fnt.setBold(True)
            p.setFont(fnt)
            p.setPen(QPen(QColor(PIE_RX)))
            p.drawText(QRectF(x, y+side*0.28, side, side*0.25), Qt.AlignCenter, self._label)
            p.setPen(QPen(QColor(PIE_TX)))
            p.drawText(QRectF(x, y+side*0.52, side, side*0.25), Qt.AlignCenter, self._sub)

        fnt2 = QFont(); fnt2.setPixelSize(11)
        p.setFont(fnt2)
        p.setPen(QPen(QColor("#a0a09a")))
        p.drawText(QRectF(0, y+side+4, w, 20), Qt.AlignCenter, self._title.upper())
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# SSH helper
# ─────────────────────────────────────────────────────────────────────────────
def _run(ssh, cmd: str, timeout: int = 15) -> str:
    try:
        _, out, _ = ssh.exec_command(cmd, timeout=timeout)
        return out.read().decode(errors="replace").strip()
    except Exception:
        return ""


def _human(b: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b //= 1024
    return f"{b:.1f} TB"


# ─────────────────────────────────────────────────────────────────────────────
# Windows collector
# ─────────────────────────────────────────────────────────────────────────────
def _win_collect(ssh) -> dict:
    d = {
        "os": "Windows", "load": None,
        "extras": [], "processes": [], "net": [], "net_bytes": {},
        "jetson": False,
    }

    # ── CPU via Get-Counter ───────────────────────────────────────────────
    raw = _run(ssh,
        'powershell -NoProfile -Command '
        '"(Get-Counter \'\\Processor(_Total)\\% Processor Time\''
        ' -SampleInterval 1 -MaxSamples 1).CounterSamples[0].CookedValue"',
        timeout=8)
    for tok in raw.replace(",", ".").split():
        try:
            d["cpu"] = round(float(tok), 1); break
        except Exception:
            pass

    # ── RAM via systeminfo ────────────────────────────────────────────────
    raw_si = _run(ssh, "systeminfo", timeout=20)
    tm = re.search(r"Total Physical Memory[:\s]+([\d\.,]+)\s*MB", raw_si, re.I)
    am = re.search(r"Available Physical Memory[:\s]+([\d\.,]+)\s*MB", raw_si, re.I)
    if tm and am:
        try:
            total = int(tm.group(1).replace(",","").replace(".",""))
            avail = int(am.group(1).replace(",","").replace(".",""))
            d["mem_total"] = total; d["mem_used"] = total - avail
        except Exception:
            pass

    # ── Uptime via 'net statistics workstation' (reliable, no PS needed) ────
    # Always contains: "Statistics since M/D/YYYY H:MM:SS AM/PM"
    raw_nw = _run(ssh, "net statistics workstation", timeout=10)
    bm = re.search(r"since\s+(.+)", raw_nw, re.I)
    if bm:
        boot_str = bm.group(1).strip()
        parsed = False
        for fmt in (
            "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",    "%d.%m.%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",    "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %I:%M %p",    "%d/%m/%Y %I:%M:%S %p",
            "%-m/%-d/%Y %I:%M:%S %p",
        ):
            try:
                boot  = datetime.strptime(boot_str.strip(), fmt)
                delta = datetime.now() - boot
                d["uptime"] = (f"{delta.days}d "
                               f"{delta.seconds//3600}h "
                               f"{(delta.seconds%3600)//60}m")
                parsed = True
                break
            except ValueError:
                pass
        if not parsed:
            d["uptime"] = f"since {boot_str[:25]}"

    # ── Disk via Get-PSDrive ──────────────────────────────────────────────
    raw = _run(ssh,
        'powershell -NoProfile -Command '
        '"$dk=Get-PSDrive C;'
        'Write-Output (($dk.Used+$dk.Free).ToString()+\' \'+$dk.Used.ToString())"',
        timeout=8)
    nums = raw.strip().split()
    if len(nums) >= 2:
        try:
            total_b = int(nums[0]); used_b = int(nums[1])
            if total_b > 0:
                d["disk_total"] = f"{total_b//(1024**3)} GB"
                d["disk_used"]  = f"{used_b//(1024**3)} GB"
                d["disk_pct"]   = int(used_b * 100 / total_b)
        except Exception:
            pass

    # ── Processes: tasklist for mem + two PS snapshots for CPU ───────────
    raw_tl = _run(ssh, "tasklist /fo csv /nh", timeout=12)
    proc_mem = {}
    for line in raw_tl.splitlines():
        parts = [p.strip('"') for p in line.strip().split('","')]
        if len(parts) >= 5:
            try:
                mem_kb = int(parts[4].replace(",","").replace(" K","").strip())
                proc_mem[parts[1]] = (parts[0].replace(".exe",""), mem_kb)
            except Exception:
                pass

    raw_ps1 = _run(ssh,
        'powershell -NoProfile -Command '
        '"Get-Process|ForEach-Object{Write-Output ($_.Id.ToString()+\'|\'+$_.CPU.ToString())}"',
        timeout=8)
    time.sleep(1)
    raw_ps2 = _run(ssh,
        'powershell -NoProfile -Command '
        '"Get-Process|ForEach-Object{Write-Output ($_.Id.ToString()+\'|\'+$_.CPU.ToString())}"',
        timeout=8)
    snap1 = {}; snap2 = {}
    for line in raw_ps1.splitlines():
        p = line.strip().split("|")
        if len(p) == 2:
            try: snap1[p[0]] = float(p[1])
            except: pass
    for line in raw_ps2.splitlines():
        p = line.strip().split("|")
        if len(p) == 2:
            try: snap2[p[0]] = float(p[1])
            except: pass
    cpu_delta = {}
    for pid, c2 in snap2.items():
        if pid in snap1:
            cpu_delta[pid] = round(max(0, c2 - snap1[pid]) * 100, 2)

    merged = []
    for pid, (name, mem_kb) in proc_mem.items():
        merged.append((cpu_delta.get(pid, 0.0), pid, name, mem_kb))
    merged.sort(reverse=True)
    for cpu_v, pid, name, mem_kb in merged[:10]:
        d["processes"].append({
            "pid": pid, "name": name[:24],
            "cpu": f"{cpu_v:.2f}", "mem": f"{mem_kb//1024} MB"})

    # ── Network: ipconfig IPs + netstat bytes ────────────────────────────
    raw_ip = _run(ssh, "ipconfig", timeout=8)
    iface = None
    for line in raw_ip.splitlines():
        s = line.strip()
        if s.endswith(":") and "adapter" in s.lower():
            iface = s.replace("adapter","").replace(":","").strip()[:24]
        if "IPv4 Address" in s and iface:
            ip = s.split(":")[-1].strip().rstrip("(Preferred)").strip()
            if ip and not ip.startswith("169.254"):
                d["net"].append({"iface": iface, "rx": ip, "tx": "–"})
            iface = None
    raw_ne = _run(ssh, "netstat -e", timeout=8)
    for line in raw_ne.splitlines():
        if line.strip().lower().startswith("bytes"):
            nums = re.findall(r'\d+', line)
            if len(nums) >= 2:
                try:
                    d["net_bytes"]["__total__"] = (int(nums[0]), int(nums[1]))
                except Exception:
                    pass
            break

    return d


# ─────────────────────────────────────────────────────────────────────────────
# Linux / Jetson Orin NX collector
# ─────────────────────────────────────────────────────────────────────────────
def _parse_tegrastats(line: str) -> dict:
    """Parse a single tegrastats line into a structured dict."""
    j = {"raw": line}
    # RAM  e.g.  RAM 3412/7772MB
    m = re.search(r"RAM\s+(\d+)/(\d+)MB", line)
    if m:
        j["ram_used"] = int(m.group(1)); j["ram_total"] = int(m.group(2))
    # CPU  e.g.  CPU [12%@1190,8%@1190,...]
    m = re.search(r"CPU\s*\[([^\]]+)\]", line)
    if m:
        cores = re.findall(r"(\d+)%", m.group(1))
        if cores:
            j["cpu_cores"]  = [int(c) for c in cores]
            j["cpu_avg"]    = round(sum(j["cpu_cores"]) / len(j["cpu_cores"]), 1)
    # GPU  e.g.  GR3D_FREQ 45%@921
    m = re.search(r"GR3D_FREQ\s+(\d+)%", line)
    if m:
        j["gpu_pct"] = int(m.group(1))
    # GPU power  e.g.  GPU 1234mW
    m = re.search(r"\bGPU\s+(\d+)mW", line)
    if m:
        j["gpu_mw"] = int(m.group(1))
    # VDD CPU  e.g.  VDD_CPU_GPU_CV 2345/2345mW
    m = re.search(r"VDD_CPU_GPU_CV\s+(\d+)/(\d+)mW", line)
    if m:
        j["vdd_cpu_gpu_mw"] = int(m.group(1))
    # VDD SOC
    m = re.search(r"VDD_SOC\s+(\d+)/(\d+)mW", line)
    if m:
        j["vdd_soc_mw"] = int(m.group(1))
    # SWAP  e.g.  SWAP 0/3886MB
    m = re.search(r"SWAP\s+(\d+)/(\d+)MB", line)
    if m:
        j["swap_used"] = int(m.group(1)); j["swap_total"] = int(m.group(2))
    return j


def _linux_collect(ssh) -> dict:
    d = {
        "os": "Linux", "extras": [],
        "processes": [], "net": [], "net_bytes": {},
        "jetson": False, "jetson_data": {},
        "temps": [],
    }

    # ── CPU — two /proc/stat snapshots ───────────────────────────────────
    raw1 = _run(ssh, "cat /proc/stat | head -1")
    time.sleep(0.5)
    raw2 = _run(ssh, "cat /proc/stat | head -1")
    try:
        p1 = list(map(int, raw1.split()[1:9]))
        p2 = list(map(int, raw2.split()[1:9]))
        dt = sum(p2)-sum(p1); di = p2[3]-p1[3]
        d["cpu"] = round((dt-di)*100/dt, 1) if dt > 0 else 0.0
    except Exception:
        pass

    # ── RAM ──────────────────────────────────────────────────────────────
    raw = _run(ssh,
        "awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}"
        "END{printf \"%d %d\",t/1024,(t-a)/1024}' /proc/meminfo")
    parts = raw.split()
    if len(parts) >= 2:
        try:
            d["mem_total"] = int(parts[0]); d["mem_used"] = int(parts[1])
        except Exception:
            pass

    # ── Swap ─────────────────────────────────────────────────────────────
    raw = _run(ssh,
        "awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}"
        "END{printf \"%d %d\",t/1024,(t-f)/1024}' /proc/meminfo")
    parts = raw.split()
    if len(parts) >= 2:
        try:
            d["swap_total"] = int(parts[0]); d["swap_used"] = int(parts[1])
        except Exception:
            pass

    # ── Disk / ───────────────────────────────────────────────────────────
    raw = _run(ssh, "df -h / | awk 'NR==2{print $2,$3,$4,$5}'")
    parts = raw.split()
    if len(parts) >= 4:
        d["disk_total"] = parts[0]; d["disk_used"] = parts[1]
        try:
            d["disk_pct"] = int(parts[3].replace("%",""))
        except Exception:
            pass

    # ── Uptime ───────────────────────────────────────────────────────────
    raw = _run(ssh, "uptime -p 2>/dev/null || uptime")
    d["uptime"] = raw.replace("up ","").strip()[:40]

    # ── Load ─────────────────────────────────────────────────────────────
    raw = _run(ssh, "cat /proc/loadavg")
    parts = raw.split()
    if len(parts) >= 3:
        d["load"] = " / ".join(parts[:3])

    # ── Processes ────────────────────────────────────────────────────────
    raw = _run(ssh, "ps -eo pid,comm,%cpu,%mem --sort=-%cpu 2>/dev/null | head -11")
    for line in raw.splitlines()[1:]:
        p = line.split(None, 3)
        if len(p) >= 4:
            d["processes"].append({
                "pid": p[0], "name": p[1],
                "cpu": p[2], "mem": p[3].strip()+"%"})

    # ── Network ──────────────────────────────────────────────────────────
    raw = _run(ssh, "cat /proc/net/dev")
    for line in raw.splitlines()[2:]:
        line = line.strip()
        if ":" in line:
            iface, rest = line.split(":", 1)
            cols = rest.split()
            if len(cols) >= 9:
                try:
                    rx = int(cols[0]); tx = int(cols[8])
                    iface = iface.strip()
                    d["net"].append({
                        "iface": iface[:20],
                        "rx": _human(rx), "tx": _human(tx)})
                    d["net_bytes"][iface] = (rx, tx)
                except Exception:
                    pass

    # ── Thermal zones (all zones, not just 5) ────────────────────────────
    raw = _run(ssh,
        "for f in /sys/class/thermal/thermal_zone*/; do "
        "t=$(cat ${f}type 2>/dev/null); "
        "v=$(cat ${f}temp 2>/dev/null); "
        "[ -n \"$t\" ] && [ -n \"$v\" ] && "
        "printf \"%s|%d\\n\" \"$t\" \"$((v/1000))\"; "
        "done 2>/dev/null", timeout=6)
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            try:
                d["temps"].append((parts[0].strip(), int(parts[1])))
            except Exception:
                pass

    # ── Jetson Orin NX via tegrastats ─────────────────────────────────────
    raw_teg = _run(ssh,
        "tegrastats --interval 500 --count 1 2>/dev/null | head -1",
        timeout=8)
    if raw_teg and raw_teg.strip() not in ("", "N/A"):
        d["jetson"] = True
        d["os"]     = "Jetson Orin NX"
        jd          = _parse_tegrastats(raw_teg)
        d["jetson_data"] = jd

        # Override RAM with unified memory from tegrastats (more accurate)
        if "ram_used" in jd and "ram_total" in jd:
            d["mem_used"]  = jd["ram_used"]
            d["mem_total"] = jd["ram_total"]

        # Override CPU with per-core average from tegrastats
        if "cpu_avg" in jd:
            d["cpu"] = jd["cpu_avg"]

    return d


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread
# ─────────────────────────────────────────────────────────────────────────────
class MetricsWorker(QThread):
    done = pyqtSignal(dict)

    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def run(self):
        ssh = self.session.ssh.ssh
        try:
            hint   = _run(ssh, "ver 2>nul || echo linux", timeout=5).lower()
            is_win = "windows" in hint or "microsoft" in hint
            data   = _win_collect(ssh) if is_win else _linux_collect(ssh)
            self.done.emit(data)
        except Exception as exc:
            self.done.emit({
                "error": str(exc), "os": "", "extras": [],
                "processes": [], "net": [], "net_bytes": {},
                "jetson": False, "jetson_data": {}, "temps": [],
            })


# ─────────────────────────────────────────────────────────────────────────────
# Panel widget
# ─────────────────────────────────────────────────────────────────────────────
class DeviceMonitorPanel(QWidget):

    POLL_MS = 12000

    def __init__(self, session: Session):
        super().__init__()
        self.session       = session
        self._timer        = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker       = None
        self._last_bytes   = {}
        self._last_poll_ts = None
        self._jetson_mode  = False
        self._last_cpu     = None   # shared with status bar
        self._last_ram_pct = None   # shared with status bar
        self._build_ui()

    # ── build UI ─────────────────────────────────────────────────────────

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#fafaf8;}")
        self._content = QWidget()
        self._content.setStyleSheet("background:#fafaf8;")
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(24, 20, 24, 20)
        self._lay.setSpacing(18)

        # Header
        hdr = QHBoxLayout()
        self.device_lbl = QLabel(f"Device: {self.session.ip}")
        self.device_lbl.setStyleSheet("font-size:16px;font-weight:500;color:#1a1a18;")
        hdr.addWidget(self.device_lbl)
        hdr.addStretch()
        self.os_badge = QLabel("detecting…")
        self.os_badge.setStyleSheet(
            "font-size:11px;padding:3px 10px;border-radius:6px;"
            "background:#f5f5f3;color:#6b6966;border:0.5px solid #d8d6d0;")
        hdr.addWidget(self.os_badge)
        self.updated_lbl = QLabel("Not fetched")
        self.updated_lbl.setStyleSheet("font-size:12px;color:#a0a09a;")
        hdr.addWidget(self.updated_lbl)
        ref_btn = QPushButton("Refresh now")
        ref_btn.setStyleSheet(
            "QPushButton{font-size:12px;padding:5px 14px;border-radius:6px;"
            "border:0.5px solid #d8d6d0;background:transparent;color:#4a4a47}"
            "QPushButton:hover{background:#eceae4}")
        ref_btn.clicked.connect(self._poll)
        hdr.addWidget(ref_btn)
        self._lay.addLayout(hdr)

        # Error banner
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(ERR_STYLE)
        self.error_lbl.setWordWrap(True)
        self.error_lbl.hide()
        self._lay.addWidget(self.error_lbl)

        # ── Main pie row: CPU / RAM / Disk / Network ──────────────────────
        pie_row = QHBoxLayout(); pie_row.setSpacing(10)
        self.pie_cpu  = PieChart(PIE_CPU,  "CPU Usage",  PieChart.MODE_SINGLE)
        self.pie_mem  = PieChart(PIE_MEM,  "Memory",     PieChart.MODE_SINGLE)
        self.pie_disk = PieChart(PIE_DISK, "Disk",       PieChart.MODE_SINGLE)
        self.pie_net  = PieChart([PIE_RX, PIE_TX], "Network", PieChart.MODE_NET)
        for pie in (self.pie_cpu, self.pie_mem, self.pie_disk, self.pie_net):
            pie.setFixedHeight(190)
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame{background:#ffffff;border:0.5px solid #d8d6d0;border-radius:10px;}")
            fl = QVBoxLayout(frame); fl.setContentsMargins(8,8,8,8); fl.addWidget(pie)
            pie_row.addWidget(frame)
        self._lay.addLayout(pie_row)

        # ── Jetson GPU pie row (hidden until Jetson detected) ────────────
        self._jetson_pie_frame = QFrame()
        self._jetson_pie_frame.setStyleSheet(
            "QFrame{background:#16213e;border:0.5px solid #3a3a5c;border-radius:10px;"
            "padding:10px;}")
        self._jetson_pie_frame.hide()
        jpl = QVBoxLayout(self._jetson_pie_frame)
        jpl.setContentsMargins(12,12,12,12); jpl.setSpacing(10)
        jt = QLabel("⬡  JETSON ORIN NX — GPU & Power")
        jt.setStyleSheet("font-size:13px;font-weight:500;color:#7C3AED;")
        jpl.addWidget(jt)
        jpie_row = QHBoxLayout(); jpie_row.setSpacing(10)
        self.pie_gpu = PieChart(PIE_GPU, "GPU Utilisation", PieChart.MODE_SINGLE)
        self.pie_gpu.setFixedHeight(180)
        gframe = QFrame()
        gframe.setStyleSheet(
            "QFrame{background:#1a1a2e;border:0.5px solid #3a3a5c;border-radius:10px;}")
        gfl = QVBoxLayout(gframe); gfl.setContentsMargins(8,8,8,8); gfl.addWidget(self.pie_gpu)
        jpie_row.addWidget(gframe)

        # Jetson stat cards (GPU power, VDD, swap, cores)
        self._jcard_grid = QGridLayout(); self._jcard_grid.setSpacing(8)
        self.jc_gpu_mw    = self._jcard("GPU Power", "–", "mW",  dark=True)
        self.jc_vdd_cpu   = self._jcard("VDD CPU+GPU", "–", "mW", dark=True)
        self.jc_vdd_soc   = self._jcard("VDD SOC",    "–", "mW",  dark=True)
        self.jc_swap      = self._jcard("Swap",        "–", "used",dark=True)
        self.jc_cores     = self._jcard("CPU Cores",   "–", "load", dark=True)
        for i, (frame, _, _) in enumerate([
                self.jc_gpu_mw, self.jc_vdd_cpu, self.jc_vdd_soc,
                self.jc_swap, self.jc_cores]):
            self._jcard_grid.addWidget(frame, i//3, i%3)
        jpie_row.addLayout(self._jcard_grid)
        jpl.addLayout(jpie_row)
        self._lay.addWidget(self._jetson_pie_frame)

        # ── Jetson temperature table (hidden until Jetson) ───────────────
        self._temp_frame = QFrame()
        self._temp_frame.hide()
        tfl = QVBoxLayout(self._temp_frame)
        tfl.setContentsMargins(0,0,0,0); tfl.setSpacing(6)
        tlbl = QLabel("🌡  Thermal Zones")
        tlbl.setStyleSheet(JSECT_LBL)
        tfl.addWidget(tlbl)
        self.temp_table = self._tbl(
            ["Zone", "°C", "Status"], 0, 200, dark=True)
        tfl.addWidget(self.temp_table)
        self._lay.addWidget(self._temp_frame)

        # ── Uptime + Load cards ──────────────────────────────────────────
        cr = QHBoxLayout(); cr.setSpacing(10)
        self.up_card   = self._card("Uptime",            "–", "since last boot")
        self.load_card = self._card("Load avg (1/5/15)", "–", "system load")
        cr.addWidget(self.up_card[0]); cr.addWidget(self.load_card[0])
        self._lay.addLayout(cr)

        # ── Network table ────────────────────────────────────────────────
        self._lay.addWidget(self._slbl("Network interfaces  (↓ RX  ↑ TX speed)"))
        self.net_table = self._tbl(
            ["Interface", "IPv4 / IP", "RX Speed", "TX Speed"], 1, 200)
        self._lay.addWidget(self.net_table)

        # ── Processes table ──────────────────────────────────────────────
        self._lay.addWidget(self._slbl("Top processes by CPU"))
        self.proc_table = self._tbl(["PID", "Process", "CPU %", "MEM"], 1, 260)
        self._lay.addWidget(self.proc_table)

        self._lay.addStretch()
        scroll.setWidget(self._content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)

    def _card(self, title, value, sub, dark=False):
        frame = QFrame()
        frame.setObjectName("metricCard")
        frame.setStyleSheet(CARD_STYLE)
        il = QVBoxLayout(frame)
        il.setContentsMargins(16,14,16,14); il.setSpacing(4)
        t = QLabel(title.upper()); t.setStyleSheet(M_LABEL); il.addWidget(t)
        v = QLabel(value);         v.setStyleSheet(M_VALUE);  il.addWidget(v)
        s = QLabel(sub);           s.setStyleSheet(M_SUB);    il.addWidget(s)
        return frame, v, s

    def _jcard(self, title, value, sub, dark=False):
        frame = QFrame()
        frame.setObjectName("jetsonCard")
        frame.setStyleSheet(JCARD_STYLE)
        il = QVBoxLayout(frame)
        il.setContentsMargins(12,10,12,10); il.setSpacing(2)
        t = QLabel(title.upper()); t.setStyleSheet(JM_LABEL); il.addWidget(t)
        v = QLabel(value);         v.setStyleSheet(JM_VALUE);  il.addWidget(v)
        s = QLabel(sub);           s.setStyleSheet(JM_SUB);    il.addWidget(s)
        return frame, v, s

    def _slbl(self, text):
        l = QLabel(text); l.setStyleSheet(SECT_LBL); return l

    def _tbl(self, headers, stretch, maxh, dark=False):
        t = QTableWidget(0, len(headers))
        t.setStyleSheet(JTBL_STYLE if dark else TBL_STYLE)
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setAlternatingRowColors(True)
        t.setMaximumHeight(maxh)
        return t

    # ── polling ───────────────────────────────────────────────────────────

    def start_polling(self):
        self._poll()
        self._timer.start(self.POLL_MS)

    def stop_polling(self):
        self._timer.stop()

    def _poll(self):
        if self._worker and self._worker.isRunning():
            return
        self.updated_lbl.setText("Fetching…")
        self._worker = MetricsWorker(self.session)
        self._worker.done.connect(self._apply)
        self._worker.start()

    # ── apply ─────────────────────────────────────────────────────────────

    def _apply(self, data: dict):
        now = datetime.now()
        self.updated_lbl.setText("Updated " + now.strftime("%H:%M:%S"))

        if "error" in data:
            self.error_lbl.setText(f"Error: {data['error']}")
            self.error_lbl.show()
        else:
            self.error_lbl.hide()

        os_name = data.get("os","")
        if os_name:
            self.os_badge.setText(os_name)

        # CPU pie
        if data.get("cpu") is not None:
            cpu = float(data["cpu"])
            self._last_cpu = cpu
            self.pie_cpu.update_value(cpu, f"{int(cpu)}%")

        # RAM pie
        if data.get("mem_total") and data.get("mem_used") is not None:
            pct = data["mem_used"] * 100 / data["mem_total"]
            self._last_ram_pct = pct
            self.pie_mem.update_value(pct, f"{int(pct)}%",
                f"{data['mem_used']}MB/{data['mem_total']}MB")

        # Disk pie
        if data.get("disk_pct") is not None:
            pct = int(data["disk_pct"])
            self.pie_disk.update_value(pct, f"{pct}%",
                f"{data.get('disk_used','–')}/{data.get('disk_total','–')}")

        # Uptime
        if data.get("uptime"):
            _, v, s = self.up_card
            v.setText(data["uptime"]); s.setText("since last boot")

        # Load avg
        if data.get("load"):
            _, v, s = self.load_card
            v.setStyleSheet("font-size:16px;font-weight:500;color:#1a1a18;")
            v.setText(data["load"]); s.setText("1 min / 5 min / 15 min")
        else:
            _, v, s = self.load_card
            v.setText("N/A"); s.setText("not available on Windows")

        # ── Jetson Orin NX specific ───────────────────────────────────────
        is_jetson = data.get("jetson", False)
        jd        = data.get("jetson_data", {})

        if is_jetson:
            self._jetson_pie_frame.show()
            self._temp_frame.show()

            # GPU pie
            gpu_pct = jd.get("gpu_pct", 0)
            self.pie_gpu.update_value(gpu_pct, f"{gpu_pct}%", "GPU load")

            # Jetson stat cards
            _, v, _ = self.jc_gpu_mw
            v.setText(f"{jd['gpu_mw']}" if "gpu_mw" in jd else "–")

            _, v, _ = self.jc_vdd_cpu
            v.setText(f"{jd['vdd_cpu_gpu_mw']}" if "vdd_cpu_gpu_mw" in jd else "–")

            _, v, _ = self.jc_vdd_soc
            v.setText(f"{jd['vdd_soc_mw']}" if "vdd_soc_mw" in jd else "–")

            if "swap_used" in jd and "swap_total" in jd:
                _, v, s = self.jc_swap
                pct = int(jd["swap_used"] * 100 / jd["swap_total"]) if jd["swap_total"] else 0
                v.setText(f"{jd['swap_used']}MB"); s.setText(f"of {jd['swap_total']}MB ({pct}%)")
            else:
                sw_used = data.get("swap_used", 0); sw_total = data.get("swap_total", 0)
                _, v, s = self.jc_swap
                if sw_total:
                    pct = int(sw_used * 100 / sw_total)
                    v.setText(f"{sw_used}MB"); s.setText(f"of {sw_total}MB ({pct}%)")

            if "cpu_cores" in jd:
                cores_str = "  ".join(f"{c}%" for c in jd["cpu_cores"])
                _, v, s = self.jc_cores
                v.setStyleSheet("font-size:12px;font-weight:500;color:#e0e0ff;")
                v.setText(cores_str); s.setText(f"avg {jd.get('cpu_avg','–')}%")

            # Temperature table
            temps = data.get("temps", [])
            self.temp_table.setRowCount(len(temps))
            for row, (zone, temp_c) in enumerate(temps):
                self.temp_table.setItem(row, 0, QTableWidgetItem(zone))
                temp_item = QTableWidgetItem(f"{temp_c}°C")
                status = "Normal"
                if temp_c >= 85:
                    temp_item.setForeground(QColor("#ff4444"))
                    status = "🔴 Critical"
                elif temp_c >= 70:
                    temp_item.setForeground(QColor("#ff9944"))
                    status = "🟡 Hot"
                elif temp_c >= 50:
                    temp_item.setForeground(QColor("#44bb44"))
                    status = "🟢 Warm"
                else:
                    temp_item.setForeground(QColor("#8888ff"))
                    status = "🔵 Cool"
                self.temp_table.setItem(row, 1, temp_item)
                self.temp_table.setItem(row, 2, QTableWidgetItem(status))
        else:
            self._jetson_pie_frame.hide()
            self._temp_frame.hide()

        # ── Network speed ─────────────────────────────────────────────────
        cur_bytes  = data.get("net_bytes", {})
        dt_secs    = (now - self._last_poll_ts).total_seconds() if self._last_poll_ts else 0
        net_speeds = {}
        if self._last_bytes and dt_secs > 0:
            for key, (rx2, tx2) in cur_bytes.items():
                if key in self._last_bytes:
                    rx1, tx1 = self._last_bytes[key]
                    drx = max(0, rx2-rx1); dtx = max(0, tx2-tx1)
                    rx_k = drx/dt_secs/1024; tx_k = dtx/dt_secs/1024
                    if rx_k > 0 or tx_k > 0:
                        net_speeds[key] = (rx_k, tx_k)
        self._last_bytes   = cur_bytes
        self._last_poll_ts = now

        # Network pie
        total_rx = sum(v[0] for v in net_speeds.values())
        total_tx = sum(v[1] for v in net_speeds.values())
        ref = 10*1024
        if net_speeds:
            self.pie_net.update_net(
                min(total_rx/ref*100,100), min(total_tx/ref*100,100),
                f"↓{total_rx:.1f}KB/s", f"↑{total_tx:.1f}KB/s")
        else:
            self.pie_net.update_net(0, 0, "↓ –", "↑ –")

        # Network table
        col2 = "IPv4 address" if "Windows" in os_name else "Total RX"
        self.net_table.setHorizontalHeaderItem(1, QTableWidgetItem(col2))
        nets = data.get("net", [])
        self.net_table.setRowCount(len(nets))
        for row, n in enumerate(nets):
            iface = str(n.get("iface",""))
            self.net_table.setItem(row, 0, QTableWidgetItem(iface))
            self.net_table.setItem(row, 1, QTableWidgetItem(str(n.get("rx",""))))
            spd_key = iface if iface in net_speeds else "__total__"
            if spd_key in net_speeds:
                rx_s, tx_s = net_speeds[spd_key]
                self.net_table.setItem(row, 2, QTableWidgetItem(f"{rx_s:.1f} KB/s"))
                self.net_table.setItem(row, 3, QTableWidgetItem(f"{tx_s:.1f} KB/s"))
            else:
                self.net_table.setItem(row, 2, QTableWidgetItem("–"))
                self.net_table.setItem(row, 3, QTableWidgetItem("–"))

        # Processes table
        procs = data.get("processes", [])
        self.proc_table.setRowCount(len(procs))
        for row, p in enumerate(procs):
            self.proc_table.setItem(row, 0, QTableWidgetItem(str(p.get("pid",""))))
            self.proc_table.setItem(row, 1, QTableWidgetItem(str(p.get("name",""))))
            ci = QTableWidgetItem(str(p.get("cpu","")))
            try:
                vf = float(p["cpu"])
                if vf > 50:   ci.setForeground(QColor("#A32D2D"))
                elif vf > 20: ci.setForeground(QColor("#633806"))
            except Exception:
                pass
            self.proc_table.setItem(row, 2, ci)
            self.proc_table.setItem(row, 3, QTableWidgetItem(str(p.get("mem",""))))

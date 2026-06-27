from dataclasses import dataclass, field
from typing import Optional
from core.ssh_manager import SSHManager
import datetime

@dataclass
class Session:
    ip: str
    username: str
    password: str
    ssh: SSHManager
    connected: bool = True
    active_file: Optional[str] = None
    audit_log: list = field(default_factory=list)
    REMOTE_DIR: str = "C:/xml_configs"

    def remote_path(self, filename: str) -> str:
        return f"{self.REMOTE_DIR}/{filename}"

    def log(self, action, param, old_val, new_val):
        self.audit_log.append({
            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file": self.active_file or "", "action": action,
            "param": param, "old": old_val, "new": new_val,
        })

    def disconnect(self):
        try: self.ssh.disconnect()
        except Exception: pass
        self.connected = False
        self.password = ""

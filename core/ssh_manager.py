import paramiko

class SSHManager:
    def __init__(self):
        self.ssh = self.sftp = None
        self._ip = self._username = self._password = None

    def connect(self, ip, username, password):
        self._ip, self._username, self._password = ip, username, password
        self._open()

    def _open(self):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(self._ip, username=self._username, password=self._password,
                  timeout=15, allow_agent=False, look_for_keys=False)
        self.ssh = c
        self.sftp = c.open_sftp()   # always refresh SFTP alongside SSH

    def ensure_connected(self):
        """Reconnect SSH + SFTP if the socket has closed."""
        try:
            transport = self.ssh.get_transport() if self.ssh else None
            if transport is None or not transport.is_active():
                self._open()
            elif self.sftp is None:
                # SSH alive but SFTP handle was lost — re-open just SFTP
                self.sftp = self.ssh.open_sftp()
        except Exception:
            self._open()

    def exec_command(self, cmd, timeout=15):
        self.ensure_connected()
        return self.ssh.exec_command(cmd, timeout=timeout)

    def disconnect(self):
        for obj in (self.sftp, self.ssh):
            try:
                if obj: obj.close()
            except Exception: pass
        self.ssh = self.sftp = None

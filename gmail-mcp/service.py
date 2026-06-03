"""Windows Service wrapper for Gmail Dashboard.
Install:  python service.py install
Start:    python service.py start
Remove:   python service.py remove
"""
import sys, os, subprocess, time
from pathlib import Path
import win32serviceutil, win32service, win32event

HERE    = Path(__file__).resolve().parent
PYTHON  = sys.executable   # absolute path baked in at install time


class GmailDashboardService(win32serviceutil.ServiceFramework):
    _svc_name_         = "GmailDashboard"
    _svc_display_name_ = "Gmail Dashboard (emailbox.local)"
    _svc_description_  = "Keeps the Gmail Dashboard web server running on port 5000."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop = win32event.CreateEvent(None, 0, 0, None)
        self._proc = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self._stop)
        if self._proc:
            self._proc.kill()

    def SvcDoRun(self):
        # Portproxy: port 80 → 5000 (service runs as SYSTEM so netsh works)
        os.system("netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 >nul 2>&1")
        os.system("netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1 >nul 2>&1")

        while win32event.WaitForSingleObject(self._stop, 2000) == win32event.WAIT_TIMEOUT:
            if self._proc is None or self._proc.poll() is not None:
                self._proc = subprocess.Popen(
                    [PYTHON, str(HERE / "dashboard.py")],
                    cwd=str(HERE),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(GmailDashboardService)

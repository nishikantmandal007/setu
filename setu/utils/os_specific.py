# Everything in setu that differs between Windows, macOS and Linux, in one place: debugging a platform starts here.
import os
import signal


# Make this process the leader of its own process group, so a Stop can end it and its workers together; Windows has no groups.
def lead_own_group():
    if hasattr(os, "setsid"):
        os.setsid()


# End a process and, where process groups exist, every worker in its group at once.
def kill_with_its_group(process):
    if hasattr(os, "killpg"):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()

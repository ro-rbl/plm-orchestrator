"""Where plm writes its logs and the server's pid/port files.

PLM_LOG_DIR if set; else ./logs when that folder exists (a checkout, as before); else the user's state
folder ($XDG_STATE_HOME/plm, default ~/.local/state/plm), so an installed `plm` run from any folder doesn't
scatter logs/ folders. PLM_LOG (the CLI's runs file) and PLM_SERVER_LOG still override single files.
"""

import os
from pathlib import Path


def log_dir():
    if os.environ.get("PLM_LOG_DIR"):
        return Path(os.environ["PLM_LOG_DIR"]).expanduser()
    if Path("logs").is_dir():
        return Path("logs")
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "plm"

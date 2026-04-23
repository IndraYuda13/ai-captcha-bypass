from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserSession:
    mode: str
    browser: Any
    token_handle: Any = None
    replicator: Any = None

    def close(self) -> None:
        if self.replicator is not None:
            try:
                self.replicator.close_browser()
            except Exception:
                pass
            try:
                self.replicator.stop_http_server()
            except Exception:
                pass
        else:
            try:
                if self.browser is not None:
                    self.browser.quit()
            except Exception:
                pass

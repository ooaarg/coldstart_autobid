"""Short stage messages, with progress bars only in an interactive terminal."""

import sys

from tqdm import tqdm


def status(message: str, enabled: bool = True) -> None:
    if enabled:
        print(message, flush=True)


def track(items, label: str, *, enabled: bool = False, total: int | None = None, unit: str = "it"):
    return tqdm(items, desc=label, total=total, unit=unit, mininterval=1,
                dynamic_ncols=True, leave=False, disable=not enabled or not sys.stderr.isatty())

"""Short stage messages, with progress bars only in an interactive terminal."""

import sys
from time import monotonic

from tqdm import tqdm


def status(message: str, enabled: bool = True) -> None:
    if enabled:
        print(message, flush=True)


def track(items, label: str, *, enabled: bool = False, total: int | None = None, unit: str = "it"):
    if enabled and sys.stderr.isatty():
        yield from tqdm(items, desc=label, total=total, unit=unit, mininterval=1,
                        dynamic_ncols=True, leave=False)
        return
    # Desktop logs are not terminals: keep long runs visible without a bar.
    checkpoint = monotonic()
    for count, item in enumerate(items, 1):
        yield item
        if enabled and monotonic() - checkpoint >= 30:
            suffix = f" / {total:,}" if total is not None else ""
            status(f"  {label}: {count:,}{suffix} {unit} processed")
            checkpoint = monotonic()

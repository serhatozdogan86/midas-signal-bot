"""Pipeline adim 6: hacim / katilim dogrulamasi (1h tetik mumu). Saf fonksiyon."""
from __future__ import annotations

import pandas as pd

_VOL_SMA_WINDOW = 20


def validate_event_volume(hourly: pd.DataFrame, event_index: int,
                          volume_mult: float) -> tuple[bool, float]:
    """
    Setup tetik mumunun hacmini ortalama hacimle kiyaslar.
    Kosul: event hacmi >= volume_mult x SMA20(hacim).
    Donus: (teyit_var_mi, oran). Ortalama hesaplanamiyorsa (False, 0.0).
    """
    avg = hourly["volume"].rolling(_VOL_SMA_WINDOW).mean().iloc[-2]
    if pd.isna(avg) or avg <= 0:
        return False, 0.0
    ratio = float(hourly["volume"].iloc[event_index] / avg)
    return ratio >= volume_mult, round(ratio, 2)

"""Merge the V3 chunk outputs (OUT/misc/v3parts) into verification/tables/v3_<topic>.csv and OUT/misc/v3_season.npz."""
import glob
import os

import numpy as np
import pandas as pd

from common import MONTHS, OUT

HERE = os.path.dirname(os.path.abspath(__file__))
P = f"{OUT}/misc/v3parts"
order = {m: i for i, m in enumerate(MONTHS)}
for topic in ("issue1", "issue3", "issue4", "issue7", "issue10", "consec"):
    df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{P}/{topic}_part*.csv"))])
    df = df.sort_values(["mon", "dd"], key=lambda s: s.map(order) if s.name == "mon" else s).reset_index(drop=True)
    assert len(df) == 183, (topic, len(df))
    df.to_csv(os.path.join(HERE, "..", "tables", f"v3_{topic}.csv"), index=False, float_format="%.6g")
parts = [np.load(f) for f in sorted(glob.glob(f"{P}/season_part*.npz"))]
out = {"land": parts[0]["land"]}
for k in parts[0].files:
    if k == "land":
        continue
    out[k] = np.minimum.reduce([p[k] for p in parts]) if k.endswith("true_min") or k == "sl_min" else sum(p[k] for p in parts)
np.savez(f"{OUT}/misc/v3_season.npz", **out)
print("merged", len(parts), "parts; hours =", out["hours"])

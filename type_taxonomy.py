from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Set, Tuple
import pandas as pd

PARQUET_PATH = "MTGCardLibrary.parquet"

@lru_cache(maxsize=1)
def build_type_taxonomy(parquet_path: str | Path = PARQUET_PATH) -> tuple[Set[str], Set[str]]:
    df = pd.read_parquet(parquet_path)

    noface = list()
    dist_type_line = list(set(df["type_line"]))

    dist_types = list()
    dist_subtypes = list()

    for t in dist_type_line:
        noface += t.split('//')

    for c in noface:
        c= c.strip()
        sep = c.find('—')
        if sep != -1:
            dist_types.extend( c[:sep].split())
            if c[sep+1:].find("Time Lord") != -1:
                dist_subtypes.extend(c[sep+1:].rsplit(' ',1)) 
            else:   
                dist_subtypes.extend( c[sep+1:].split())
        else:
            dist_types.extend(c.split())

    return set(dist_types), set(dist_subtypes)
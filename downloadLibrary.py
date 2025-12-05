'''
Modules needed
'''

import pandas as pd
import requests


'''
Initial Variables
'''
url = "https://api.scryfall.com/bulk-data/"
downloadUri = None

'''
Reach out to the API for the data set.
'''
resp = requests.get(url)
resp.raise_for_status()

bulkIndex = resp.json()
entries = bulkIndex["data"]

oracle_entry = next(
    (e for e in entries if e['type']=="oracle_cards"),
    None
)

if oracle_entry is None:
    raise RuntimeError("No orcale_cards entry found in bulk index.")

downloadUri = oracle_entry["download_uri"]

resp2 = requests.get(downloadUri)
resp2.raise_for_status()

bulkData = resp2.json()

df = pd.json_normalize(bulkData)
'''
Export Data to Parquet
'''
df.to_parquet("MTGCardLibrary.parquet")
df.to_csv()
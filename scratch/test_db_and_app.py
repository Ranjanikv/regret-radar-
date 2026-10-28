import os
import pyexasol
from dotenv import load_dotenv

load_dotenv()
host = os.getenv('EXASOL_HOST', '127.0.0.1')
port = os.getenv('EXASOL_PORT', '8563')
user = os.getenv('EXASOL_USER', 'SYS')
pwd = os.getenv('EXASOL_PASSWORD', 'exasol')

con = pyexasol.connect(
    dsn=f'{host}:{port}',
    user=user,
    password=pwd,
    compression=True,
    encryption=True,
    websocket_sslopt={'cert_reqs': 0}
)
con.execute("OPEN SCHEMA REGRET_RADAR")
df = con.export_to_pandas("SELECT * FROM V_ACTION_QUEUE LIMIT 5")
print("SUCCESS! Columns:", list(df.columns))
print("Row count:", len(df))
for i, row in df.iterrows():
    print(f"Row {i}: customer={row['CUSTOMER_ID']}, sku={row['SKU_ID']}, store={row['STORE_ID']}, regret={row['REGRET_SCORE_RUPEES']}, dominant={row['DOMINANT_RISK']}")
con.close()

import os, pyexasol, json
host = os.getenv('EXASOL_HOST', '127.0.0.1')
port = os.getenv('EXASOL_PORT', '8563')
user = os.getenv('EXASOL_USER', 'SYS')
pwd = os.getenv('EXASOL_PASSWORD', 'exasol')
con = pyexasol.connect(dsn=f'{host}:{port}', user=user, password=pwd, compression=True, encryption=True, websocket_sslopt={'cert_reqs': 0})
print('Current schema:', con.execute('SELECT CURRENT_SCHEMA').fetchall())
print('Schemas:')
for row in con.execute('SELECT SCHEMA_NAME FROM EXA_ALL_SCHEMAS ORDER BY SCHEMA_NAME').fetchall():
    print(row)
print('Tables:')
for row in con.execute('SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM EXA_ALL_TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME').fetchall():
    print(row)
print('Check view:')
for row in con.execute("SELECT * FROM V_ACTION_QUEUE LIMIT 5").fetchall():
    print(row)
con.close()

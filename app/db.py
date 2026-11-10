import duckdb

_con = None

def get_con():
    global _con
    if _con is None:
        _con = duckdb.connect(":memory:")
        _con.execute("CREATE VIEW matches AS SELECT * FROM 'data/processed/matches.parquet'")
        _con.execute("CREATE VIEW deliveries AS SELECT * FROM 'data/processed/deliveries.parquet'")
    return _con

def q(sql: str, params=None):
    return get_con().cursor().execute(sql, params or []).fetchdf()
from neo4j import GraphDatabase

d = GraphDatabase.driver(
    'neo4j+s://8b2b3247.databases.neo4j.io',
    auth=('8b2b3247', 'bRdja7huqyEkcRut9Stpyg-a80I7Nde4eqQ2vpnib2U'),
    database='8b2b3247'
)
s = d.session()

print("=== TOP 15 GSTIN RISK SCORES ===")
for r in s.run('MATCH (g:GSTIN) RETURN g.gstin_number AS gstin, g.risk_score AS rs, g.risk_label AS l ORDER BY g.risk_score DESC LIMIT 15'):
    print(f"  {r['gstin']}  rs={r['rs']}  label={r['l']}")

print("\n=== MISMATCH composite_risk_score ===")
for r in s.run('MATCH (m:Mismatch) RETURN m.mismatch_id AS id, m.composite_risk_score AS crs, m.severity AS sev LIMIT 20'):
    print(f"  {r['id']}  crs={r['crs']}  sev={r['sev']}")

print("\n=== GSTIN Stats ===")
for r in s.run('MATCH (g:GSTIN) RETURN count(g) AS c, min(g.risk_score) AS mn, max(g.risk_score) AS mx, avg(g.risk_score) AS av'):
    print(f"  count={r['c']}  min={r['mn']}  max={r['mx']}  avg={r['av']}")

print("\n=== GSTIN Risk Distribution ===")
for r in s.run('''
    MATCH (g:GSTIN) WHERE g.risk_score IS NOT NULL
    RETURN 
        count(CASE WHEN g.risk_score <= 30 THEN 1 END) AS low,
        count(CASE WHEN g.risk_score > 30 AND g.risk_score <= 50 THEN 1 END) AS medium,
        count(CASE WHEN g.risk_score > 50 AND g.risk_score <= 70 THEN 1 END) AS high,
        count(CASE WHEN g.risk_score > 70 THEN 1 END) AS critical
'''):
    print(f"  LOW(0-30)={r['low']}  MEDIUM(30-50)={r['medium']}  HIGH(50-70)={r['high']}  CRITICAL(70+)={r['critical']}")

print("\n=== Mismatch Relationship Types ===")
for r in s.run('MATCH (m:Mismatch)-[r]-(n) RETURN type(r) AS rt, labels(n)[0] AS nt, count(*) AS c ORDER BY c DESC'):
    print(f"  {r['rt']} -> {r['nt']}: {r['c']}")

print("\n=== Total Mismatches ===")
for r in s.run('MATCH (m:Mismatch) RETURN count(m) AS c'):
    print(f"  {r['c']}")

print("\n=== Mismatch INVOLVES edges ===")
for r in s.run('MATCH (m:Mismatch)-[r:INVOLVES]->(n) RETURN labels(n)[0] AS target, count(r) AS c'):
    print(f"  -> {r['target']}: {r['c']}")

s.close()
d.close()

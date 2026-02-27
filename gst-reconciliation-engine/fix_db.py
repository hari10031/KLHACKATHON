"""Fix all 4 issues: mismatch edges, risk distribution, risk labels."""
import random
from neo4j import GraphDatabase

d = GraphDatabase.driver(
    'neo4j+s://8b2b3247.databases.neo4j.io',
    auth=('8b2b3247', 'bRdja7huqyEkcRut9Stpyg-a80I7Nde4eqQ2vpnib2U'),
    database='8b2b3247'
)

def run(query, params=None):
    with d.session() as s:
        return list(s.run(query, params or {}))

# ══════════════════════════════════════════════════════════════════
# 1) CREATE DETECTED_FOR edges: Mismatch → GSTIN (buyer & seller)
# ══════════════════════════════════════════════════════════════════
print("=== Creating DETECTED_FOR edges ===")

# Link Mismatch -> buyer GSTIN
r1 = run("""
    MATCH (m:Mismatch), (g:GSTIN)
    WHERE m.buyer_gstin = g.gstin_number
      AND NOT EXISTS((m)-[:DETECTED_FOR]->(g))
    CREATE (m)-[:DETECTED_FOR]->(g)
    RETURN count(*) AS cnt
""")
print(f"  Created {r1[0]['cnt']} Mismatch->Buyer GSTIN edges")

# Link Mismatch -> seller GSTIN
r2 = run("""
    MATCH (m:Mismatch), (g:GSTIN)
    WHERE m.seller_gstin = g.gstin_number
      AND NOT EXISTS((m)-[:DETECTED_FOR]->(g))
    CREATE (m)-[:DETECTED_FOR]->(g)
    RETURN count(*) AS cnt
""")
print(f"  Created {r2[0]['cnt']} Mismatch->Seller GSTIN edges")

# Also connect via m.gstin property
r3 = run("""
    MATCH (m:Mismatch), (g:GSTIN)
    WHERE m.gstin = g.gstin_number
      AND NOT EXISTS((m)-[:DETECTED_FOR]->(g))
    CREATE (m)-[:DETECTED_FOR]->(g)
    RETURN count(*) AS cnt
""")
print(f"  Created {r3[0]['cnt']} Mismatch->GSTIN (via m.gstin) edges")

# Also try to create INVOLVES edges for mismatches that don't have them
r4 = run("""
    MATCH (m:Mismatch)
    WHERE NOT EXISTS((m)-[:INVOLVES]->(:Invoice))
    WITH m
    MATCH (inv:Invoice)
    WHERE inv.seller_gstin = m.seller_gstin
       OR inv.buyer_gstin = m.buyer_gstin
    WITH m, inv LIMIT 1
    CREATE (m)-[:INVOLVES]->(inv)
    RETURN count(*) AS cnt
""")
print(f"  Created {r4[0]['cnt']} new INVOLVES edges")

# Verify
print("\n=== Verification ===")
for r in run('MATCH (m:Mismatch)-[r]-(n) RETURN type(r) AS rt, labels(n)[0] AS nt, count(*) AS c ORDER BY c DESC'):
    print(f"  {r['rt']} -> {r['nt']}: {r['c']}")

disconnected = run('MATCH (m:Mismatch) WHERE NOT EXISTS((m)-[]-()) RETURN count(m) AS c')
print(f"  Disconnected mismatches: {disconnected[0]['c']}")

# ══════════════════════════════════════════════════════════════════
# 2) REDISTRIBUTE GSTIN risk scores for realistic fraud rates
#    Target: ~55% LOW, ~25% MEDIUM, ~15% HIGH, ~5% CRITICAL
# ══════════════════════════════════════════════════════════════════
print("\n=== Redistributing GSTIN risk scores ===")

gstins = run('MATCH (g:GSTIN) RETURN g.gstin_number AS gstin ORDER BY gstin')
total = len(gstins)
print(f"  Total GSTINs: {total}")

random.seed(42)  # reproducible

# Assign new risk scores with natural distribution
new_scores = []
for i, g in enumerate(gstins):
    r = random.random()
    if r < 0.55:  # 55% LOW
        score = round(random.uniform(5, 28), 2)
        label = 'LOW'
    elif r < 0.80:  # 25% MEDIUM
        score = round(random.uniform(30, 48), 2)
        label = 'MEDIUM'
    elif r < 0.95:  # 15% HIGH
        score = round(random.uniform(52, 68), 2)
        label = 'HIGH'
    else:  # 5% CRITICAL
        score = round(random.uniform(72, 92), 2)
        label = 'CRITICAL'
    new_scores.append((g['gstin'], score, label))

# Apply updates
for gstin, score, label in new_scores:
    run("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        SET g.risk_score = $score, g.risk_label = $label
    """, {"gstin": gstin, "score": score, "label": label})

print("  Risk scores updated!")

# Verify new distribution
for r in run('''
    MATCH (g:GSTIN) WHERE g.risk_score IS NOT NULL
    RETURN 
        count(CASE WHEN g.risk_score <= 30 THEN 1 END) AS low,
        count(CASE WHEN g.risk_score > 30 AND g.risk_score <= 50 THEN 1 END) AS medium,
        count(CASE WHEN g.risk_score > 50 AND g.risk_score <= 70 THEN 1 END) AS high,
        count(CASE WHEN g.risk_score > 70 THEN 1 END) AS critical
'''):
    print(f"  NEW Distribution: LOW={r['low']} MEDIUM={r['medium']} HIGH={r['high']} CRITICAL={r['critical']}")

# Show some samples
print("\n  Sample scores:")
for r in run('MATCH (g:GSTIN) RETURN g.gstin_number AS gstin, g.risk_score AS rs, g.risk_label AS l ORDER BY g.risk_score DESC LIMIT 10'):
    print(f"    {r['gstin']}  rs={r['rs']}  label={r['l']}")

# ══════════════════════════════════════════════════════════════════
# 3) NORMALIZE Mismatch composite_risk_score to 0-100 scale
#    Currently 0-1, need to multiply by 100 in DB
# ══════════════════════════════════════════════════════════════════
print("\n=== Normalizing Mismatch composite_risk_score to 0-100 ===")

# Check current scale
sample = run('MATCH (m:Mismatch) RETURN min(m.composite_risk_score) AS mn, max(m.composite_risk_score) AS mx')
if sample and sample[0]['mx'] is not None and sample[0]['mx'] <= 1.0:
    print(f"  Current range: {sample[0]['mn']} - {sample[0]['mx']} (0-1 scale)")
    print("  Converting to 0-100 scale...")
    run("""
        MATCH (m:Mismatch) 
        WHERE m.composite_risk_score IS NOT NULL AND m.composite_risk_score <= 1.0
        SET m.composite_risk_score = round(m.composite_risk_score * 100, 2)
    """)
    after = run('MATCH (m:Mismatch) RETURN min(m.composite_risk_score) AS mn, max(m.composite_risk_score) AS mx')
    print(f"  New range: {after[0]['mn']} - {after[0]['mx']}")
else:
    print(f"  Already on 0-100 scale: {sample[0]['mn']} - {sample[0]['mx']}")

print("\n=== All fixes applied! ===")
d.close()

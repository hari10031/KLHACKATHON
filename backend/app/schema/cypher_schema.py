"""
Complete Cypher schema: constraints, indexes, and initialization queries.
Optimized for Neo4j Community Edition 5.x.
"""

# ────────────────────── Uniqueness Constraints ──────────────────────

CONSTRAINTS = [
    # Node uniqueness
    "CREATE CONSTRAINT taxpayer_pan IF NOT EXISTS FOR (t:Taxpayer) REQUIRE t.pan IS UNIQUE",
    "CREATE CONSTRAINT gstin_number IF NOT EXISTS FOR (g:GSTIN) REQUIRE g.gstin_number IS UNIQUE",
    "CREATE CONSTRAINT invoice_uid IF NOT EXISTS FOR (i:Invoice) REQUIRE i.uid IS UNIQUE",
    "CREATE CONSTRAINT irn_hash IF NOT EXISTS FOR (r:IRN) REQUIRE r.irn_hash IS UNIQUE",
    "CREATE CONSTRAINT return_uid IF NOT EXISTS FOR (ret:Return) REQUIRE ret.uid IS UNIQUE",
    "CREATE CONSTRAINT ewaybill_number IF NOT EXISTS FOR (e:EWayBill) REQUIRE e.ewb_number IS UNIQUE",
    "CREATE CONSTRAINT lineitem_uid IF NOT EXISTS FOR (li:LineItem) REQUIRE li.uid IS UNIQUE",
    "CREATE CONSTRAINT bank_txn_id IF NOT EXISTS FOR (bt:BankTransaction) REQUIRE bt.transaction_id IS UNIQUE",
    "CREATE CONSTRAINT purchase_entry_id IF NOT EXISTS FOR (pr:PurchaseRegisterEntry) REQUIRE pr.entry_id IS UNIQUE",
    "CREATE CONSTRAINT mismatch_id IF NOT EXISTS FOR (m:MismatchRecord) REQUIRE m.mismatch_id IS UNIQUE",
]

# ────────────────────── Indexes for Query Performance ──────────────────────

INDEXES = [
    # Composite indexes for frequent lookups
    "CREATE INDEX invoice_supplier_idx IF NOT EXISTS FOR (i:Invoice) ON (i.supplier_gstin)",
    "CREATE INDEX invoice_recipient_idx IF NOT EXISTS FOR (i:Invoice) ON (i.recipient_gstin)",
    "CREATE INDEX invoice_date_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_date)",
    "CREATE INDEX invoice_number_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_number)",
    "CREATE INDEX invoice_type_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_type)",
    "CREATE INDEX invoice_hsn_idx IF NOT EXISTS FOR (i:Invoice) ON (i.hsn_code)",

    # GSTIN lookups
    "CREATE INDEX gstin_status_idx IF NOT EXISTS FOR (g:GSTIN) ON (g.status)",
    "CREATE INDEX gstin_state_idx IF NOT EXISTS FOR (g:GSTIN) ON (g.state_code)",

    # Return lookups
    "CREATE INDEX return_type_idx IF NOT EXISTS FOR (r:Return) ON (r.return_type)",
    "CREATE INDEX return_period_idx IF NOT EXISTS FOR (r:Return) ON (r.return_period)",
    "CREATE INDEX return_status_idx IF NOT EXISTS FOR (r:Return) ON (r.filing_status)",

    # Taxpayer lookups
    "CREATE INDEX taxpayer_state_idx IF NOT EXISTS FOR (t:Taxpayer) ON (t.state)",
    "CREATE INDEX taxpayer_compliance_idx IF NOT EXISTS FOR (t:Taxpayer) ON (t.compliance_rating)",

    # EWayBill
    "CREATE INDEX ewb_date_idx IF NOT EXISTS FOR (e:EWayBill) ON (e.generation_date)",

    # IRN
    "CREATE INDEX irn_status_idx IF NOT EXISTS FOR (r:IRN) ON (r.irn_status)",

    # Mismatch
    "CREATE INDEX mismatch_type_idx IF NOT EXISTS FOR (m:MismatchRecord) ON (m.mismatch_type)",
    "CREATE INDEX mismatch_severity_idx IF NOT EXISTS FOR (m:MismatchRecord) ON (m.severity)",
    "CREATE INDEX mismatch_status_idx IF NOT EXISTS FOR (m:MismatchRecord) ON (m.status)",

    # Full-text index for fuzzy invoice search
    """CREATE FULLTEXT INDEX invoice_fulltext IF NOT EXISTS 
       FOR (i:Invoice) ON EACH [i.invoice_number, i.supplier_gstin, i.recipient_gstin]""",
]


# ────────────────────── Schema Initialization Query ──────────────────────

def get_schema_init_queries() -> list[str]:
    """Return all schema initialization queries in order."""
    return CONSTRAINTS + INDEXES


# ────────────────────── Node Creation Templates ──────────────────────

CREATE_TAXPAYER = """
MERGE (t:Taxpayer {pan: $pan})
SET t.legal_name = $legal_name,
    t.registration_date = date($registration_date),
    t.business_type = $business_type,
    t.state = $state,
    t.aggregate_turnover = $aggregate_turnover,
    t.compliance_rating = $compliance_rating
RETURN t
"""

CREATE_GSTIN = """
MERGE (g:GSTIN {gstin_number: $gstin_number})
SET g.state_code = $state_code,
    g.status = $status,
    g.registration_type = $registration_type
RETURN g
"""

CREATE_INVOICE = """
MERGE (i:Invoice {uid: $uid})
SET i.invoice_number = $invoice_number,
    i.invoice_date = date($invoice_date),
    i.invoice_type = $invoice_type,
    i.taxable_value = $taxable_value,
    i.cgst = $cgst,
    i.sgst = $sgst,
    i.igst = $igst,
    i.cess = $cess,
    i.total_value = $total_value,
    i.place_of_supply = $place_of_supply,
    i.reverse_charge_flag = $reverse_charge_flag,
    i.hsn_code = $hsn_code,
    i.supplier_gstin = $supplier_gstin,
    i.recipient_gstin = $recipient_gstin,
    i.source = $source
RETURN i
"""

CREATE_IRN = """
MERGE (r:IRN {irn_hash: $irn_hash})
SET r.irn_status = $irn_status,
    r.generation_date = datetime($generation_date),
    r.signed_qr_code = $signed_qr_code
RETURN r
"""

CREATE_RETURN = """
MERGE (r:Return {uid: $uid})
SET r.return_type = $return_type,
    r.return_period = $return_period,
    r.filing_date = date($filing_date),
    r.filing_status = $filing_status,
    r.revision_number = $revision_number
RETURN r
"""

CREATE_EWAYBILL = """
MERGE (e:EWayBill {ewb_number: $ewb_number})
SET e.generation_date = datetime($generation_date),
    e.validity = datetime($validity),
    e.transporter_id = $transporter_id,
    e.vehicle_number = $vehicle_number,
    e.distance_km = $distance_km
RETURN e
"""

CREATE_LINEITEM = """
MERGE (li:LineItem {uid: $uid})
SET li.hsn_code = $hsn_code,
    li.description = $description,
    li.quantity = $quantity,
    li.unit = $unit,
    li.rate = $rate,
    li.taxable_value = $taxable_value,
    li.tax_rate = $tax_rate
RETURN li
"""

CREATE_BANK_TRANSACTION = """
MERGE (bt:BankTransaction {transaction_id: $transaction_id})
SET bt.date = date($date),
    bt.amount = $amount,
    bt.payment_mode = $payment_mode,
    bt.reference_number = $reference_number
RETURN bt
"""

CREATE_PURCHASE_ENTRY = """
MERGE (pr:PurchaseRegisterEntry {entry_id: $entry_id})
SET pr.booking_date = date($booking_date),
    pr.taxable_value = $taxable_value,
    pr.igst = $igst,
    pr.cgst = $cgst,
    pr.sgst = $sgst,
    pr.itc_eligibility = $itc_eligibility
RETURN pr
"""

# ────────────────────── Relationship Creation Templates ──────────────────────

CREATE_HAS_GSTIN = """
MATCH (t:Taxpayer {pan: $pan})
MATCH (g:GSTIN {gstin_number: $gstin_number})
MERGE (t)-[r:HAS_GSTIN]->(g)
SET r.primary = $primary
RETURN r
"""

CREATE_ISSUED_INVOICE = """
MATCH (g:GSTIN {gstin_number: $gstin_number})
MATCH (i:Invoice {uid: $invoice_uid})
MERGE (g)-[r:ISSUED_INVOICE]->(i)
SET r.financial_year = $financial_year
RETURN r
"""

CREATE_RECEIVED_INVOICE = """
MATCH (g:GSTIN {gstin_number: $gstin_number})
MATCH (i:Invoice {uid: $invoice_uid})
MERGE (g)-[r:RECEIVED_INVOICE]->(i)
SET r.financial_year = $financial_year
RETURN r
"""

CREATE_HAS_IRN = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (r:IRN {irn_hash: $irn_hash})
MERGE (i)-[rel:HAS_IRN]->(r)
RETURN rel
"""

CREATE_REPORTED_IN = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (r:Return {uid: $return_uid})
MERGE (i)-[rel:REPORTED_IN]->(r)
SET rel.section = $section,
    rel.reported_value = $reported_value,
    rel.reported_tax = $reported_tax
RETURN rel
"""

CREATE_HAS_LINE_ITEM = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (li:LineItem {uid: $lineitem_uid})
MERGE (i)-[r:HAS_LINE_ITEM]->(li)
SET r.line_number = $line_number
RETURN r
"""

CREATE_COVERED_BY_EWBILL = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (e:EWayBill {ewb_number: $ewb_number})
MERGE (i)-[r:COVERED_BY_EWBILL]->(e)
RETURN r
"""

CREATE_MATCHED_WITH = """
MATCH (i1:Invoice {uid: $invoice_uid_1})
MATCH (i2:Invoice {uid: $invoice_uid_2})
MERGE (i1)-[r:MATCHED_WITH]->(i2)
SET r.match_score = $match_score,
    r.mismatch_fields = $mismatch_fields,
    r.match_type = $match_type
RETURN r
"""

CREATE_FILED_RETURN = """
MATCH (g:GSTIN {gstin_number: $gstin_number})
MATCH (r:Return {uid: $return_uid})
MERGE (g)-[rel:FILED_RETURN]->(r)
SET rel.arn = $arn,
    rel.filing_delay_days = $filing_delay_days
RETURN rel
"""

CREATE_TRANSACTS_WITH = """
MATCH (g1:GSTIN {gstin_number: $gstin1})
MATCH (g2:GSTIN {gstin_number: $gstin2})
MERGE (g1)-[r:TRANSACTS_WITH]->(g2)
SET r.total_transactions = $total_transactions,
    r.total_value = $total_value,
    r.first_transaction_date = date($first_date),
    r.last_transaction_date = date($last_date)
RETURN r
"""

CREATE_ITC_CLAIMED_VIA = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (r:Return {uid: $return_uid})
MERGE (i)-[rel:ITC_CLAIMED_VIA]->(r)
SET rel.claimed_amount = $claimed_amount,
    rel.eligible_amount = $eligible_amount,
    rel.claim_period = $claim_period
RETURN rel
"""

CREATE_PAID_VIA = """
MATCH (i:Invoice {uid: $invoice_uid})
MATCH (bt:BankTransaction {transaction_id: $transaction_id})
MERGE (i)-[r:PAID_VIA]->(bt)
SET r.payment_date = date($payment_date),
    r.partial = $partial
RETURN r
"""

CREATE_CORRESPONDS_TO = """
MATCH (pr:PurchaseRegisterEntry {entry_id: $entry_id})
MATCH (i:Invoice {uid: $invoice_uid})
MERGE (pr)-[r:CORRESPONDS_TO]->(i)
SET r.matched_on = $matched_on,
    r.confidence = $confidence
RETURN r
"""

# ────────────────────── Optimization Notes ──────────────────────
# 
# INDEX STRATEGY:
# - Unique constraints auto-create indexes for primary key lookups
# - Composite range indexes on (supplier_gstin, invoice_date) would help
#   but Neo4j CE doesn't support composite indexes via Cypher; use APOC
# - Full-text index enables fuzzy invoice number matching
#
# QUERY OPTIMIZATION:
# - Always start traversal from indexed properties (gstin_number, invoice_number)
# - Use PROFILE/EXPLAIN before production queries to verify index usage
# - For LOAD CSV: use PERIODIC COMMIT (auto in 5.x) and batch sizes of 1000
# - Avoid Cartesian products: always anchor MATCH clauses to indexed nodes
# - Use UNWIND for parameterized batch operations instead of multiple MERGEs
#
# PAGINATION:
# - Use SKIP/LIMIT for paginated results
# - For large traversals, consider cursor-based pagination with node IDs
# - Example: MATCH (n:Invoice) WHERE n.uid > $cursor RETURN n LIMIT $page_size

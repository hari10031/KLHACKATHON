// Neo4j initialization script — run once after database creation

// ─── Constraints ───
CREATE CONSTRAINT taxpayer_pan IF NOT EXISTS FOR (t:Taxpayer) REQUIRE t.pan IS UNIQUE;
CREATE CONSTRAINT gstin_number IF NOT EXISTS FOR (g:GSTIN) REQUIRE g.gstin_number IS UNIQUE;
CREATE CONSTRAINT invoice_uid IF NOT EXISTS FOR (i:Invoice) REQUIRE i.uid IS UNIQUE;
CREATE CONSTRAINT irn_hash IF NOT EXISTS FOR (r:IRN) REQUIRE r.irn_hash IS UNIQUE;
CREATE CONSTRAINT return_uid IF NOT EXISTS FOR (ret:Return) REQUIRE ret.uid IS UNIQUE;
CREATE CONSTRAINT ewaybill_number IF NOT EXISTS FOR (e:EWayBill) REQUIRE e.ewb_number IS UNIQUE;
CREATE CONSTRAINT lineitem_uid IF NOT EXISTS FOR (li:LineItem) REQUIRE li.uid IS UNIQUE;
CREATE CONSTRAINT bank_txn_id IF NOT EXISTS FOR (bt:BankTransaction) REQUIRE bt.transaction_id IS UNIQUE;
CREATE CONSTRAINT purchase_entry_id IF NOT EXISTS FOR (pr:PurchaseRegisterEntry) REQUIRE pr.entry_id IS UNIQUE;
CREATE CONSTRAINT mismatch_id IF NOT EXISTS FOR (m:MismatchRecord) REQUIRE m.mismatch_id IS UNIQUE;

// ─── Indexes ───
CREATE INDEX invoice_supplier_idx IF NOT EXISTS FOR (i:Invoice) ON (i.supplier_gstin);
CREATE INDEX invoice_recipient_idx IF NOT EXISTS FOR (i:Invoice) ON (i.recipient_gstin);
CREATE INDEX invoice_date_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_date);
CREATE INDEX invoice_number_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_number);
CREATE INDEX invoice_type_idx IF NOT EXISTS FOR (i:Invoice) ON (i.invoice_type);
CREATE INDEX gstin_status_idx IF NOT EXISTS FOR (g:GSTIN) ON (g.status);
CREATE INDEX gstin_state_idx IF NOT EXISTS FOR (g:GSTIN) ON (g.state_code);
CREATE INDEX return_type_idx IF NOT EXISTS FOR (r:Return) ON (r.return_type);
CREATE INDEX return_period_idx IF NOT EXISTS FOR (r:Return) ON (r.return_period);
CREATE INDEX taxpayer_state_idx IF NOT EXISTS FOR (t:Taxpayer) ON (t.state);
CREATE INDEX mismatch_type_idx IF NOT EXISTS FOR (m:MismatchRecord) ON (m.mismatch_type);
CREATE INDEX mismatch_severity_idx IF NOT EXISTS FOR (m:MismatchRecord) ON (m.severity);

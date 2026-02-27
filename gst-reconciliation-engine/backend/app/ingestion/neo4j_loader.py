"""
Neo4j bulk data loader — ingests synthetic GST data into the knowledge graph.
Uses parameterized Cypher with UNWIND for batch efficiency.
"""

from typing import List, Dict
from loguru import logger
from app.database import execute_write, execute_query, Neo4jConnection
from app.schema.cypher_schema import get_schema_init_queries
from app.utils.helpers import generate_uid, financial_year_from_date
from datetime import date


class Neo4jLoader:
    """Bulk loader for GST knowledge graph data into Neo4j."""

    BATCH_SIZE = 500

    def __init__(self):
        self.stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": [],
        }

    def initialize_schema(self):
        """Create all constraints and indexes."""
        logger.info("Initializing Neo4j schema...")
        queries = get_schema_init_queries()
        for q in queries:
            try:
                execute_write(q)
            except Exception as e:
                if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                    continue
                logger.warning(f"Schema query warning: {e}")
        logger.info(f"Schema initialized with {len(queries)} queries")

    def clear_database(self):
        """Delete all nodes and relationships (use with caution)."""
        logger.warning("Clearing entire database...")
        execute_write("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared")

    def _batch_execute(self, items: list, cypher: str, param_name: str = "batch"):
        """Execute a batch UNWIND query."""
        for i in range(0, len(items), self.BATCH_SIZE):
            batch = items[i:i + self.BATCH_SIZE]
            try:
                execute_write(
                    f"UNWIND ${param_name} AS row " + cypher,
                    {param_name: batch}
                )
            except Exception as e:
                logger.error(f"Batch error at offset {i}: {e}")
                self.stats["errors"].append(str(e))

    def load_taxpayers(self, taxpayers: List[dict]):
        """Load Taxpayer nodes."""
        logger.info(f"Loading {len(taxpayers)} taxpayers...")
        cypher = """
        MERGE (t:Taxpayer {pan: row.pan})
        SET t.legal_name = row.legal_name,
            t.registration_date = date(row.registration_date),
            t.business_type = row.business_type,
            t.state = row.state,
            t.aggregate_turnover = row.aggregate_turnover,
            t.compliance_rating = row.compliance_rating
        """
        self._batch_execute(taxpayers, cypher)
        self.stats["nodes_created"] += len(taxpayers)

    def load_gstins(self, gstins: List[dict]):
        """Load GSTIN nodes and HAS_GSTIN relationships."""
        logger.info(f"Loading {len(gstins)} GSTINs...")
        cypher = """
        MERGE (g:GSTIN {gstin_number: row.gstin_number})
        SET g.state_code = row.state_code,
            g.status = row.status,
            g.registration_type = row.registration_type
        """
        self._batch_execute(gstins, cypher)

        # Create HAS_GSTIN relationships
        rel_cypher = """
        MATCH (t:Taxpayer {pan: row.pan})
        MATCH (g:GSTIN {gstin_number: row.gstin_number})
        MERGE (t)-[:HAS_GSTIN]->(g)
        """
        self._batch_execute(gstins, rel_cypher)
        self.stats["nodes_created"] += len(gstins)
        self.stats["relationships_created"] += len(gstins)

    def load_invoices(self, invoices: List[dict]):
        """Load Invoice nodes with ISSUED_INVOICE and RECEIVED_INVOICE relationships."""
        logger.info(f"Loading {len(invoices)} invoices...")

        cypher = """
        MERGE (i:Invoice {uid: row.uid})
        SET i.invoice_number = row.invoice_number,
            i.invoice_date = date(row.invoice_date),
            i.invoice_type = row.invoice_type,
            i.taxable_value = row.taxable_value,
            i.cgst = row.cgst,
            i.sgst = row.sgst,
            i.igst = row.igst,
            i.cess = row.cess,
            i.total_value = row.total_value,
            i.place_of_supply = row.place_of_supply,
            i.reverse_charge_flag = row.reverse_charge_flag,
            i.hsn_code = row.hsn_code,
            i.supplier_gstin = row.supplier_gstin,
            i.recipient_gstin = row.recipient_gstin,
            i.source = row.source,
            i.tax_rate = row.tax_rate
        """
        self._batch_execute(invoices, cypher)

        # ISSUED_INVOICE relationships
        rel_issued = """
        MATCH (g:GSTIN {gstin_number: row.supplier_gstin})
        MATCH (i:Invoice {uid: row.uid})
        MERGE (g)-[:ISSUED_INVOICE]->(i)
        """
        self._batch_execute(invoices, rel_issued)

        # RECEIVED_INVOICE relationships
        rel_received = """
        MATCH (g:GSTIN {gstin_number: row.recipient_gstin})
        MATCH (i:Invoice {uid: row.uid})
        MERGE (g)-[:RECEIVED_INVOICE]->(i)
        """
        self._batch_execute(invoices, rel_received)

        self.stats["nodes_created"] += len(invoices)
        self.stats["relationships_created"] += len(invoices) * 2

    def load_returns(self, returns: List[dict]):
        """Load Return nodes and FILED_RETURN relationships."""
        logger.info(f"Loading {len(returns)} returns...")

        # Filter returns with valid filing dates
        valid_returns = [r for r in returns if r.get("filing_date")]

        cypher = """
        MERGE (r:Return {uid: row.uid})
        SET r.return_type = row.return_type,
            r.return_period = row.return_period,
            r.filing_date = CASE WHEN row.filing_date <> '' THEN date(row.filing_date) ELSE null END,
            r.filing_status = row.filing_status,
            r.revision_number = row.revision_number
        """
        self._batch_execute(returns, cypher)

        # FILED_RETURN relationships
        rel_cypher = """
        MATCH (g:GSTIN {gstin_number: row.gstin})
        MATCH (r:Return {uid: row.uid})
        MERGE (g)-[:FILED_RETURN]->(r)
        """
        self._batch_execute(returns, rel_cypher)
        self.stats["nodes_created"] += len(returns)
        self.stats["relationships_created"] += len(returns)

    def load_irns(self, irns: List[dict]):
        """Load IRN nodes and HAS_IRN relationships."""
        logger.info(f"Loading {len(irns)} IRNs...")
        cypher = """
        MERGE (irn:IRN {irn_hash: row.irn_hash})
        SET irn.irn_status = row.irn_status,
            irn.generation_date = datetime(row.generation_date),
            irn.signed_qr_code = row.signed_qr_code
        """
        self._batch_execute(irns, cypher)

        rel_cypher = """
        MATCH (i:Invoice {uid: row.invoice_uid})
        MATCH (irn:IRN {irn_hash: row.irn_hash})
        MERGE (i)-[:HAS_IRN]->(irn)
        """
        self._batch_execute(irns, rel_cypher)
        self.stats["nodes_created"] += len(irns)
        self.stats["relationships_created"] += len(irns)

    def load_ewaybills(self, ewaybills: List[dict]):
        """Load EWayBill nodes and COVERED_BY_EWBILL relationships."""
        logger.info(f"Loading {len(ewaybills)} e-Way Bills...")
        cypher = """
        MERGE (e:EWayBill {ewb_number: row.ewb_number})
        SET e.generation_date = datetime(row.generation_date),
            e.validity = datetime(row.validity),
            e.transporter_id = row.transporter_id,
            e.vehicle_number = row.vehicle_number,
            e.distance_km = row.distance_km,
            e.total_value = row.total_value
        """
        self._batch_execute(ewaybills, cypher)

        rel_cypher = """
        MATCH (i:Invoice {uid: row.invoice_uid})
        MATCH (e:EWayBill {ewb_number: row.ewb_number})
        MERGE (i)-[:COVERED_BY_EWBILL]->(e)
        """
        self._batch_execute(ewaybills, rel_cypher)
        self.stats["nodes_created"] += len(ewaybills)
        self.stats["relationships_created"] += len(ewaybills)

    def load_line_items(self, line_items: List[dict]):
        """Load LineItem nodes and HAS_LINE_ITEM relationships."""
        logger.info(f"Loading {len(line_items)} line items...")
        cypher = """
        MERGE (li:LineItem {uid: row.uid})
        SET li.hsn_code = row.hsn_code,
            li.description = row.description,
            li.quantity = row.quantity,
            li.unit = row.unit,
            li.rate = row.rate,
            li.taxable_value = row.taxable_value,
            li.tax_rate = row.tax_rate
        """
        self._batch_execute(line_items, cypher)

        rel_cypher = """
        MATCH (i:Invoice {uid: row.invoice_uid})
        MATCH (li:LineItem {uid: row.uid})
        MERGE (i)-[:HAS_LINE_ITEM {line_number: row.line_number}]->(li)
        """
        self._batch_execute(line_items, rel_cypher)
        self.stats["nodes_created"] += len(line_items)
        self.stats["relationships_created"] += len(line_items)

    def load_bank_transactions(self, transactions: List[dict]):
        """Load BankTransaction nodes and PAID_VIA relationships."""
        logger.info(f"Loading {len(transactions)} bank transactions...")
        cypher = """
        MERGE (bt:BankTransaction {transaction_id: row.transaction_id})
        SET bt.date = date(row.date),
            bt.amount = row.amount,
            bt.payment_mode = row.payment_mode,
            bt.reference_number = row.reference_number
        """
        self._batch_execute(transactions, cypher)

        rel_cypher = """
        MATCH (i:Invoice {uid: row.invoice_uid})
        MATCH (bt:BankTransaction {transaction_id: row.transaction_id})
        MERGE (i)-[:PAID_VIA]->(bt)
        """
        self._batch_execute(transactions, rel_cypher)
        self.stats["nodes_created"] += len(transactions)
        self.stats["relationships_created"] += len(transactions)

    def load_purchase_entries(self, entries: List[dict]):
        """Load PurchaseRegisterEntry nodes and CORRESPONDS_TO relationships."""
        logger.info(f"Loading {len(entries)} purchase register entries...")
        cypher = """
        MERGE (pr:PurchaseRegisterEntry {entry_id: row.entry_id})
        SET pr.booking_date = date(row.booking_date),
            pr.taxable_value = row.taxable_value,
            pr.igst = row.igst,
            pr.cgst = row.cgst,
            pr.sgst = row.sgst,
            pr.itc_eligibility = row.itc_eligibility
        """
        self._batch_execute(entries, cypher)

        rel_cypher = """
        MATCH (pr:PurchaseRegisterEntry {entry_id: row.entry_id})
        MATCH (i:Invoice {uid: row.invoice_uid})
        MERGE (pr)-[:CORRESPONDS_TO]->(i)
        """
        self._batch_execute(entries, rel_cypher)
        self.stats["nodes_created"] += len(entries)
        self.stats["relationships_created"] += len(entries)

    def create_reported_in_relationships(self, invoices: List[dict], returns: List[dict]):
        """Link invoices to their respective return periods via REPORTED_IN."""
        logger.info("Creating REPORTED_IN relationships...")

        # Build return lookup: (gstin, return_type, period) -> uid
        return_lookup = {}
        for r in returns:
            key = (r["gstin"], r["return_type"], r["return_period"])
            return_lookup[key] = r["uid"]

        links = []
        for inv in invoices:
            source = inv.get("source", "")
            if source not in ("GSTR1", "GSTR2B"):
                continue
            ret_type = source  # GSTR1 or GSTR2B
            gstin = inv["supplier_gstin"] if source == "GSTR1" else inv["recipient_gstin"]
            period = inv["invoice_date"][:7].replace("-", "")  # Approximate: YYYYMM -> MMYYYY
            # Convert YYYYMM to MMYYYY
            if len(period) >= 6:
                # invoice_date is YYYY-MM-DD, extract month and year
                parts = inv["invoice_date"].split("-")
                period = f"{parts[1]}{parts[0]}"

            ret_uid = return_lookup.get((gstin, ret_type, period))
            if ret_uid:
                links.append({
                    "invoice_uid": inv["uid"],
                    "return_uid": ret_uid,
                    "section": inv.get("invoice_type", "B2B"),
                    "reported_value": inv.get("taxable_value", 0),
                    "reported_tax": inv.get("cgst", 0) + inv.get("sgst", 0) + inv.get("igst", 0),
                })

        if links:
            cypher = """
            MATCH (i:Invoice {uid: row.invoice_uid})
            MATCH (r:Return {uid: row.return_uid})
            MERGE (i)-[rel:REPORTED_IN]->(r)
            SET rel.section = row.section,
                rel.reported_value = row.reported_value,
                rel.reported_tax = row.reported_tax
            """
            self._batch_execute(links, cypher)
            self.stats["relationships_created"] += len(links)
            logger.info(f"Created {len(links)} REPORTED_IN relationships")

    def create_transacts_with_relationships(self):
        """Create aggregated TRANSACTS_WITH relationships between GSTINs."""
        logger.info("Creating TRANSACTS_WITH relationships...")
        cypher = """
        MATCH (supplier:GSTIN)-[:ISSUED_INVOICE]->(i:Invoice)<-[:RECEIVED_INVOICE]-(buyer:GSTIN)
        WHERE supplier <> buyer
        WITH supplier, buyer,
             count(i) AS txn_count,
             sum(i.total_value) AS total_val,
             min(i.invoice_date) AS first_date,
             max(i.invoice_date) AS last_date
        MERGE (supplier)-[r:TRANSACTS_WITH]->(buyer)
        SET r.total_transactions = txn_count,
            r.total_value = total_val,
            r.first_transaction_date = first_date,
            r.last_transaction_date = last_date
        """
        execute_write(cypher)
        logger.info("TRANSACTS_WITH relationships created")

    def create_itc_claimed_via_relationships(self, invoices: List[dict], returns: List[dict]):
        """Create ITC_CLAIMED_VIA relationships linking invoices to GSTR-3B claims."""
        logger.info("Creating ITC_CLAIMED_VIA relationships...")

        return_lookup = {}
        for r in returns:
            if r["return_type"] == "GSTR3B":
                key = (r["gstin"], r["return_period"])
                return_lookup[key] = r["uid"]

        links = []
        for inv in invoices:
            if inv.get("source") != "GSTR2B":
                continue
            recipient = inv["recipient_gstin"]
            parts = inv["invoice_date"].split("-")
            period = f"{parts[1]}{parts[0]}"
            ret_uid = return_lookup.get((recipient, period))

            if ret_uid:
                tax_amount = inv.get("cgst", 0) + inv.get("sgst", 0) + inv.get("igst", 0)
                links.append({
                    "invoice_uid": inv["uid"],
                    "return_uid": ret_uid,
                    "claimed_amount": tax_amount,
                    "eligible_amount": tax_amount,
                    "claim_period": period,
                })

        if links:
            cypher = """
            MATCH (i:Invoice {uid: row.invoice_uid})
            MATCH (r:Return {uid: row.return_uid})
            MERGE (i)-[rel:ITC_CLAIMED_VIA]->(r)
            SET rel.claimed_amount = row.claimed_amount,
                rel.eligible_amount = row.eligible_amount,
                rel.claim_period = row.claim_period
            """
            self._batch_execute(links, cypher)
            self.stats["relationships_created"] += len(links)
            logger.info(f"Created {len(links)} ITC_CLAIMED_VIA relationships")

    def load_all(self, data: dict):
        """Load all data from generator output into Neo4j."""
        logger.info("Starting full data ingestion...")

        self.initialize_schema()
        self.clear_database()
        self.initialize_schema()  # Re-create after clear

        self.load_taxpayers(data["taxpayers"])
        self.load_gstins(data["gstins"])
        self.load_invoices(data["invoices_gstr1"] + data["invoices_gstr2b"])
        self.load_returns(data["returns"])
        self.load_irns(data["irns"])
        self.load_ewaybills(data["ewaybills"])
        self.load_line_items(data["line_items"])
        self.load_bank_transactions(data["bank_transactions"])
        self.load_purchase_entries(data["purchase_entries"])

        # Create derived relationships
        all_invoices = data["invoices_gstr1"] + data["invoices_gstr2b"]
        self.create_reported_in_relationships(all_invoices, data["returns"])
        self.create_itc_claimed_via_relationships(all_invoices, data["returns"])
        self.create_transacts_with_relationships()

        logger.info(
            f"Ingestion complete: {self.stats['nodes_created']} nodes, "
            f"{self.stats['relationships_created']} relationships, "
            f"{len(self.stats['errors'])} errors"
        )
        return self.stats

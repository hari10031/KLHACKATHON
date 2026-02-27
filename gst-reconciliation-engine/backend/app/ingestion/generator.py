"""
Synthetic GST data generator with configurable mismatch injection.

Generates 50+ taxpayers, 500+ invoices across 12 months with realistic
HSN codes, tax rates, and 15-20% deliberate mismatches.
"""

import random
import hashlib
import json
import csv
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
from loguru import logger

from app.utils.gstin import STATE_CODES, generate_gstin_check_digit
from app.utils.helpers import (
    generate_uid, generate_irn_hash, financial_year_from_date,
    return_period_from_date,
)


# ────────────────────── Constants ──────────────────────

VALID_TAX_RATES = [0.0, 5.0, 12.0, 18.0, 28.0]

HSN_CODES = {
    "1001": ("Wheat", 0.0), "1006": ("Rice", 5.0), "0402": ("Milk products", 5.0),
    "2106": ("Food preparations", 12.0), "3004": ("Medicaments", 12.0),
    "3926": ("Plastic articles", 18.0), "7308": ("Steel structures", 18.0),
    "8471": ("Computers", 18.0), "8517": ("Telecom equipment", 18.0),
    "8703": ("Motor cars", 28.0), "2402": ("Cigarettes", 28.0),
    "6109": ("T-shirts", 5.0), "8504": ("Transformers", 18.0),
    "7210": ("Steel sheets", 18.0), "3923": ("Plastic packaging", 18.0),
    "8443": ("Printers", 18.0), "9403": ("Furniture", 18.0),
    "8528": ("Monitors/TVs", 18.0), "2710": ("Petroleum oils", 5.0),
    "8544": ("Wires/cables", 18.0),
}

BUSINESS_NAMES = [
    "Bharat Electronics Ltd", "Tata Steel Industries", "Reliance Trading Corp",
    "Mahindra Components", "Infosys Technologies", "Wipro Ltd",
    "Adani Enterprises", "Hindustan Unilever", "ITC Limited",
    "Larsen & Toubro Eng", "Bajaj Auto Parts", "Sun Pharma Labs",
    "Cipla Healthcare", "JSW Steel Works", "Grasim Industries",
    "UltraTech Cement", "Asian Paints Co", "Titan Company Ltd",
    "Maruti Suzuki Comp", "Hero MotoCorp Parts",
    "Godrej Consumer", "Dabur India Ltd", "Havells India",
    "Voltas Limited", "Blue Star Cooling", "Crompton Greaves",
    "Amara Raja Batt", "Exide Industries", "Berger Paints",
    "Pidilite Industries", "Coromandel Intl", "Aarti Industries",
    "SRF Limited", "Deepak Nitrite", "Navin Fluorine",
    "Gujarat Gas Ltd", "Thermax Limited", "Kirloskar Brothers",
    "Cummins India", "ABB India Ltd", "Siemens India Ltd",
    "Schneider Elec IN", "Honeywell Auto IN", "Bosch Limited",
    "SKF India Ltd", "Timken India Ltd", "Schaeffler India",
    "ZF Commercial IN", "Valeo India Auto", "Continental IN",
    "Finolex Cables", "Polycab India", "KEI Industries",
]

STATES_WITH_CODES = list(STATE_CODES.items())

BUSINESS_TYPES = ["Proprietorship", "Partnership", "LLP", "Private Limited", "Public Limited"]

UNITS = ["NOS", "KGS", "MTR", "LTR", "PCS", "SET", "BOX", "TON"]


@dataclass
class GeneratedTaxpayer:
    pan: str
    legal_name: str
    registration_date: str
    business_type: str
    state: str
    state_code: str
    aggregate_turnover: float
    compliance_rating: float
    gstins: List[str] = field(default_factory=list)


@dataclass
class GeneratedInvoice:
    uid: str
    invoice_number: str
    invoice_date: str
    invoice_type: str
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    cess: float
    total_value: float
    place_of_supply: str
    reverse_charge_flag: bool
    hsn_code: str
    supplier_gstin: str
    recipient_gstin: str
    source: str  # "GSTR1" or "GSTR2B"
    tax_rate: float = 18.0


@dataclass
class GeneratedReturn:
    uid: str
    return_type: str
    return_period: str
    filing_date: str
    filing_status: str
    revision_number: int
    gstin: str


@dataclass
class MismatchInjection:
    mismatch_type: str
    original_invoice: dict
    modified_invoice: dict
    description: str


class SyntheticDataGenerator:
    """
    Generates realistic GST ecosystem data with configurable mismatch rates.
    
    Usage:
        gen = SyntheticDataGenerator(
            num_taxpayers=50, num_invoices=500, mismatch_rate=0.17
        )
        data = gen.generate_all()
        gen.export_json("./data")
        gen.export_csv("./data")
    """

    def __init__(
        self,
        num_taxpayers: int = 55,
        num_invoices: int = 600,
        mismatch_rate: float = 0.17,
        num_months: int = 12,
        seed: int = 42,
    ):
        self.num_taxpayers = num_taxpayers
        self.num_invoices = num_invoices
        self.mismatch_rate = mismatch_rate
        self.num_months = num_months
        self.seed = seed
        random.seed(seed)

        self.taxpayers: List[GeneratedTaxpayer] = []
        self.gstins: List[dict] = []
        self.invoices_gstr1: List[GeneratedInvoice] = []
        self.invoices_gstr2b: List[GeneratedInvoice] = []
        self.returns: List[GeneratedReturn] = []
        self.irns: List[dict] = []
        self.ewaybills: List[dict] = []
        self.line_items: List[dict] = []
        self.bank_transactions: List[dict] = []
        self.purchase_entries: List[dict] = []
        self.mismatches_injected: List[MismatchInjection] = []
        self.circular_chains: List[List[str]] = []

        # Date range: April 2024 to March 2025 (FY 2024-25)
        self.start_date = date(2024, 4, 1)
        self.end_date = date(2025, 3, 31)

    def _random_pan(self) -> str:
        """Generate a valid-format PAN."""
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        first3 = "".join(random.choices(letters, k=3))
        fourth = random.choice("ABCFGHLJPT")  # Entity type
        fifth = random.choice(letters)
        digits = "".join(random.choices("0123456789", k=4))
        check = random.choice(letters)
        return f"{first3}{fourth}{fifth}{digits}{check}"

    def _random_gstin(self, pan: str, state_code: str) -> str:
        """Generate a valid-format GSTIN from PAN and state code."""
        entity_code = random.choice("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        partial = f"{state_code}{pan}{entity_code}Z"
        check = generate_gstin_check_digit(partial)
        return f"{partial}{check}"

    def _random_date_in_range(self, start: date = None, end: date = None) -> date:
        """Generate a random date within range."""
        s = start or self.start_date
        e = end or self.end_date
        delta = (e - s).days
        return s + timedelta(days=random.randint(0, max(0, delta)))

    def _random_invoice_number(self, supplier_gstin: str, seq: int) -> str:
        """Generate realistic invoice number."""
        prefixes = ["INV", "B2B", "TAX", "GST", "SI", ""]
        prefix = random.choice(prefixes)
        fy = "2425"
        sep = random.choice(["/", "-", ""])
        num = str(seq).zfill(random.randint(3, 6))
        parts = [p for p in [prefix, fy, num] if p]
        return sep.join(parts)

    def generate_taxpayers(self) -> List[GeneratedTaxpayer]:
        """Generate taxpayer entities with GSTINs."""
        logger.info(f"Generating {self.num_taxpayers} taxpayers...")

        used_pans = set()
        for i in range(self.num_taxpayers):
            pan = self._random_pan()
            while pan in used_pans:
                pan = self._random_pan()
            used_pans.add(pan)

            state_code, state_name = random.choice(STATES_WITH_CODES)
            name = BUSINESS_NAMES[i % len(BUSINESS_NAMES)]
            if i >= len(BUSINESS_NAMES):
                name += f" {i // len(BUSINESS_NAMES) + 1}"

            reg_date = self._random_date_in_range(
                date(2017, 7, 1), date(2023, 12, 31)
            )
            turnover = round(random.uniform(500000, 500000000), 2)
            compliance = round(random.uniform(20, 100), 1)

            # Mark some as non-compliant
            if i % 8 == 0:
                compliance = round(random.uniform(5, 35), 1)

            tp = GeneratedTaxpayer(
                pan=pan,
                legal_name=name,
                registration_date=reg_date.isoformat(),
                business_type=random.choice(BUSINESS_TYPES),
                state=state_name,
                state_code=state_code,
                aggregate_turnover=turnover,
                compliance_rating=compliance,
            )

            # Generate 1-2 GSTINs per taxpayer
            num_gstins = random.choices([1, 2], weights=[0.8, 0.2])[0]
            used_states = {state_code}
            for j in range(num_gstins):
                sc = state_code if j == 0 else random.choice(
                    [c for c, _ in STATES_WITH_CODES if c not in used_states]
                )
                used_states.add(sc)
                gstin = self._random_gstin(pan, sc)
                tp.gstins.append(gstin)

                status = "active"
                if compliance < 20 and random.random() < 0.3:
                    status = random.choice(["suspended", "cancelled"])

                self.gstins.append({
                    "gstin_number": gstin,
                    "state_code": sc,
                    "status": status,
                    "registration_type": random.choices(
                        ["regular", "composition", "ISD"],
                        weights=[0.85, 0.10, 0.05]
                    )[0],
                    "pan": pan,
                })

            self.taxpayers.append(tp)

        logger.info(f"Generated {len(self.taxpayers)} taxpayers, {len(self.gstins)} GSTINs")
        return self.taxpayers

    def generate_invoices(self) -> Tuple[List[GeneratedInvoice], List[GeneratedInvoice]]:
        """Generate invoice pairs (GSTR-1 and GSTR-2B) with mismatch injection."""
        logger.info(f"Generating {self.num_invoices} invoice pairs...")

        all_gstins = [g["gstin_number"] for g in self.gstins if g["status"] == "active"]
        cancelled_gstins = [g["gstin_number"] for g in self.gstins if g["status"] == "cancelled"]

        num_mismatches = int(self.num_invoices * self.mismatch_rate)
        mismatch_indices = set(random.sample(range(self.num_invoices), num_mismatches))

        # Mismatch type distribution
        mismatch_types = [
            ("VALUE_MISMATCH", 0.15),
            ("TAX_RATE_MISMATCH", 0.10),
            ("MISSING_IN_GSTR2B", 0.15),
            ("MISSING_IN_GSTR1", 0.10),
            ("DUPLICATE", 0.08),
            ("ITC_OVERCLAIM", 0.10),
            ("PERIOD_MISMATCH", 0.08),
            ("PHANTOM_INVOICE", 0.06),
            ("CIRCULAR_TRADE", 0.06),
            ("IRN_INVALID", 0.06),
            ("EWB_MISMATCH", 0.06),
        ]
        mismatch_names = [m[0] for m in mismatch_types]
        mismatch_weights = [m[1] for m in mismatch_types]

        for idx in range(self.num_invoices):
            supplier = random.choice(all_gstins)
            recipient = random.choice([g for g in all_gstins if g != supplier])

            inv_date = self._random_date_in_range()
            period = return_period_from_date(inv_date)
            fy = financial_year_from_date(inv_date)

            hsn_code, (desc, default_rate) = random.choice(list(HSN_CODES.items()))
            tax_rate = default_rate
            taxable_value = round(random.uniform(1000, 5000000), 2)

            supplier_state = supplier[:2]
            recipient_state = recipient[:2]
            is_inter_state = supplier_state != recipient_state
            pos = recipient_state

            if is_inter_state:
                igst = round(taxable_value * tax_rate / 100, 2)
                cgst = 0.0
                sgst = 0.0
            else:
                cgst = round(taxable_value * tax_rate / 200, 2)
                sgst = round(taxable_value * tax_rate / 200, 2)
                igst = 0.0

            cess = round(taxable_value * 0.01, 2) if tax_rate == 28.0 and random.random() < 0.3 else 0.0
            total_value = round(taxable_value + cgst + sgst + igst + cess, 2)

            inv_number = self._random_invoice_number(supplier, idx + 1)
            uid_gstr1 = generate_uid(supplier, inv_number, inv_date.isoformat(), "GSTR1")

            gstr1_inv = GeneratedInvoice(
                uid=uid_gstr1,
                invoice_number=inv_number,
                invoice_date=inv_date.isoformat(),
                invoice_type="B2B",
                taxable_value=taxable_value,
                cgst=cgst, sgst=sgst, igst=igst, cess=cess,
                total_value=total_value,
                place_of_supply=pos,
                reverse_charge_flag=random.random() < 0.05,
                hsn_code=hsn_code,
                supplier_gstin=supplier,
                recipient_gstin=recipient,
                source="GSTR1",
                tax_rate=tax_rate,
            )

            # Default: exact mirror for GSTR-2B
            gstr2b_inv = GeneratedInvoice(
                uid=generate_uid(supplier, inv_number, inv_date.isoformat(), "GSTR2B"),
                invoice_number=inv_number,
                invoice_date=inv_date.isoformat(),
                invoice_type="B2B",
                taxable_value=taxable_value,
                cgst=cgst, sgst=sgst, igst=igst, cess=cess,
                total_value=total_value,
                place_of_supply=pos,
                reverse_charge_flag=gstr1_inv.reverse_charge_flag,
                hsn_code=hsn_code,
                supplier_gstin=supplier,
                recipient_gstin=recipient,
                source="GSTR2B",
                tax_rate=tax_rate,
            )

            # Generate line items
            num_lines = random.randint(1, 4)
            for li in range(num_lines):
                li_hsn, (li_desc, li_rate) = random.choice(list(HSN_CODES.items()))
                qty = round(random.uniform(1, 1000), 2)
                unit_rate = round(random.uniform(10, 50000), 2)
                li_taxable = round(qty * unit_rate, 2)
                self.line_items.append({
                    "uid": generate_uid(uid_gstr1, str(li)),
                    "invoice_uid": uid_gstr1,
                    "hsn_code": li_hsn,
                    "description": li_desc,
                    "quantity": qty,
                    "unit": random.choice(UNITS),
                    "rate": unit_rate,
                    "taxable_value": li_taxable,
                    "tax_rate": li_rate,
                    "line_number": li + 1,
                })

            # Generate IRN (for B2B invoices with value > ₹5 Cr turnover)
            irn_hash = generate_irn_hash(supplier, inv_number, fy)
            self.irns.append({
                "irn_hash": irn_hash,
                "irn_status": "active",
                "generation_date": datetime.combine(inv_date, datetime.min.time()).isoformat(),
                "signed_qr_code": hashlib.md5(irn_hash.encode()).hexdigest(),
                "invoice_uid": uid_gstr1,
            })

            # Generate e-Way bill (for values > ₹50,000)
            if total_value > 50000:
                ewb_gen_date = datetime.combine(inv_date, datetime.min.time())
                self.ewaybills.append({
                    "ewb_number": f"{random.randint(100000000000, 999999999999)}",
                    "generation_date": ewb_gen_date.isoformat(),
                    "validity": (ewb_gen_date + timedelta(days=random.choice([1, 3, 7, 15]))).isoformat(),
                    "transporter_id": self._random_gstin(self._random_pan(), random.choice(list(STATE_CODES.keys()))),
                    "vehicle_number": f"{random.choice(['MH','DL','KA','TN','GJ'])}{random.randint(1,99):02d}{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}{random.randint(1000,9999)}",
                    "distance_km": round(random.uniform(10, 2500), 1),
                    "invoice_uid": uid_gstr1,
                    "total_value": total_value,
                })

            # Generate bank transaction
            if random.random() < 0.7:
                pay_date = inv_date + timedelta(days=random.randint(0, 60))
                self.bank_transactions.append({
                    "transaction_id": f"TXN{random.randint(100000, 999999)}",
                    "date": pay_date.isoformat(),
                    "amount": total_value,
                    "payment_mode": random.choice(["NEFT", "RTGS", "UPI", "CHEQUE"]),
                    "reference_number": f"REF{random.randint(10000, 99999)}",
                    "invoice_uid": uid_gstr1,
                })

            # Generate purchase register entry
            self.purchase_entries.append({
                "entry_id": f"PR{idx + 1:06d}",
                "booking_date": inv_date.isoformat(),
                "taxable_value": taxable_value,
                "igst": igst, "cgst": cgst, "sgst": sgst,
                "itc_eligibility": random.choices(
                    ["eligible", "ineligible", "provisional"],
                    weights=[0.8, 0.1, 0.1]
                )[0],
                "invoice_uid": uid_gstr1,
            })

            # ──── MISMATCH INJECTION ────
            if idx in mismatch_indices:
                mm_type = random.choices(mismatch_names, weights=mismatch_weights)[0]
                gstr2b_inv = self._inject_mismatch(
                    mm_type, gstr1_inv, gstr2b_inv, 
                    all_gstins, cancelled_gstins, inv_date, period
                )

            self.invoices_gstr1.append(gstr1_inv)
            if gstr2b_inv is not None:  # Could be None for MISSING_IN_GSTR2B
                self.invoices_gstr2b.append(gstr2b_inv)

        # Inject circular trading patterns
        self._inject_circular_trades(all_gstins)

        logger.info(
            f"Generated {len(self.invoices_gstr1)} GSTR-1 invoices, "
            f"{len(self.invoices_gstr2b)} GSTR-2B invoices, "
            f"{len(self.mismatches_injected)} mismatches injected"
        )
        return self.invoices_gstr1, self.invoices_gstr2b

    def _inject_mismatch(
        self, mm_type: str, gstr1: GeneratedInvoice, gstr2b: GeneratedInvoice,
        all_gstins: List[str], cancelled_gstins: List[str],
        inv_date: date, period: str
    ) -> Optional[GeneratedInvoice]:
        """Inject a specific mismatch type into the GSTR-2B invoice."""

        desc = ""

        if mm_type == "VALUE_MISMATCH":
            # Alter taxable value in GSTR-2B by 5-30%
            factor = random.uniform(0.7, 0.95) if random.random() < 0.5 else random.uniform(1.05, 1.3)
            gstr2b.taxable_value = round(gstr1.taxable_value * factor, 2)
            gstr2b.total_value = round(
                gstr2b.taxable_value + gstr2b.cgst + gstr2b.sgst + gstr2b.igst + gstr2b.cess, 2
            )
            desc = f"Taxable value differs: GSTR-1={gstr1.taxable_value}, GSTR-2B={gstr2b.taxable_value}"

        elif mm_type == "TAX_RATE_MISMATCH":
            wrong_rate = random.choice([r for r in VALID_TAX_RATES if r != gstr1.tax_rate])
            if gstr2b.igst > 0:
                gstr2b.igst = round(gstr2b.taxable_value * wrong_rate / 100, 2)
            else:
                gstr2b.cgst = round(gstr2b.taxable_value * wrong_rate / 200, 2)
                gstr2b.sgst = round(gstr2b.taxable_value * wrong_rate / 200, 2)
            gstr2b.total_value = round(
                gstr2b.taxable_value + gstr2b.cgst + gstr2b.sgst + gstr2b.igst + gstr2b.cess, 2
            )
            gstr2b.tax_rate = wrong_rate
            desc = f"Tax rate mismatch: GSTR-1={gstr1.tax_rate}%, GSTR-2B={wrong_rate}%"

        elif mm_type == "MISSING_IN_GSTR2B":
            desc = f"Invoice {gstr1.invoice_number} present in GSTR-1 but missing in GSTR-2B"
            self.mismatches_injected.append(MismatchInjection(
                mismatch_type=mm_type,
                original_invoice=asdict(gstr1),
                modified_invoice={},
                description=desc,
            ))
            return None  # No GSTR-2B entry

        elif mm_type == "MISSING_IN_GSTR1":
            gstr1.source = "PHANTOM_GSTR1"  # Mark as not actually in GSTR-1
            desc = f"Invoice {gstr2b.invoice_number} in GSTR-2B but not filed in GSTR-1"

        elif mm_type == "DUPLICATE":
            # Create a duplicate with same invoice number, slightly different date
            dup = GeneratedInvoice(
                uid=generate_uid(gstr1.supplier_gstin, gstr1.invoice_number, "DUP", "GSTR2B"),
                invoice_number=gstr1.invoice_number,
                invoice_date=(inv_date + timedelta(days=random.randint(1, 15))).isoformat(),
                invoice_type=gstr1.invoice_type,
                taxable_value=gstr1.taxable_value,
                cgst=gstr1.cgst, sgst=gstr1.sgst, igst=gstr1.igst, cess=gstr1.cess,
                total_value=gstr1.total_value,
                place_of_supply=gstr1.place_of_supply,
                reverse_charge_flag=gstr1.reverse_charge_flag,
                hsn_code=gstr1.hsn_code,
                supplier_gstin=gstr1.supplier_gstin,
                recipient_gstin=gstr1.recipient_gstin,
                source="GSTR2B",
                tax_rate=gstr1.tax_rate,
            )
            self.invoices_gstr2b.append(dup)
            desc = f"Duplicate invoice {gstr1.invoice_number} appearing twice in GSTR-2B"

        elif mm_type == "ITC_OVERCLAIM":
            # ITC claimed is higher than eligible (will be checked in chain validation)
            overclaim_factor = random.uniform(1.2, 2.0)
            tax_amount = gstr1.cgst + gstr1.sgst + gstr1.igst
            self.purchase_entries[-1]["itc_eligibility"] = "eligible"
            # The overclaim will be detected by comparing claimed vs eligible in the ITC chain
            desc = f"ITC overclaimed by factor {overclaim_factor:.2f}x on invoice {gstr1.invoice_number}"

        elif mm_type == "PERIOD_MISMATCH":
            # Invoice reported in different period in GSTR-2B
            offset_months = random.choice([-2, -1, 1, 2])
            new_month = ((inv_date.month - 1 + offset_months) % 12) + 1
            new_year = inv_date.year + ((inv_date.month - 1 + offset_months) // 12)
            new_date = inv_date.replace(month=new_month, year=new_year, day=min(inv_date.day, 28))
            gstr2b.invoice_date = new_date.isoformat()
            desc = f"Period mismatch: GSTR-1 date={gstr1.invoice_date}, GSTR-2B date={gstr2b.invoice_date}"

        elif mm_type == "PHANTOM_INVOICE":
            if cancelled_gstins:
                gstr1.supplier_gstin = random.choice(cancelled_gstins)
                gstr2b.supplier_gstin = gstr1.supplier_gstin
            desc = f"Phantom invoice from cancelled GSTIN {gstr1.supplier_gstin}"

        elif mm_type == "IRN_INVALID":
            if self.irns:
                self.irns[-1]["irn_status"] = random.choice(["cancelled", "invalid"])
            desc = f"IRN invalid/cancelled for invoice {gstr1.invoice_number}"

        elif mm_type == "EWB_MISMATCH":
            if self.ewaybills:
                ewb = self.ewaybills[-1]
                ewb["total_value"] = round(ewb["total_value"] * random.uniform(0.5, 0.8), 2)
            desc = f"e-Way Bill value discrepancy for invoice {gstr1.invoice_number}"

        elif mm_type == "CIRCULAR_TRADE":
            pass  # Handled separately in _inject_circular_trades

        self.mismatches_injected.append(MismatchInjection(
            mismatch_type=mm_type,
            original_invoice=asdict(gstr1),
            modified_invoice=asdict(gstr2b),
            description=desc,
        ))

        return gstr2b

    def _inject_circular_trades(self, all_gstins: List[str]):
        """Inject 3-4 circular trading chains: A->B->C->A with inflated values."""
        logger.info("Injecting circular trading patterns...")
        num_chains = random.randint(3, 4)

        for chain_idx in range(num_chains):
            chain_length = random.randint(3, 5)
            chain_gstins = random.sample(all_gstins, min(chain_length, len(all_gstins)))

            if len(chain_gstins) < 3:
                continue

            base_value = round(random.uniform(100000, 2000000), 2)
            inflation = random.uniform(1.1, 1.5)

            chain = []
            for i in range(len(chain_gstins)):
                supplier = chain_gstins[i]
                recipient = chain_gstins[(i + 1) % len(chain_gstins)]
                value = round(base_value * (inflation ** i), 2)

                inv_date = self._random_date_in_range()
                inv_num = f"CIRC-{chain_idx}-{i}"
                uid = generate_uid(supplier, inv_num, inv_date.isoformat(), "CIRC")

                tax_rate = 18.0
                igst = round(value * tax_rate / 100, 2)

                inv = GeneratedInvoice(
                    uid=uid,
                    invoice_number=inv_num,
                    invoice_date=inv_date.isoformat(),
                    invoice_type="B2B",
                    taxable_value=value,
                    cgst=0.0, sgst=0.0, igst=igst, cess=0.0,
                    total_value=round(value + igst, 2),
                    place_of_supply=recipient[:2],
                    reverse_charge_flag=False,
                    hsn_code="8471",
                    supplier_gstin=supplier,
                    recipient_gstin=recipient,
                    source="GSTR1",
                    tax_rate=tax_rate,
                )
                self.invoices_gstr1.append(inv)
                # Mirror in GSTR-2B
                inv2b = GeneratedInvoice(
                    uid=generate_uid(supplier, inv_num, inv_date.isoformat(), "GSTR2B_CIRC"),
                    invoice_number=inv_num,
                    invoice_date=inv_date.isoformat(),
                    invoice_type="B2B",
                    taxable_value=value,
                    cgst=0.0, sgst=0.0, igst=igst, cess=0.0,
                    total_value=round(value + igst, 2),
                    place_of_supply=recipient[:2],
                    reverse_charge_flag=False,
                    hsn_code="8471",
                    supplier_gstin=supplier,
                    recipient_gstin=recipient,
                    source="GSTR2B",
                    tax_rate=tax_rate,
                )
                self.invoices_gstr2b.append(inv2b)
                chain.append(supplier)

            self.circular_chains.append(chain)

        logger.info(f"Injected {len(self.circular_chains)} circular trading chains")

    def generate_returns(self) -> List[GeneratedReturn]:
        """Generate return filings for all GSTINs across all months."""
        logger.info("Generating return filings...")

        for gstin_data in self.gstins:
            gstin = gstin_data["gstin_number"]
            for month_offset in range(self.num_months):
                month = ((3 + month_offset) % 12) + 1  # Start from April
                year = 2024 if month >= 4 else 2025
                period = f"{month:02d}{year}"

                for ret_type in ["GSTR1", "GSTR2B", "GSTR3B"]:
                    # Due dates: GSTR-1 by 11th, GSTR-3B by 20th
                    due_day = 11 if ret_type == "GSTR1" else 20
                    due_date = date(year if month < 12 else year + 1,
                                   (month % 12) + 1, due_day)

                    # Simulate filing delays
                    delay_days = 0
                    filing_status = "filed"
                    if gstin_data.get("status") == "cancelled":
                        filing_status = "not_filed"
                        filing_date = None
                    elif random.random() < 0.15:
                        delay_days = random.randint(1, 60)
                        filing_status = "late_filed"
                        filing_date = (due_date + timedelta(days=delay_days)).isoformat()
                    elif random.random() < 0.05:
                        filing_status = "not_filed"
                        filing_date = None
                    else:
                        filing_date = (due_date - timedelta(days=random.randint(0, 5))).isoformat()

                    uid = generate_uid(gstin, ret_type, period)
                    ret = GeneratedReturn(
                        uid=uid,
                        return_type=ret_type,
                        return_period=period,
                        filing_date=filing_date or "",
                        filing_status=filing_status,
                        revision_number=0,
                        gstin=gstin,
                    )
                    self.returns.append(ret)

        logger.info(f"Generated {len(self.returns)} return filings")
        return self.returns

    def generate_all(self) -> dict:
        """Generate all synthetic data."""
        self.generate_taxpayers()
        self.generate_invoices()
        self.generate_returns()

        return {
            "taxpayers": [asdict(t) for t in self.taxpayers],
            "gstins": self.gstins,
            "invoices_gstr1": [asdict(i) for i in self.invoices_gstr1],
            "invoices_gstr2b": [asdict(i) for i in self.invoices_gstr2b],
            "returns": [asdict(r) for r in self.returns],
            "irns": self.irns,
            "ewaybills": self.ewaybills,
            "line_items": self.line_items,
            "bank_transactions": self.bank_transactions,
            "purchase_entries": self.purchase_entries,
            "circular_chains": self.circular_chains,
            "mismatches_injected": [asdict(m) for m in self.mismatches_injected],
            "stats": {
                "num_taxpayers": len(self.taxpayers),
                "num_gstins": len(self.gstins),
                "num_invoices_gstr1": len(self.invoices_gstr1),
                "num_invoices_gstr2b": len(self.invoices_gstr2b),
                "num_returns": len(self.returns),
                "num_irns": len(self.irns),
                "num_ewaybills": len(self.ewaybills),
                "num_mismatches": len(self.mismatches_injected),
                "num_circular_chains": len(self.circular_chains),
            },
        }

    def export_json(self, output_dir: str = "./data"):
        """Export all generated data to JSON files."""
        os.makedirs(output_dir, exist_ok=True)
        data = self.generate_all() if not self.taxpayers else {
            "taxpayers": [asdict(t) for t in self.taxpayers],
            "gstins": self.gstins,
            "invoices_gstr1": [asdict(i) for i in self.invoices_gstr1],
            "invoices_gstr2b": [asdict(i) for i in self.invoices_gstr2b],
            "returns": [asdict(r) for r in self.returns],
            "irns": self.irns,
            "ewaybills": self.ewaybills,
            "line_items": self.line_items,
            "bank_transactions": self.bank_transactions,
            "purchase_entries": self.purchase_entries,
        }

        for key, records in data.items():
            if isinstance(records, list) and records:
                filepath = os.path.join(output_dir, f"{key}.json")
                with open(filepath, "w") as f:
                    json.dump(records, f, indent=2, default=str)
                logger.info(f"Exported {len(records)} records to {filepath}")

    def export_csv(self, output_dir: str = "./data"):
        """Export key datasets to CSV for Neo4j LOAD CSV."""
        os.makedirs(output_dir, exist_ok=True)

        datasets = {
            "taxpayers": [asdict(t) for t in self.taxpayers],
            "gstins": self.gstins,
            "invoices_gstr1": [asdict(i) for i in self.invoices_gstr1],
            "invoices_gstr2b": [asdict(i) for i in self.invoices_gstr2b],
            "returns": [asdict(r) for r in self.returns],
            "irns": self.irns,
            "ewaybills": self.ewaybills,
            "line_items": self.line_items,
            "bank_transactions": self.bank_transactions,
            "purchase_entries": self.purchase_entries,
        }

        for name, records in datasets.items():
            if not records:
                continue
            filepath = os.path.join(output_dir, f"{name}.csv")
            # Flatten nested fields (like gstins list in taxpayers)
            flat_records = []
            for rec in records:
                flat = {}
                for k, v in rec.items():
                    if isinstance(v, list):
                        flat[k] = ";".join(str(x) for x in v)
                    else:
                        flat[k] = v
                flat_records.append(flat)

            if flat_records:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=flat_records[0].keys())
                    writer.writeheader()
                    writer.writerows(flat_records)
                logger.info(f"Exported {len(flat_records)} records to {filepath}")

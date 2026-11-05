"""FreightGuard Tariff Intelligence & Contract RAG Engine
Provides indexed retrieval of contracted clauses, rate schedules, and telematics evidence.
Preserves verifiable source citations, clause sections, and contract effective periods.
Includes a local, dependency-free BM25 retrieval ranker for grounding AI dispute generation.
"""
from typing import Dict, Any, List, Optional
import json
import re
import math
from collections import Counter


def _tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for local BM25 ranking."""
    return re.findall(r"\w+", (text or "").lower())


def bm25_rank(documents: List[Dict[str, Any]], query: str, k1: float = 1.5, b: float = 0.75) -> List[Dict[str, Any]]:
    """Ranks a list of clause dictionaries against a query string using BM25.
    Returns documents with an added 'bm25_score' field, sorted descending by score.
    """
    if not documents:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return documents

    N = len(documents)
    doc_token_counts = []
    doc_lens = []
    df = Counter()

    for doc in documents:
        # Combine text representation of rule
        content = f"{doc.get('rule_code', '')} {doc.get('clause_reference', '')} {doc.get('category', '')} {doc.get('rule_description', '')}"
        tokens = _tokenize(content)
        counts = Counter(tokens)
        doc_token_counts.append(counts)
        doc_lens.append(len(tokens))
        for word in counts.keys():
            df[word] += 1

    avgdl = sum(doc_lens) / max(N, 1)

    scored_docs = []
    for idx, doc in enumerate(documents):
        counts = doc_token_counts[idx]
        dl = doc_lens[idx]
        score = 0.0
        for q in query_tokens:
            if q in counts:
                # Standard BM25 idf & tf formula
                n_q = df[q]
                idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)
                tf = counts[q]
                denom = tf + k1 * (1.0 - b + b * (dl / max(avgdl, 1e-6)))
                score += idf * ((tf * (k1 + 1.0)) / max(denom, 1e-6))

        doc_copy = dict(doc)
        doc_copy["bm25_score"] = round(score, 4)
        scored_docs.append(doc_copy)

    scored_docs.sort(key=lambda d: d["bm25_score"], reverse=True)
    return scored_docs


class TariffRAGEngine:
    """Deterministic, indexed tariff retrieval engine."""

    def __init__(self, db_conn):
        self.conn = db_conn

    def get_contract_for_carrier(self, carrier_id: str, invoice_date: str) -> Optional[Dict[str, Any]]:
        """Retrieves active contract for the given carrier and invoice date."""
        cur = self.conn.cursor()
        cur.execute(
            """SELECT * FROM contracts 
               WHERE carrier_id = ? 
               AND status = 'ACTIVE'
               AND date(?) BETWEEN date(effective_start) AND date(effective_end)
               ORDER BY effective_start DESC LIMIT 1""",
            (carrier_id, invoice_date)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_tariff_rules_for_contract(self, contract_id: str) -> List[Dict[str, Any]]:
        """Retrieves all tariff rules associated with a contract."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tariff_rules WHERE contract_id = ?", (contract_id,))
        rows = cur.fetchall()
        rules = []
        for r in rows:
            rule_dict = dict(r)
            if rule_dict.get("parameters_json"):
                try:
                    rule_dict["parameters"] = json.loads(rule_dict["parameters_json"])
                except Exception:
                    rule_dict["parameters"] = {}
            rules.append(rule_dict)
        return rules

    def get_shipment_evidence(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves telematics, BOL, and physical dock evidence for a shipment."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,))
        row = cur.fetchone()
        if not row:
            return None
        shipment = dict(row)
        if shipment.get("pre_authorized_accessorials_json"):
            try:
                shipment["pre_authorized_accessorials"] = json.loads(shipment["pre_authorized_accessorials_json"])
            except Exception:
                shipment["pre_authorized_accessorials"] = []
        else:
            shipment["pre_authorized_accessorials"] = []
        return shipment

    def retrieve_clause_citation(
        self,
        contract_id: str,
        category: str,
        charge_code: str,
        origin: str = None,
        destination: str = None
    ) -> Dict[str, Any]:
        """Performs indexed citation search for a specific charge category and lane."""
        cur = self.conn.cursor()
        
        # Search for exact lane match if LINEHAUL
        if category == "LINEHAUL" and origin and destination:
            cur.execute(
                """SELECT * FROM tariff_rules 
                   WHERE contract_id = ? AND category = 'LINEHAUL' 
                   AND origin_zone = ? AND destination_zone = ? LIMIT 1""",
                (contract_id, origin, destination)
            )
            row = cur.fetchone()
            if row:
                return {
                    "found": True,
                    "clause_reference": row["clause_reference"],
                    "description": row["rule_description"],
                    "contracted_rate_cents": row["contracted_rate_cents"],
                    "rule_code": row["rule_code"]
                }

        # Search by category
        cur.execute(
            "SELECT * FROM tariff_rules WHERE contract_id = ? AND category = ? LIMIT 1",
            (contract_id, category)
        )
        row = cur.fetchone()
        if row:
            return {
                "found": True,
                "clause_reference": row["clause_reference"],
                "description": row["rule_description"],
                "contracted_rate_cents": row["contracted_rate_cents"],
                "rule_code": row["rule_code"]
            }

        return {
            "found": False,
            "clause_reference": "INSUFFICIENT_EVIDENCE",
            "description": f"No contractual tariff found for category '{category}' and charge '{charge_code}'.",
            "contracted_rate_cents": 0,
            "rule_code": "UNCONTRACTED"
        }

    def rank_clauses_for_findings(self, contract_id: str, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Retrieves and ranks contract clauses against audit findings using local BM25 ranking."""
        rules = self.get_tariff_rules_for_contract(contract_id)
        if not findings or not rules:
            return rules

        # Construct search query from findings
        query_parts = []
        for f in findings:
            query_parts.append(f.get("finding_type", ""))
            query_parts.append(f.get("clause_citation", ""))
            query_parts.append(f.get("explanation", ""))
        query = " ".join(query_parts)

        return bm25_rank(rules, query)

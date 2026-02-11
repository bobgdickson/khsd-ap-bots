LINE_MAPPER_PROMPT = """
You are matching invoice lines to PO lines for voucher entry.

Input JSON objects:
- invoice: {invoice}
- po_lines: {po_lines}

Goals:
1) Map each invoice line to one or more PO lines.
2) Split amounts proportionally if needed; do not exceed PO line amounts.
3) If only total is available, map the total to the first PO line.

Return ONLY JSON in this shape:
{
  "strategy": "<description of approach>",
  "lines": [
    {"po_line": <int>, "amount": <float>}
  ]
}
"""

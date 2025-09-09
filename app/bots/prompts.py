# Agent Prompt injections for behavior customization

CDW_PROMPT = """INVOICE NUMBER RULES (CDW):
- The invoice number is ALPHANUMERIC (contains at least one letter and one digit).
- Typical length 6 characters, uppercase, no spaces. Examples: AF66R7Y, AB123C45."""
CLASS_PROMPT = """PO NUMBER RULES (Class Leasing):
- The PO number will often have the form of LN1234 or KERNH-LN5678
- Typically the Lease# XXXX will match the PO as LNXXXX.  Don't include trailing zero like _0"""
# Agent Prompt injections for behavior customization

CDW_PROMPT = """INVOICE NUMBER RULES (CDW):
- The invoice number is ALPHANUMERIC (contains at least one letter and one digit).
- Typical length 6 characters, uppercase, no spaces. Examples: AF66R7Y, AB123C45."""
CLASS_PROMPT = """PO NUMBER RULES (Class Leasing):
- The PO number will often have the form of LN1234 or KERNH-LN5678
- Typically the Lease# XXXX will match the PO as LNXXXX.  Don't include trailing zero like _0"""
MOBILE_PROMPT = """PO NUMBER RULES (Mobile Modular):
- The PO number will often have the form of KERNH-CON12345
"""
FIC_PROMPT = """Scholarship Type: FIC"""
GRAINGER_PROMPT="""If the PO does not start with APO and is in the 95 series ending with a letter, prefix it with APO, the current active APO is APO950011J.
A fully numeric PO should be prefixed with 0's to make it a 10 digit number.
If you cannot find a PO number use APO950011J as the default as long as the amount is under $500."""
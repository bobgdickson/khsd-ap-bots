from .models import POLine
from app.database import SessionLocalPS
from sqlalchemy import text

def search_po_candidates(pattern: str) -> list[dict]:
    sql = text("""
        SELECT P.PO_ID, P.VENDOR_ID, V.NAME1, P.PO_STATUS, P.BUSINESS_UNIT
        FROM PS_PO_HDR P, PS_VENDOR V
        WHERE P.VENDOR_ID = V.VENDOR_ID
            AND PO_ID LIKE :pattern
    """)
    with SessionLocalPS() as db:
        rows = db.execute(sql, {"pattern": pattern}).fetchall()

    return [
        {
            "po_id": row.PO_ID,
            "vendor_id": row.VENDOR_ID,
            "vendor_name": row.NAME1,
            "status": row.PO_STATUS,
            "business_unit": row.BUSINESS_UNIT,
        }
        for row in rows
    ]


def load_po_lines(po_id: str) -> list[POLine]:
    sql = text("""
        SELECT A.PO_ID, A.LINE_NBR, B.SCHED_NBR, C.DISTRIB_LINE_NUM,
               A.DESCR254_MIXED, C.MERCHANDISE_AMT,
               C.ACCOUNT, C.FUND_CODE, C.PROGRAM_CODE
        FROM PS_PO_LINE A
        JOIN PS_PO_LINE_SHIP B ON A.BUSINESS_UNIT = B.BUSINESS_UNIT
                              AND A.PO_ID = B.PO_ID
                              AND A.LINE_NBR = B.LINE_NBR
        JOIN PS_PO_LINE_DISTRIB C ON A.BUSINESS_UNIT = C.BUSINESS_UNIT
                                 AND A.PO_ID = C.PO_ID
                                 AND A.LINE_NBR = C.LINE_NBR
                                 AND B.SCHED_NBR = C.SCHED_NBR
        WHERE A.PO_ID = :po_id
        ORDER BY A.LINE_NBR, B.SCHED_NBR, C.DISTRIB_LINE_NUM
    """)

    with SessionLocalPS() as db:
        rows = db.execute(sql, {"po_id": po_id}).fetchall()

    return [
        POLine(
            po_id=row.PO_ID,
            po_line=row.LINE_NBR,
            sched=row.SCHED_NBR,
            distrib=row.DISTRIB_LINE_NUM,
            description=row.DESCR254_MIXED,
            amount=row.MERCHANDISE_AMT,
            account=row.ACCOUNT,
            fund=row.FUND_CODE,
            program=row.PROGRAM_CODE,
        )
        for row in rows
    ]

if __name__ == "__main__":
    # Simple search of PO 227878
    results = search_po_candidates("%227878%")
    print("[SMOKE] PO Search Results:")
    for r in results:
        print(r)
    # Load PO lines for PO 227878 from json output
    first_line = results[0]
    po = first_line["po_id"]
    
    po_lines = load_po_lines(po)
    print("[SMOKE] PO Lines for PO 227878:")
    for line in po_lines:
        print(line)
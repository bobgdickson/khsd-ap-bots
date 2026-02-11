import datetime
from pathlib import Path

import pytest

from app.bots.voucher import pipeline
from app.bots.voucher.models import (
    ExtractedInvoice,
    InvoiceLine,
    LineMapping,
    LineMappingEntry,
    POLine,
    ValidatedPO,
)


def _sample_invoice() -> ExtractedInvoice:
    return ExtractedInvoice(
        invoice_number="INV-123",
        vendor_name="GRAINGER",
        invoice_date="2025-11-18",
        total_amount=155.8,
        purchase_order_raw="KERNH-0000227878",
        fuzzy_po_candidates=["KERNH-0000227878", "1567882102"],
        lines=[
            InvoiceLine(
                description="LOCKING PLIER SETS, PLAIN GRIP, 4 PCS",
                quantity=1.0,
                unit_price=75.1,
                line_amount=75.1,
            ),
            InvoiceLine(
                description="HEXKEY SET, L, 2 27/32 IN TO 6 3/4 IN",
                quantity=3.0,
                unit_price=22.94,
                line_amount=68.82,
            ),
        ],
    )


def _sample_po_lines():
    return [
        POLine(
            po_id="0000227878",
            po_line=1,
            sched=1,
            distrib=1,
            description="Tongue and Groove Plier Set",
            amount=93.74,
            account="4301",
            fund="03",
            program="0000",
        ),
        POLine(
            po_id="0000227878",
            po_line=2,
            sched=1,
            distrib=1,
            description="Locking Pliers Set",
            amount=75.10,
            account="4301",
            fund="03",
            program="0000",
        ),
    ]


def test_run_extraction_monkeypatched(monkeypatch, tmp_path):
    from app.bots.voucher import extraction_stage

    sample_invoice = _sample_invoice()

    # Patch extract_to_schema to avoid network/OpenAI during test
    monkeypatch.setattr(
        extraction_stage,
        "extract_to_schema",
        lambda file_path, schema, prompt=None: sample_invoice,
    )

    # Create dummy file path
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_text("placeholder")

    result = extraction_stage.run_extraction(str(pdf_path), extra_prompt=None)
    assert isinstance(result, ExtractedInvoice)
    assert result.invoice_number == sample_invoice.invoice_number
    assert result.lines, "Should include at least one line item"


def test_identify_po_monkeypatched(monkeypatch):
    from app.bots.voucher import po_identifier

    sample_invoice = _sample_invoice()
    expected = ValidatedPO(
        po_id="0000227878",
        vendor_id="V001",
        vendor_name="GRAINGER",
        confidence=0.9,
    )

    class DummyAgent:
        def invoke(self, *_, **__):
            return {"structured_response": expected}

    monkeypatch.setattr(po_identifier, "create_agent", lambda **kwargs: DummyAgent())
    result = po_identifier.identify_po(sample_invoice, filepath="dummy.pdf", extra_prompt=None)
    assert isinstance(result, ValidatedPO)
    assert result.po_id == expected.po_id
    assert result.confidence == pytest.approx(0.9)


def test_generate_line_mapping_monkeypatched(monkeypatch):
    from app.bots.voucher import line_mapper

    sample_invoice = _sample_invoice()
    po_lines = _sample_po_lines()
    expected = LineMapping(
        strategy="single-line",
        lines=[LineMappingEntry(po_line=1, amount=75.1)],
    )

    class DummyAgent:
        def invoke(self, *_args, **_kwargs):
            return {"structured_response": expected}

    monkeypatch.setattr(line_mapper, "create_agent", lambda **kwargs: DummyAgent())
    mapping = line_mapper.generate_line_mapping(sample_invoice, po_lines)
    assert isinstance(mapping, LineMapping)
    assert mapping.lines[0].po_line == 1
    assert mapping.lines[0].amount == pytest.approx(75.1)


def test_pipeline_run_v2_voucher(monkeypatch, tmp_path):
    # Patch pipeline components to isolate logic
    sample_invoice = _sample_invoice()
    validated_po = ValidatedPO(po_id="0000227878", vendor_id="V001", vendor_name="GRAINGER", confidence=0.95)
    po_lines = _sample_po_lines()
    line_map = LineMapping(strategy="direct", lines=[LineMappingEntry(po_line=1, amount=75.1)])

    monkeypatch.setattr(pipeline, "detect_vendor", lambda fp, sp: ("GRAINGER", {"extraction": None, "po_identifier": None}))
    monkeypatch.setattr(pipeline, "run_extraction", lambda fp, extra_prompt=None: sample_invoice)
    monkeypatch.setattr(pipeline, "identify_po", lambda invoice, filepath, extra_prompt=None: validated_po)
    monkeypatch.setattr(pipeline, "load_po_lines", lambda po_id: po_lines)
    monkeypatch.setattr(pipeline, "generate_line_mapping", lambda invoice, lines, filepath, extra_prompt=None: line_map)
    monkeypatch.setattr(pipeline, "execute_voucher_entry", lambda page, plan: {"status": "ok", "plan": plan})

    dummy_page = object()
    dummy_file = tmp_path / "dummy.pdf"
    dummy_file.write_text("placeholder")

    result = pipeline.run_v2_voucher(str(dummy_file), dummy_page)
    assert result["status"] == "ok"
    plan = result["plan"]
    assert plan.po.po_id == validated_po.po_id
    assert plan.mapping.lines[0].po_line == 1

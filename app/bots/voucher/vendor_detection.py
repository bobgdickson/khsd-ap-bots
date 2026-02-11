from pathlib import Path

from pydantic import BaseModel

from app.bots.agents.multimodal import extract_to_schema


class VendorDetectionResult(BaseModel):
    vendor_name: str | None = None


def load_special_vendor_prompts() -> dict[str, dict[str, str]]:
    """
    Load vendor-specific prompt text from files under app/bots/prompts/vendor/*.py.
    Each file must define PROMPT_EXTRACTION and PROMPT_PO_IDENTIFIER strings.
    Filename (without extension) is the vendor key (case-insensitive).
    """
    prompts_dir = Path("app/bots/voucher/prompts/vendor")
    prompts: dict[str, dict[str, str]] = {}
    if not prompts_dir.exists():
        return prompts
    import importlib.util

    for path in prompts_dir.glob("*.py"):
        key = path.stem.lower()
        try:
            spec = importlib.util.spec_from_file_location(f"vendor_prompts.{key}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            prompts[key] = {
                "extraction": getattr(mod, "PROMPT_EXTRACTION", ""),
                "po_identifier": getattr(mod, "PROMPT_PO_IDENTIFIER", ""),
            }
        except Exception:
            continue
    return prompts


def detect_vendor(filepath: str, special_prompts: dict[str, dict[str, str]]) -> tuple[str | None, dict[str, str] | None]:
    """
    Light vendor detection using multimodal extract. Returns (vendor_name, vendor_specific_prompt).
    """
    special_list = ", ".join(sorted(special_prompts.keys()))
    base_prompt = "Identify the vendor name from this invoice or return null."
    if special_list:
        base_prompt += f" If the vendor matches any of: {special_list}, return the name exactly as printed."
    try:
        result = extract_to_schema(
            filepath,
            VendorDetectionResult,
            prompt=base_prompt,
        )
        vendor = (result.vendor_name or "").strip()
        prompt_bundle = special_prompts.get(vendor.lower()) if vendor else None
        return vendor, prompt_bundle
    except Exception:
        return None, None

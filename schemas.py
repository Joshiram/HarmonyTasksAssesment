from typing import Optional
from pydantic import BaseModel, validator


class ExtractionResult(BaseModel):
    id: str
    product_line: Optional[str]
    origin_port_code: Optional[str]
    origin_port_name: Optional[str]
    destination_port_code: Optional[str]
    destination_port_name: Optional[str]
    incoterm: Optional[str]
    cargo_weight_kg: Optional[float]
    cargo_cbm: Optional[float]
    is_dangerous: bool = False

    @validator("cargo_weight_kg", pre=True, always=True)
    def round_weight(cls, v):
        if v is None:
            return None
        try:
            return round(float(v), 2)
        except Exception:
            return None

    @validator("cargo_cbm", pre=True, always=True)
    def round_cbm(cls, v):
        if v is None:
            return None
        try:
            return round(float(v), 2)
        except Exception:
            return None

    @validator("incoterm", pre=True, always=True)
    def norm_incoterm(cls, v):
        if v is None:
            return None
        s = str(v).strip().upper()
        return s or None

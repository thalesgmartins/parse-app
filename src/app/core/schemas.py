"""Schemas de Dados."""

from pydantic import BaseModel, field_validator


class CnisCompetencia(BaseModel):
    data_competencia: str
    valor: float

    @field_validator("valor", mode="before")
    @classmethod
    def tratar_moeda_brasileira(cls, v):
        if isinstance(v, str):
            return float(v.replace(".", "").replace(",", "."))
        return v

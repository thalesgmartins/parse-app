"""Schemas de validação e transferência de dados (DTOs)."""

from pydantic import BaseModel, field_validator


class CnisCompetencia(BaseModel):
    """Representação estruturada de uma competência previdenciária e sua remuneração."""

    data_competencia: str
    valor: float | str

    @field_validator("valor", mode="before")
    @classmethod
    def tratar_moeda_brasileira(cls, valor_bruto: float | str) -> float:
        """Converte string monetária brasileira em valor numérico decimal.

        Args:
            valor_bruto: Valor monetário como float ou string formatada em Real.

        Returns:
            Valor monetário normalizado como float.
        """
        if isinstance(valor_bruto, str):
            return float(valor_bruto.replace(".", "").replace(",", "."))
        return float(valor_bruto)

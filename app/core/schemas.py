"""Schemas de validação e transferência de dados (DTOs)."""

from pydantic import BaseModel, Field, field_validator


class CnisCompetencia(BaseModel):
    """Representação estruturada de uma competência previdenciária e sua remuneração.

    Attributes:
        data_competencia: Competência no formato MM/AAAA.
        valor: Valor monetário da remuneração ou salário de contribuição base.
        origem_vinculo: Tipo de vínculo identificado (ex: CLT, Contribuinte Individual).
        indicadores: Lista de códigos de indicadores previdenciários associados.
    """

    data_competencia: str
    valor: float | str
    origem_vinculo: str | None = None
    indicadores: list[str] = Field(default_factory=list)

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

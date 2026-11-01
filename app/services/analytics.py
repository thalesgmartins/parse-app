"""Serviço de cálculo de indicadores e séries gráficas para análise do CNIS."""

from dataclasses import dataclass

from app.database.models import Contribuicao

TETO_INSS_REFERENCIA: float = 7786.02
MESES_LABELS: tuple[str, ...] = (
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
)


@dataclass(frozen=True)
class ItemTabelaAnalise:
    """Representa uma linha enriquecida da tabela de competências do CNIS."""

    indice: int
    data_competencia: str
    ano: str
    valor: float
    variacao_pct: float
    percentual_teto: float
    acima_media: bool


@dataclass(frozen=True)
class CelulaMapaCalor:
    """Representa uma célula mensal na matriz de densidade contributiva."""

    mes_numero: int
    mes_nome: str
    competencia: str
    valor: float
    nivel: int


@dataclass(frozen=True)
class LinhaMapaCalor:
    """Agrupa os 12 meses de um ano específico para o mapa de calor."""

    ano: str
    celulas: list[CelulaMapaCalor]


@dataclass(frozen=True)
class ResumoAnualCnis:
    """Resumo consolidado de contribuições por ano civil."""

    ano: str
    quantidade_meses: int
    media_valor: float
    total_valor: float
    densidade_pct: int


@dataclass(frozen=True)
class PontoGraficoCnis:
    """Ponto coordenado para renderização do gráfico SVG de evolução salarial."""

    competencia: str
    valor: float
    x: float
    y: float


@dataclass(frozen=True)
class SerieGraficoCnis:
    """Estrutura completa de coordenadas SVG para o gráfico de evolução."""

    pontos: list[PontoGraficoCnis]
    caminho_linha: str
    caminho_area: str
    y_media: float
    eixo_y_valores: list[float]
    pico_ponto: PontoGraficoCnis | None


@dataclass(frozen=True)
class PainelAnaliseCnis:
    """Conjunto de KPIs, séries gráficas e tabelas para a tela de estatísticas."""

    total_competencias: int
    tempo_contribuicao: str
    media_salarial: float
    maior_remuneracao: float
    competencia_maior: str
    soma_remuneracoes: float
    variacao_geral_pct: float
    atingiu_teto_count: int
    percentual_teto_medio: float
    periodo_inicio: str
    periodo_fim: str
    itens_tabela: list[ItemTabelaAnalise]
    mapa_calor: list[LinhaMapaCalor]
    resumos_anuais: list[ResumoAnualCnis]
    grafico: SerieGraficoCnis


def formatar_moeda_br(valor: float) -> str:
    """Formata um número de ponto flutuante no padrão monetário brasileiro.

    Args:
        valor: Valor numérico em reais.

    Returns:
        String formatada como '1.234,56'.
    """
    texto = f"{valor:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _extrair_mes_ano(competencia: str) -> tuple[int, str]:
    """Extrai o número do mês (1-12) e o ano (4 dígitos) de 'MM/AAAA'."""
    partes = competencia.strip().split("/")
    if len(partes) == 2 and partes[0].isdigit() and len(partes[1]) == 4:
        mes = max(1, min(12, int(partes[0])))
        return mes, partes[1]
    return 1, "0000"


def _construir_curva_suave(pontos: list[PontoGraficoCnis]) -> tuple[str, str]:
    """Gera os comandos SVG path (linha Bézier suave e área preenchida)."""
    if not pontos:
        return "", ""
    if len(pontos) == 1:
        p = pontos[0]
        linha = f"M 40,{p.y:.1f} L 680,{p.y:.1f}"
        area = f"{linha} L 680,220 L 40,220 Z"
        return linha, area

    comandos: list[str] = [f"M {pontos[0].x:.1f},{pontos[0].y:.1f}"]
    for idx in range(len(pontos) - 1):
        atual = pontos[idx]
        prox = pontos[idx + 1]
        ctrl_x = (atual.x + prox.x) / 2.0
        comandos.append(
            f"C {ctrl_x:.1f},{atual.y:.1f} {ctrl_x:.1f},{prox.y:.1f} {prox.x:.1f},{prox.y:.1f}"
        )

    caminho_linha = " ".join(comandos)
    primeiro_x = pontos[0].x
    ultimo_x = pontos[-1].x
    caminho_area = f"{caminho_linha} L {ultimo_x:.1f},220 L {primeiro_x:.1f},220 Z"
    return caminho_linha, caminho_area


def _gerar_serie_grafico(
    contribuicoes: list[Contribuicao],
    media_salarial: float,
) -> SerieGraficoCnis:
    """Calcula os pontos amostrados e curvas SVG para o histórico salarial."""
    if not contribuicoes:
        return SerieGraficoCnis(
            pontos=[],
            caminho_linha="",
            caminho_area="",
            y_media=125.0,
            eixo_y_valores=[8000.0, 6000.0, 4000.0, 2000.0, 0.0],
            pico_ponto=None,
        )

    max_pontos = 12
    total = len(contribuicoes)
    if total <= max_pontos:
        amostra = list(contribuicoes)
    else:
        indices = {round(i * (total - 1) / (max_pontos - 1)) for i in range(max_pontos)}
        idx_pico = max(range(total), key=lambda i: contribuicoes[i].valor)
        indices.add(idx_pico)
        amostra = [contribuicoes[i] for i in sorted(indices)]

    maior_val = max(c.valor for c in amostra)
    teto_grafico = max(1000.0, maior_val * 1.15)
    eixo_y = [round(teto_grafico * (1.0 - 0.25 * i), 2) for i in range(5)]

    largura_util = 620.0
    x_inicial = 50.0
    y_topo = 30.0
    y_base = 210.0
    altura_util = y_base - y_topo

    qtd = len(amostra)
    pontos: list[PontoGraficoCnis] = []
    for i, item in enumerate(amostra):
        x = (
            x_inicial + (i * largura_util / (qtd - 1))
            if qtd > 1
            else x_inicial + largura_util / 2.0
        )
        proporcao = min(1.0, max(0.0, item.valor / teto_grafico))
        y = y_base - (proporcao * altura_util)
        pontos.append(
            PontoGraficoCnis(
                competencia=item.data_competencia,
                valor=item.valor,
                x=round(x, 1),
                y=round(y, 1),
            )
        )

    prop_media = min(1.0, max(0.0, media_salarial / teto_grafico))
    y_media = round(y_base - (prop_media * altura_util), 1)
    caminho_linha, caminho_area = _construir_curva_suave(pontos)
    pico_ponto = max(pontos, key=lambda p: p.valor) if pontos else None

    return SerieGraficoCnis(
        pontos=pontos,
        caminho_linha=caminho_linha,
        caminho_area=caminho_area,
        y_media=y_media,
        eixo_y_valores=eixo_y,
        pico_ponto=pico_ponto,
    )


def _gerar_mapa_calor_e_resumo(
    contribuicoes: list[Contribuicao],
    maior_remuneracao: float,
) -> tuple[list[LinhaMapaCalor], list[ResumoAnualCnis]]:
    """Constrói a matriz de densidade mensal e os cartões de resumo por ano."""
    por_ano_mes: dict[str, dict[int, float]] = {}
    for c in contribuicoes:
        mes, ano = _extrair_mes_ano(c.data_competencia)
        if ano == "0000":
            continue
        if ano not in por_ano_mes:
            por_ano_mes[ano] = {}
        por_ano_mes[ano][mes] = c.valor

    anos_ordenados = sorted(por_ano_mes.keys(), reverse=True)
    anos_exibidos = sorted(anos_ordenados[:6]) if anos_ordenados else ["2024"]
    referencia_max = max(maior_remuneracao, TETO_INSS_REFERENCIA, 1.0)

    linhas_mapa: list[LinhaMapaCalor] = []
    for ano in anos_exibidos:
        mapa_meses = por_ano_mes.get(ano, {})
        celulas: list[CelulaMapaCalor] = []
        for mes_idx in range(1, 13):
            valor = mapa_meses.get(mes_idx, 0.0)
            if valor <= 0.0:
                nivel = 0
            else:
                razao = valor / referencia_max
                if razao >= 0.80:
                    nivel = 4
                elif razao >= 0.55:
                    nivel = 3
                elif razao >= 0.30:
                    nivel = 2
                else:
                    nivel = 1
            celulas.append(
                CelulaMapaCalor(
                    mes_numero=mes_idx,
                    mes_nome=MESES_LABELS[mes_idx - 1],
                    competencia=f"{mes_idx:02d}/{ano}",
                    valor=valor,
                    nivel=nivel,
                )
            )
        linhas_mapa.append(LinhaMapaCalor(ano=ano, celulas=celulas))

    resumos: list[ResumoAnualCnis] = []
    for ano in anos_ordenados[:6]:
        valores_ano = list(por_ano_mes[ano].values())
        qtd_meses = len(valores_ano)
        soma_ano = sum(valores_ano)
        media_ano = soma_ano / qtd_meses if qtd_meses else 0.0
        densidade = min(100, round((qtd_meses / 12.0) * 100))
        resumos.append(
            ResumoAnualCnis(
                ano=ano,
                quantidade_meses=qtd_meses,
                media_valor=round(media_ano, 2),
                total_valor=round(soma_ano, 2),
                densidade_pct=densidade,
            )
        )

    return linhas_mapa, resumos


def construir_painel_analise(
    contribuicoes: list[Contribuicao],
) -> PainelAnaliseCnis:
    """Consolida métricas, gráficos e tabela enriquecida para a Tela 3.

    Args:
        contribuicoes: Lista de contribuições ordenadas cronologicamente.

    Returns:
        Objeto PainelAnaliseCnis pronto para renderização no template Jinja2.
    """
    total = len(contribuicoes)
    if total == 0:
        mapa_vazio, resumos_vazios = _gerar_mapa_calor_e_resumo([], 0.0)
        return PainelAnaliseCnis(
            total_competencias=0,
            tempo_contribuicao="0a 00m",
            media_salarial=0.0,
            maior_remuneracao=0.0,
            competencia_maior="-",
            soma_remuneracoes=0.0,
            variacao_geral_pct=0.0,
            atingiu_teto_count=0,
            percentual_teto_medio=0.0,
            periodo_inicio="-",
            periodo_fim="-",
            itens_tabela=[],
            mapa_calor=mapa_vazio,
            resumos_anuais=resumos_vazios,
            grafico=_gerar_serie_grafico([], 0.0),
        )

    anos = total // 12
    meses = total % 12
    tempo_str = f"{anos}a {meses:02d}m"

    soma = sum(c.valor for c in contribuicoes)
    media = soma / total
    item_maior = max(contribuicoes, key=lambda c: c.valor)
    primeiro_val = contribuicoes[0].valor
    ultimo_val = contribuicoes[-1].valor
    variacao_geral = (
        ((ultimo_val - primeiro_val) / primeiro_val) * 100.0 if primeiro_val > 0 else 0.0
    )

    limiar_teto = TETO_INSS_REFERENCIA * 0.80
    atingiu_teto = sum(1 for c in contribuicoes if c.valor >= limiar_teto)
    pct_teto_medio = min(100.0, (media / TETO_INSS_REFERENCIA) * 100.0)

    itens_tabela: list[ItemTabelaAnalise] = []
    for idx, c in enumerate(contribuicoes):
        _, ano = _extrair_mes_ano(c.data_competencia)
        if idx == 0 or contribuicoes[idx - 1].valor <= 0:
            var_item = 0.0
        else:
            ant = contribuicoes[idx - 1].valor
            var_item = ((c.valor - ant) / ant) * 100.0
        pct_teto = min(100.0, (c.valor / TETO_INSS_REFERENCIA) * 100.0)
        itens_tabela.append(
            ItemTabelaAnalise(
                indice=idx + 1,
                data_competencia=c.data_competencia,
                ano=ano,
                valor=c.valor,
                variacao_pct=round(var_item, 1),
                percentual_teto=round(pct_teto, 1),
                acima_media=c.valor >= media,
            )
        )

    mapa_calor, resumos_anuais = _gerar_mapa_calor_e_resumo(
        contribuicoes,
        item_maior.valor,
    )
    grafico = _gerar_serie_grafico(contribuicoes, media)

    return PainelAnaliseCnis(
        total_competencias=total,
        tempo_contribuicao=tempo_str,
        media_salarial=round(media, 2),
        maior_remuneracao=round(item_maior.valor, 2),
        competencia_maior=item_maior.data_competencia,
        soma_remuneracoes=round(soma, 2),
        variacao_geral_pct=round(variacao_geral, 1),
        atingiu_teto_count=atingiu_teto,
        percentual_teto_medio=round(pct_teto_medio, 1),
        periodo_inicio=contribuicoes[0].data_competencia,
        periodo_fim=contribuicoes[-1].data_competencia,
        itens_tabela=itens_tabela,
        mapa_calor=mapa_calor,
        resumos_anuais=resumos_anuais,
        grafico=grafico,
    )

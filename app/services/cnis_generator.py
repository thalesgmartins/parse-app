"""Módulo para geração sintética de extratos CNIS com leiaute oficial do INSS.

Produz documentos PDF em formato idêntico ao emitido pelo portal Meu INSS,
preservando o leiaute (A4 Paisagem, JasperReports), tipografia, cabeçalhos,
tabelas de remunerações e consolidações anuais com dados fictícios.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

_LOGGER = logging.getLogger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN_LEFT = 20.0
MARGIN_RIGHT = 822.0
CONTENT_WIDTH = MARGIN_RIGHT - MARGIN_LEFT  # 802.0 pt
COLOR_BORDER = HexColor("#333333")
COLOR_HEADER_BG = HexColor("#F5F5F5")


@dataclass
class CnisCompetenciaFicticia:
    """Representa uma competência mensal com respectivo valor salarial."""

    mes_ano: str
    valor: float
    indicador: str | None = None


@dataclass
class CnisVinculoFicticio:
    """Representa um vínculo empregatício no extrato previdenciário."""

    seq: int
    nit: str
    codigo_emp: str
    origem_vinculo: str
    matricula: str
    tipo_filiado: str
    data_inicio: str
    data_fim: str | None
    ult_remun: str | None
    indicador_vinculo: str | None = None
    competencias: list[CnisCompetenciaFicticia] = field(default_factory=list)


@dataclass
class CnisSeguradoFicticio:
    """Perfil cadastral completo do segurado para geração do extrato."""

    nome: str
    cpf: str
    nit: str
    data_nascimento: str
    nome_mae: str
    vinculos: list[CnisVinculoFicticio] = field(default_factory=list)


def formatar_moeda_br(valor: float) -> str:
    """Formata valor decimal no padrão monetário brasileiro (ex: 2.450,00).

    Args:
        valor: Valor numérico a ser formatado.

    Returns:
        String formatada com ponto como milhar e vírgula como decimal.
    """
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_cpf_ficticio(base_nove_digitos: str = "715428930") -> str:
    """Gera um CPF sintético válido com dígitos verificadores calculados.

    Args:
        base_nove_digitos: Primeiros 9 dígitos numéricos base.

    Returns:
        CPF formatado no padrão 000.000.000-00.
    """
    numeros = [int(char) for char in base_nove_digitos if char.isdigit()][:9]
    while len(numeros) < 9:
        numeros.append(0)

    soma1 = sum(num * (10 - idx) for idx, num in enumerate(numeros))
    resto1 = soma1 % 11
    dig1 = 0 if resto1 < 2 else 11 - resto1
    numeros.append(dig1)

    soma2 = sum(num * (11 - idx) for idx, num in enumerate(numeros))
    resto2 = soma2 % 11
    dig2 = 0 if resto2 < 2 else 11 - resto2
    numeros.append(dig2)

    digitos_str = "".join(str(num) for num in numeros)
    return f"{digitos_str[:3]}.{digitos_str[3:6]}.{digitos_str[6:9]}-{digitos_str[9:]}"


def criar_perfil_ficticio(
    nome: str = "CARLOS EDUARDO SILVA SANTOS",
    cpf: str | None = None,
    nit: str = "270.86941.72-2",
    data_nascimento: str = "14/08/1988",
    nome_mae: str = "MARIA HELENA DA SILVA SANTOS",
    ano_inicio: int = 2015,
    ano_fim: int = 2026,
    salario_base: float = 2400.0,
) -> CnisSeguradoFicticio:
    """Cria perfil fictício com múltiplos empregadores e evolução salarial.

    Args:
        nome: Nome completo fictício do filiado.
        cpf: CPF formatado opcional; se None, calcula automaticamente.
        nit: NIT formatado do trabalhador.
        data_nascimento: Data de nascimento DD/MM/AAAA.
        nome_mae: Nome completo da genitora.
        ano_inicio: Ano de início do primeiro vínculo.
        ano_fim: Ano final da série histórica.
        salario_base: Salário de partida para cálculo da progressão.

    Returns:
        Instância preenchida de CnisSeguradoFicticio.
    """
    cpf_final = cpf if cpf else gerar_cpf_ficticio("345441508")
    segurado = CnisSeguradoFicticio(
        nome=nome,
        cpf=cpf_final,
        nit=nit,
        data_nascimento=data_nascimento,
        nome_mae=nome_mae,
    )

    empresas_catalogo = [
        ("93.070.159", "ALPHA TECNOLOGIA E SERVICOS S.A.", "70133"),
        ("15.436.940", "BETA CONSULTORIA DE SISTEMAS LTDA", "40921"),
        ("48.912.304", "DELTA INOVACOES DIGITAIS S.A.", "82015"),
    ]

    total_anos = max(1, ano_fim - ano_inicio + 1)
    anos_por_empresa = max(1, math.ceil(total_anos / len(empresas_catalogo)))

    ano_atual_iter = ano_inicio
    seq = 1
    salario_corrente = salario_base

    for cnpj, razao, matricula in empresas_catalogo:
        if ano_atual_iter > ano_fim:
            break

        ano_limite = min(ano_fim, ano_atual_iter + anos_por_empresa - 1)
        data_inicio = f"01/01/{ano_atual_iter}"
        eh_ultimo = ano_limite == ano_fim
        data_fim = None if eh_ultimo else f"31/12/{ano_limite}"
        ult_remun = f"08/{ano_fim}" if eh_ultimo else f"12/{ano_limite}"

        vinculo = CnisVinculoFicticio(
            seq=seq,
            nit=nit,
            codigo_emp=cnpj,
            origem_vinculo=razao,
            matricula=matricula,
            tipo_filiado="Empregado",
            data_inicio=data_inicio,
            data_fim=data_fim,
            ult_remun=ult_remun,
            indicador_vinculo="IREM-INDPEND" if seq == 1 else None,
        )

        for ano in range(ano_atual_iter, ano_limite + 1):
            mes_limite = 8 if (eh_ultimo and ano == ano_fim) else 12
            for mes in range(1, mes_limite + 1):
                vinculo.competencias.append(
                    CnisCompetenciaFicticia(
                        mes_ano=f"{mes:02d}/{ano}",
                        valor=round(salario_corrente, 2),
                    )
                )
            salario_corrente = round(salario_corrente * 1.075, 2)

        segurado.vinculos.append(vinculo)
        seq += 1
        ano_atual_iter = ano_limite + 1

    return segurado


class _NumberedCanvas(canvas.Canvas):
    """Canvas em duas passagens para numeração precisa 'Página X de Y'."""

    def __init__(
        self,
        filename: str,
        pagesize: tuple[float, float] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(filename, pagesize=pagesize, **kwargs)  # type: ignore[arg-type]
        self._saved_page_states: list[dict[str, object]] = []

    def showPage(self) -> None:
        """Armazena o estado da página atual para segunda passagem."""
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # type: ignore[attr-defined]

    def save(self) -> None:
        """Desenha a numeração total em todas as páginas gravadas."""
        total_paginas = len(self._saved_page_states)
        for estado in self._saved_page_states:
            self.__dict__.update(estado)
            self._desenhar_numero_pagina(total_paginas)
            super().showPage()
        super().save()

    def _desenhar_numero_pagina(self, total_paginas: int) -> None:
        """Insere o texto de paginação no cabeçalho superior direito."""
        self.setFont("Helvetica", 8)
        self.setFillColorRGB(0, 0, 0)
        self.drawRightString(
            MARGIN_RIGHT,
            PAGE_HEIGHT - 26.0,
            f"Página {self.getPageNumber()} de {total_paginas}",
        )


class CnisPdfBuilder:
    """Construtor visual de extratos CNIS com desenho vetorial ReportLab."""

    def __init__(
        self,
        caminho_saida: Path | str,
        segurado: CnisSeguradoFicticio,
        data_emissao: str | None = None,
    ) -> None:
        """Inicializa o construtor com o segurado e arquivo de destino.

        Args:
            caminho_saida: Arquivo PDF onde o documento será gerado.
            segurado: Dados cadastrais e vínculos a serem impressos.
            data_emissao: Data e hora de emissão no cabeçalho.
        """
        self.caminho = Path(caminho_saida)
        self.segurado = segurado
        self.data_emissao = data_emissao or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.canvas = _NumberedCanvas(
            str(self.caminho),
            pagesize=landscape(A4),
        )

    def construir(self) -> Path:
        """Executa a montagem e geração física do documento PDF.

        Returns:
            Path do arquivo PDF final gravado no disco.
        """
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._desenhar_documento()
        self.canvas.save()
        _LOGGER.info("Extrato CNIS gerado com sucesso em: %s", self.caminho)
        return self.caminho

    def _desenhar_documento(self) -> None:
        """Orquestra as páginas de vínculos e a página final consolidada."""
        vinculos = self.segurado.vinculos

        for vinculo in vinculos:
            self._desenhar_pagina_vinculo(vinculo)

        self._desenhar_pagina_consolidada()

    def _desenhar_pagina_vinculo(self, vinculo: CnisVinculoFicticio) -> None:
        """Renderiza uma página contendo um vínculo e suas remunerações."""
        c = self.canvas
        self._desenhar_cabecalho_pagina()
        self._desenhar_box_filiado()

        # Section: Relações Previdenciárias
        y_rel_top = 432.0
        y_rel_bottom = 68.0
        h_rel = y_rel_top - y_rel_bottom  # 364.0 pt
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=y_rel_bottom,
            width=CONTENT_WIDTH,
            height=h_rel,
            title="Relações Previdenciárias",
        )

        # Sub-box Vínculo Cabeçalho
        y_vinc = 376.0
        c.setLineWidth(0.5)
        c.setStrokeColor(COLOR_BORDER)
        c.rect(30.0, y_vinc, 782.0, 44.0, stroke=1, fill=0)

        # Linha títulos da tabela do vínculo
        c.setFillColor(COLOR_HEADER_BG)
        c.rect(30.5, y_vinc + 22.0, 781.0, 21.5, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(34.0, y_vinc + 28.0, "Seq.")
        c.drawString(60.0, y_vinc + 28.0, "NIT")
        c.drawString(145.0, y_vinc + 28.0, "Código Emp.")
        c.drawString(225.0, y_vinc + 28.0, "Origem do Vínculo")
        c.drawString(450.0, y_vinc + 33.0, "Matrícula do")
        c.drawString(450.0, y_vinc + 24.0, "Trabalhador")
        c.drawString(530.0, y_vinc + 33.0, "Tipo Filiado no")
        c.drawString(530.0, y_vinc + 24.0, "Vínculo")
        c.drawString(640.0, y_vinc + 28.0, "Data Início")
        c.drawString(705.0, y_vinc + 28.0, "Data Fim")
        c.drawString(760.0, y_vinc + 28.0, "Últ. Remun.")

        # Linha de dados do vínculo
        c.setFont("Helvetica", 8)
        c.drawString(38.0, y_vinc + 8.0, str(vinculo.seq))
        c.drawString(60.0, y_vinc + 8.0, vinculo.nit)
        c.drawString(145.0, y_vinc + 8.0, vinculo.codigo_emp)
        c.drawString(225.0, y_vinc + 8.0, vinculo.origem_vinculo[:40])
        c.drawString(450.0, y_vinc + 8.0, vinculo.matricula)
        c.drawString(530.0, y_vinc + 8.0, vinculo.tipo_filiado)
        c.drawString(640.0, y_vinc + 8.0, vinculo.data_inicio)
        c.drawString(705.0, y_vinc + 8.0, vinculo.data_fim or "")
        c.drawString(760.0, y_vinc + 8.0, vinculo.ult_remun or "")

        # Indicador de pendência se houver
        if vinculo.indicador_vinculo:
            c.setFont("Helvetica", 8)
            c.drawString(
                35.0,
                y_vinc - 11.0,
                f"Indicadores: {vinculo.indicador_vinculo}",
            )

        # Sub-box Remunerações
        y_remun_box = 78.0
        h_remun_box = 274.0
        self._draw_groupbox(
            x=30.0,
            y=y_remun_box,
            width=782.0,
            height=h_remun_box,
            title="Remunerações",
        )

        # Cabeçalho das 3 colunas de remunerações
        y_remun_hdr = y_remun_box + h_remun_box - 20.0
        c.setFont("Helvetica-Bold", 8)
        c.drawString(42.0, y_remun_hdr, "Competência")
        c.drawString(132.0, y_remun_hdr, "Remuneração")
        c.drawString(220.0, y_remun_hdr, "Indicadores")

        c.drawString(305.0, y_remun_hdr, "Competência")
        c.drawString(395.0, y_remun_hdr, "Remuneração")
        c.drawString(483.0, y_remun_hdr, "Indicadores")

        c.drawString(568.0, y_remun_hdr, "Competência")
        c.drawString(658.0, y_remun_hdr, "Remuneração")
        c.drawString(746.0, y_remun_hdr, "Indicadores")

        # Dados das competências (3 colunas por linha)
        y_linha = y_remun_hdr - 14.0
        c.setFont("Helvetica", 8.5)

        competencias = vinculo.competencias
        for idx in range(0, len(competencias), 3):
            if y_linha < y_remun_box + 10.0:
                break

            bloco = competencias[idx : idx + 3]

            # Coluna 1
            c.drawString(42.0, y_linha, bloco[0].mes_ano)
            c.drawRightString(
                195.0,
                y_linha,
                formatar_moeda_br(bloco[0].valor),
            )
            if bloco[0].indicador:
                c.drawString(220.0, y_linha, bloco[0].indicador)

            # Coluna 2
            if len(bloco) > 1:
                c.drawString(305.0, y_linha, bloco[1].mes_ano)
                c.drawRightString(
                    458.0,
                    y_linha,
                    formatar_moeda_br(bloco[1].valor),
                )
                if bloco[1].indicador:
                    c.drawString(483.0, y_linha, bloco[1].indicador)

            # Coluna 3
            if len(bloco) > 2:
                c.drawString(568.0, y_linha, bloco[2].mes_ano)
                c.drawRightString(
                    721.0,
                    y_linha,
                    formatar_moeda_br(bloco[2].valor),
                )
                if bloco[2].indicador:
                    c.drawString(746.0, y_linha, bloco[2].indicador)

            y_linha -= 13.0

        self._desenhar_disclaimer_legal()
        c.showPage()

    def _desenhar_pagina_consolidada(self) -> None:
        """Gera a página de fechamento com consolidações, QR code e legendas."""
        c = self.canvas
        self._desenhar_cabecalho_pagina()
        self._desenhar_box_filiado()

        # Dicionário de anos consolidados
        dados_anuais: dict[int, dict[int, float]] = {}
        for vinculo in self.segurado.vinculos:
            for item in vinculo.competencias:
                partes = item.mes_ano.split("/")
                if len(partes) == 2:
                    mes, ano = int(partes[0]), int(partes[1])
                    dados_anuais.setdefault(ano, {})[mes] = item.valor

        anos_ordenados = sorted(dados_anuais.keys())
        altura_tabela = max(90.0, 28.0 + len(anos_ordenados) * 13.0)

        # Section: Valores Consolidados por Ano Civil
        y_consol_top = 432.0
        y_consol = y_consol_top - altura_tabela
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=y_consol,
            width=CONTENT_WIDTH,
            height=altura_tabela,
            title="Valores Consolidados por Ano Civil",
        )

        # Cabeçalho da tabela de meses
        y_hdr = y_consol + altura_tabela - 18.0
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(35.0, y_hdr, "Ano")
        meses_abrev = [
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
        ]
        for idx, m_nome in enumerate(meses_abrev):
            c.drawString(110.0 + idx * 58.0, y_hdr, m_nome)

        # Linhas anuais
        y_linha_ano = y_hdr - 14.0
        for ano in anos_ordenados:
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(35.0, y_linha_ano, str(ano))
            c.setFont("Helvetica", 7.5)
            for m_num in range(1, 13):
                valor = dados_anuais[ano].get(m_num)
                if valor is not None:
                    c.drawRightString(
                        140.0 + (m_num - 1) * 58.0,
                        y_linha_ano,
                        formatar_moeda_br(valor),
                    )
            y_linha_ano -= 13.0

        # Section: Legenda de Indicadores
        h_legenda = 65.0
        y_legenda = y_consol - 12.0 - h_legenda
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=y_legenda,
            width=CONTENT_WIDTH,
            height=h_legenda,
            title="Legenda de Indicadores",
        )
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(32.0, y_legenda + 45.0, "Indicador")
        c.drawString(130.0, y_legenda + 45.0, "Descrição")
        c.drawString(420.0, y_legenda + 45.0, "Indicador")
        c.drawString(550.0, y_legenda + 45.0, "Descrição")

        c.setFont("Helvetica", 7.5)
        c.drawString(32.0, y_legenda + 28.0, "IREM-INDPEND")
        c.drawString(
            130.0,
            y_legenda + 28.0,
            "Remunerações com indicadores/pendências",
        )
        c.drawString(420.0, y_legenda + 28.0, "PSC-MEN-SM-EC103")
        c.drawString(
            550.0,
            y_legenda + 28.0,
            "Pendência em competência com valor menor que o mínimo.",
        )

        # Section: Autenticidade com QR Code
        h_auth = 75.0
        y_auth = y_legenda - 10.0 - h_auth
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=y_auth,
            width=CONTENT_WIDTH,
            height=h_auth,
        )

        # QR Code vetorial
        self._desenhar_qr_code(32.0, y_auth + 8.0, 58.0)

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 8)
        c.drawString(
            110.0,
            y_auth + 48.0,
            "Você pode conferir a autenticidade do documento em",
        )
        c.drawString(
            110.0,
            y_auth + 34.0,
            "https://meu.inss.gov.br/central/#/autenticidade",
        )
        c.drawString(
            110.0,
            y_auth + 20.0,
            "com o código 2610061WQLIV2QYLLS-915",
        )

        self._desenhar_disclaimer_legal()
        c.showPage()

    def _desenhar_cabecalho_pagina(self) -> None:
        """Desenha o cabeçalho oficial com logotipo do INSS e títulos."""
        c = self.canvas

        # Logotipo do INSS
        caminhos_logo = [
            Path("app/assets/inss_logo.png"),
            Path("script/assets/inss_logo.png"),
        ]
        logo_aplicado = False
        for caminho in caminhos_logo:
            if caminho.exists():
                c.drawImage(
                    str(caminho),
                    MARGIN_LEFT,
                    PAGE_HEIGHT - 20.0 - 43.0,
                    width=129.0,
                    height=43.0,
                    mask="auto",
                )
                logo_aplicado = True
                break

        if not logo_aplicado:
            c.setFont("Helvetica-Bold", 18)
            c.drawString(MARGIN_LEFT, PAGE_HEIGHT - 45.0, "INSS")

        # Títulos
        c.setFont("Helvetica-Bold", 12)
        c.drawString(160.0, PAGE_HEIGHT - 35.0, "INSS")
        c.drawString(
            160.0,
            PAGE_HEIGHT - 49.0,
            "CNIS - Cadastro Nacional de Informações Sociais",
        )
        c.drawString(160.0, PAGE_HEIGHT - 63.0, "Extrato Previdenciário")

        # Data e Hora de emissão
        c.setFont("Helvetica", 8)
        c.drawRightString(
            MARGIN_RIGHT,
            PAGE_HEIGHT - 70.0,
            self.data_emissao,
        )

    def _desenhar_box_filiado(self) -> None:
        """Desenha o box com dados cadastrais e identificação do segurado."""
        c = self.canvas
        box_y = PAGE_HEIGHT - 150.0
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=box_y,
            width=CONTENT_WIDTH,
            height=50.0,
            title="Identificação do Filiado",
        )

        c.setFillColorRGB(0, 0, 0)
        # Linha 1: NIT, CPF e Nome
        c.setFont("Helvetica-Bold", 9)
        c.drawString(32.0, box_y + 30.0, "NIT:")
        c.setFont("Helvetica", 9)
        c.drawString(55.0, box_y + 30.0, self.segurado.nit)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(160.0, box_y + 30.0, "CPF:")
        c.setFont("Helvetica", 9)
        c.drawString(185.0, box_y + 30.0, self.segurado.cpf)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(290.0, box_y + 30.0, "Nome:")
        c.setFont("Helvetica", 9)
        c.drawString(325.0, box_y + 30.0, self.segurado.nome)

        # Linha 2: Data de Nascimento e Nome da Mãe
        c.setFont("Helvetica-Bold", 9)
        c.drawString(32.0, box_y + 12.0, "Data de nascimento:")
        c.setFont("Helvetica", 9)
        c.drawString(135.0, box_y + 12.0, self.segurado.data_nascimento)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(240.0, box_y + 12.0, "Nome da mãe:")
        c.setFont("Helvetica", 9)
        c.drawString(310.0, box_y + 12.0, self.segurado.nome_mae)

    def _desenhar_disclaimer_legal(self) -> None:
        """Insere o aviso legal oficial na borda inferior da página."""
        c = self.canvas
        self._draw_groupbox(
            x=MARGIN_LEFT,
            y=20.0,
            width=CONTENT_WIDTH,
            height=38.0,
        )
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 7.5)
        c.drawString(
            25.0,
            46.0,
            "O INSS poderá rever a qualquer tempo as informações constantes "
            "deste extrato, observados os arts.19 ao 19-F do RPS aprovado "
            "pelo Decreto 3.048/99.",
        )
        c.drawString(
            25.0,
            36.0,
            "O segurado somente terá reconhecida como tempo de contribuição ao "
            "RGPS a competência cujo valor consolidado seja igual ou superior "
            "ao salário mínimo, sendo assegurados os ajustes de complementação, "
            "utilização",
        )
        c.drawString(
            25.0,
            26.0,
            "ou agrupamento, conforme o caso, de acordo com o § 14 do art.195 "
            "da CF/1988 e art.29 da EC 103/2019.",
        )

    def _desenhar_qr_code(self, pos_x: float, pos_y: float, tamanho: float) -> None:
        """Renderiza um QR Code vetorial funcional no canvas."""
        widget = QrCodeWidget("https://meu.inss.gov.br/central/#/autenticidade")
        bounds = widget.getBounds()
        largura_original = bounds[2] - bounds[0]
        altura_original = bounds[3] - bounds[1]
        desenho = Drawing(
            tamanho,
            tamanho,
            transform=[
                tamanho / largura_original,
                0,
                0,
                tamanho / altura_original,
                0,
                0,
            ],
        )
        desenho.add(widget)
        renderPDF.draw(desenho, self.canvas, pos_x, pos_y)

    def _draw_groupbox(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        title: str | None = None,
    ) -> None:
        """Desenha caixa de agrupamento com efeito legend recortado no topo."""
        c = self.canvas
        c.setLineWidth(0.6)
        c.setStrokeColor(COLOR_BORDER)
        c.setFillColorRGB(1, 1, 1)
        c.rect(x, y, width, height, stroke=1, fill=0)

        if title:
            largura_texto = c.stringWidth(title, "Helvetica-Bold", 9) + 14.0
            pos_tx = x + 16.0
            pos_ty = y + height - 6.0
            c.rect(pos_tx, pos_ty, largura_texto, 12.0, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(pos_tx + 7.0, pos_ty + 2.5, title)
        else:
            c.setFillColorRGB(0, 0, 0)


def gerar_pdf_cnis(
    segurado: CnisSeguradoFicticio,
    caminho_saida: Path | str,
    data_emissao: str | None = None,
) -> Path:
    """Função pública de alto nível para geração do arquivo PDF do CNIS.

    Args:
        segurado: Entidade de dados com todas as informações fictícias.
        caminho_saida: Destino do arquivo PDF gerado.
        data_emissao: Timestamp opcional de emissão.

    Returns:
        Path para o arquivo gerado e pronto para consumo.
    """
    builder = CnisPdfBuilder(
        caminho_saida=caminho_saida,
        segurado=segurado,
        data_emissao=data_emissao,
    )
    return builder.construir()

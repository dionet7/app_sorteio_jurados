from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit

def gerar_relatorio_pdf(sorteados, impedidos, nao_sorteados, nome_arquivo="relatorio_jurados.pdf", nome_comarca=None):
    c = canvas.Canvas(nome_arquivo, pagesize=A4)
    largura, altura = A4

    # Margens e layout
    margem_esq = 2 * cm
    margem_sup = 2 * cm
    margem_inf = 2 * cm
    largura_util = largura - 2 * margem_esq

    linha_altura = 14
    fonte_titulo = ("Helvetica-Bold", 16)
    fonte_secao  = ("Helvetica-Bold", 14)
    fonte_texto  = ("Helvetica", 11)
    fonte_sub    = ("Helvetica", 12)

    x = margem_esq
    y = altura - margem_sup

    def quebra_pagina():
        nonlocal y
        c.showPage()
        y = altura - margem_sup
        c.setFont(fonte_texto[0], fonte_texto[1])

    def desenha_titulo_central(texto, subtitulo=None):
        nonlocal y
        # título
        c.setFont(fonte_titulo[0], fonte_titulo[1])
        c.drawCentredString(largura / 2, y, texto)
        y -= linha_altura

        # subtítulo (ex.: COMARCA DE XXXXX)
        if subtitulo:
            c.setFont(fonte_sub[0], fonte_sub[1])
            # quebra o subtítulo caso seja muito longo
            linhas = simpleSplit(subtitulo, fonte_sub[0], fonte_sub[1], largura_util)
            for t in linhas:
                c.drawCentredString(largura / 2, y, t)
                y -= linha_altura

        # espaço após o cabeçalho
        y -= linha_altura
        c.setFont(fonte_texto[0], fonte_texto[1])

    def desenha_secao(texto):
        nonlocal y
        if y < (margem_inf + 2 * linha_altura):
            quebra_pagina()
        c.setFont(fonte_secao[0], fonte_secao[1])
        c.drawString(x, y, texto)
        y -= linha_altura
        c.setFont(fonte_texto[0], fonte_texto[1])

    def escrever_lista(lista, com_motivo=False):
        """
        Escreve cada item com quebra automática por largura.
        Se com_motivo=True, inclui motivo/data do impedimento (quando existentes).
        """
        nonlocal y
        c.setFont(fonte_texto[0], fonte_texto[1])

        for j in lista:
            prof = getattr(j, "profissao", None)
            # Nome (Profissão), resto do endereço...
            if prof:
                cabeca = f"{j.nome} ({prof})"
            else:
                cabeca = f"{j.nome}"
            linha = f"{cabeca}, {j.endereco}, {j.numero}, {j.bairro}, {j.cidade}"
                    # linha = f"{j.nome}, {j.endereco}, {j.numero}, {j.bairro}, {j.cidade}"

            if com_motivo:
                motivo = getattr(j, "motivo_impedimento", None)
                data_imp = getattr(j, "data_impedimento", None)
                if motivo and str(motivo).strip():
                    extra = f" — Motivo: {motivo}"
                else:
                    extra = " — Motivo: não informado"
                if data_imp:
                    try:
                        extra += f" (em {data_imp.strftime('%d/%m/%Y')})"
                    except Exception:
                        extra += f" (em {data_imp})"
                linha += extra

            linhas = simpleSplit(linha, fonte_texto[0], fonte_texto[1], largura_util)
            for trecho in linhas:
                if y < (margem_inf + linha_altura):
                    quebra_pagina()
                c.drawString(x, y, trecho)
                y -= linha_altura

    # ----- Cabeçalho
    subtitulo = None
    if nome_comarca:
        subtitulo = f"{str(nome_comarca).upper()}"
    desenha_titulo_central("RELATÓRIO DE JURADOS", subtitulo)

    # 1) Sorteados
    desenha_secao("1. Jurados já sorteados:")
    escrever_lista(sorteados, com_motivo=False)

    # 2) Impedidos (com motivo!)
    y -= linha_altura
    desenha_secao("2. Jurados impedidos:")
    escrever_lista(impedidos, com_motivo=True)

    # 3) Não sorteados
    y -= linha_altura
    desenha_secao("3. Jurados não sorteados:")
    escrever_lista(nao_sorteados, com_motivo=False)

    c.save()
    print(f"✅ Relatório PDF gerado com sucesso: {nome_arquivo}")
    return nome_arquivo

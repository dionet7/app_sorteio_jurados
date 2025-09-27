# from database import Session, Jurado

# def importar_jurados_arquivo(caminho_arquivo):
#     session = Session()
#     with open(caminho_arquivo, "r", encoding="utf-8") as file:
#         for linha in file:
#             partes = linha.strip().split(",")
#             if len(partes) == 5:
#                 nome, endereco, numero, bairro, cidade = partes
#                 jurado = Jurado(
#                     nome=nome.strip(),
#                     endereco=endereco.strip(),
#                     numero=numero.strip(),
#                     bairro=bairro.strip(),
#                     cidade=cidade.strip()
#                 )
#                 session.add(jurado)
#     session.commit()
#     session.close()
#     print(f"✅ Jurados importados de {caminho_arquivo} com sucesso!")
from database import Session, Jurado

def atualizar_jurados_multiplos(lista_arquivos):
    """
    Recebe lista de tuplas (nome_arquivo/cidade, conteudo_txt).
    Apaga todos os jurados e cadastra os novos.
    Formatos aceitos por linha:
      - 5 colunas: Nome, Endereço, Número, Bairro, Cidade
      - 6 colunas: Nome, Endereço, Número, Bairro, Cidade, Profissão
    """
    session = Session()
    session.query(Jurado).delete()
    session.commit()

    for nome_arquivo, conteudo in lista_arquivos:
        linhas = conteudo.strip().split("\n")
        for linha in linhas:
            partes = [p.strip() for p in linha.strip().split(",")]

            if len(partes) >= 5:
                nome, endereco, numero, bairro, cidade = partes[:5]
                profissao = partes[5].strip() if len(partes) >= 6 else None

                jurado = Jurado(
                    nome=nome,
                    endereco=endereco,
                    numero=numero,
                    bairro=bairro,
                    cidade=cidade,
                    profissao=(profissao or None)
                )
                session.add(jurado)
            # (opcional) else: log/avisar que a linha foi ignorada

    session.commit()
    session.close()
    print("✅ Jurados atualizados com sucesso!")



# ✅ Teste manual (roda apenas se executar este arquivo diretamente)
if __name__ == "__main__":
    try:
        with open("jurados_inhuma.txt", "r", encoding="utf-8") as f1:
            conteudo_inhuma = f1.read()

        with open("jurados_ipiranga.txt", "r", encoding="utf-8") as f2:
            conteudo_ipiranga = f2.read()

        lista = [
            ("Inhuma", conteudo_inhuma),
            ("Ipiranga", conteudo_ipiranga)
        ]

        atualizar_jurados_multiplos(lista)
        print("✅ Teste concluído com sucesso.")
    except FileNotFoundError:
        print("⚠️ Arquivo de jurados não encontrado. Verifique os nomes e caminhos.")


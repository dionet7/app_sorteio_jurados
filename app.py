import io
import hashlib
import datetime
import pandas as pd
import streamlit as st
from database import Session, Jurado, Sorteio
from database import comarca_existe, obter_comarca, Comarca
import random
import datetime
from sqlalchemy import or_
from gerar_ata import gerar_ata
from importar_jurados import atualizar_jurados_multiplos
from gerar_relatorio import gerar_relatorio_pdf

def cidades_da_comarca():
    from database import obter_comarca
    comarca = obter_comarca()
    if not comarca or not comarca.cidades:
        return []
    # remove espaços extras e linhas vazias
    return [c.strip() for c in comarca.cidades.split(",") if c.strip()]


# Configurações iniciais

st.set_page_config(page_title="Sistema de Sorteio de Jurados", layout="wide")
# ==== LOGIN SIMPLES COM HASHING DE SENHA ====
usuarios_validos = {
    "admin": hashlib.sha256("1234".encode()).hexdigest(),
    "usuario1": hashlib.sha256("senha1".encode()).hexdigest(),
    "usuario2": hashlib.sha256("senha2".encode()).hexdigest(),
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'usuario_logado' not in st.session_state:
    st.session_state.usuario_logado = ""

# Sidebar com status e logout (fica visível depois do login)
with st.sidebar:
    st.markdown("## 👤 Sessão")
    if st.session_state.autenticado:
        st.write(f"Logado como: **{st.session_state.usuario_logado}**")
        if st.button("Sair"):
            # limpa sessão e volta para tela de login
            st.session_state.clear()
            st.rerun()
    else:
        st.write("Não autenticado.")

# Gatekeeper: se não autenticado, mostra login e bloqueia o resto do app
if not st.session_state.autenticado:
    st.title("Login Seguro")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", key="botao_entrar"):
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        if usuario in usuarios_validos and senha_hash == usuarios_validos[usuario]:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = usuario
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    st.stop()  # impede que o restante da página seja renderizado sem login




st.title("🎯 Sistema de Sorteio de Jurados")

tabs = st.tabs(["📝 Cadastro", "🎲 Sorteio", "👥 Visualização", "⚙️ Atualização", "📄 Relatório PDF"])

if not comarca_existe():
    st.warning("⚠️ Nenhuma comarca cadastrada. Cadastre a comarca para começar.")

    with st.form("form_configuracao_inicial"):
        nome_comarca = st.text_input("Nome da Comarca")
        cidades_comarca = st.text_input("Cidades associadas (separadas por vírgula)", placeholder="Ex: Inhuma,Ipiranga")
        confirmar = st.form_submit_button("Salvar")

        if confirmar:
            if nome_comarca.strip() and cidades_comarca.strip():
                session = Session()
                comarca = Comarca(
                    nome=nome_comarca.strip(),
                    cidades=cidades_comarca.strip()
                )
                session.add(comarca)
                session.commit()
                session.close()
                st.success("✅ Comarca cadastrada com sucesso!")
                st.rerun() # st.experimental_rerun()
            else:
                st.error("❌ Preencha todos os campos.")
    st.stop()  # Interrompe o app até cadastrar a comarca

# FUNÇÕES PRINCIPAIS DO SISTEMA exportação, sorteio, impedir
def exportar_jurados_csv():
    """Gera um CSV com todos os jurados atuais (compatível com Excel)."""
    session = Session()
    jurados = session.query(Jurado).all()
    session.close()

    linhas = []
    for j in jurados:
        linhas.append({
            "id": j.id,
            "nome": j.nome or "",
            "profissao": j.profissao or "", 
            "endereco": j.endereco or "",
            "numero": j.numero or "",
            "bairro": j.bairro or "",
            "cidade": (j.cidade or "").strip(),
            "impedido": bool(j.impedido),
            "motivo_impedimento": getattr(j, "motivo_impedimento", "") or "",
            "data_impedimento": j.data_impedimento.strftime("%Y-%m-%d") if getattr(j, "data_impedimento", None) else "",
            "sorteios_passados": j.sorteios_passados or 0,
            "foi_sorteado": bool(getattr(j, "foi_sorteado", False)),
        })

    df = pd.DataFrame(linhas)
    # UTF-8 com BOM para abrir no Excel sem acentuação quebrada
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig")
    return csv_bytes


def sortear_jurados(cidade_processo):
    session = Session()

    # 1) Jurados disponíveis: não impedidos e que NÃO participaram do último sorteio
    jurados_disponiveis = session.query(Jurado).filter(
        Jurado.impedido == False,
        Jurado.participou_ultimo == False
    ).all()

    # 2) Separar por cidade do processo x outras cidades
    da_cidade = [j for j in jurados_disponiveis if j.cidade == cidade_processo]
    outra_cidade = [j for j in jurados_disponiveis if j.cidade != cidade_processo]

    n_da_cidade = min(13, len(da_cidade))
    n_outra = min(25 - n_da_cidade, len(outra_cidade))

    if len(da_cidade) < n_da_cidade or len(outra_cidade) < n_outra:
        st.error("⚠️ Não há jurados suficientes para realizar o sorteio completo.")
        session.close()
        return [], []

    titulares = random.sample(da_cidade, n_da_cidade) + random.sample(outra_cidade, n_outra)

    restantes = [j for j in jurados_disponiveis if j not in titulares]
    if len(restantes) < 5:
        st.warning("⚠️ Menos de 5 jurados disponíveis para suplência.")

    suplentes = random.sample(restantes, min(5, len(restantes)))

    # 3) Registrar sorteio e atualizar flags/contadores
    novo_sorteio = Sorteio(cidade_processo=cidade_processo)
    session.add(novo_sorteio)
    
    session.query(Jurado).filter(Jurado.participou_ultimo == True)\
    .update({Jurado.participou_ultimo: False}, synchronize_session=False)


    # 3.1) Antes de marcar os novos, limpa o flag de quem participou no último sorteio
    session.query(Jurado).filter(Jurado.participou_ultimo == True)\
        .update({Jurado.participou_ultimo: False}, synchronize_session=False)

    # 3.2) Marca os sorteados atuais e incrementa contador
    for j in titulares + suplentes:
        j.sorteios_passados = (j.sorteios_passados or 0) + 1
        j.participou_ultimo = True
        j.foi_sorteado = True  # se ainda usar em algum lugar
        session.add(j)


    session.commit()
    session.close()
    return titulares, suplentes


    # Atualiza contadores
    for j in titulares + suplentes:
        j.sorteios_passados += 1
        session.add(j)

    novo_sorteio = Sorteio(cidade_processo=cidade_processo)
    session.add(novo_sorteio)
    session.commit()
    session.close()

    return titulares, suplentes

# FUNÇÃO PARA MARCAR IMPEDIDO
# def marcar_impedido(jurado_id):
#     session = Session()
#     jurado = session.query(Jurado).get(jurado_id)
#     jurado.impedido = True
#     session.commit()
#     session.close()

def marcar_impedido(jurado_id, motivo=None):
    session = Session()
    jurado = session.query(Jurado).get(jurado_id)
    jurado.impedido = True
    jurado.motivo_impedimento = motivo
    jurado.data_impedimento = datetime.date.today()
    session.commit()
    session.close()


with tabs[1]:
    st.subheader("Sorteio de Jurados")

    # cidade_processo = st.selectbox("Selecione a cidade do processo:", ["Inhuma", "Ipiranga"], key="cidade_sorteio")
    comarca = obter_comarca()
    cidades = comarca.cidades.split(",") if comarca else []
    cidade_processo = st.selectbox("Selecione a cidade do processo:", cidades)

    titulares = []
    suplentes = []
    nome_arquivo = None

    if st.button("Sortear Jurados"):
        titulares, suplentes = sortear_jurados(cidade_processo)

        if titulares:
            st.success("Jurados sorteados com sucesso!")

            st.subheader("✅ Titulares")
            for j in titulares:
                col1, col2 = st.columns([4, 1])
                col1.write(f"{j.nome} — {j.endereco}, {j.numero}, {j.bairro} ({j.cidade})")
                if col2.button("⛔ Impedir", key=f"impedir_t_{j.id}"):
                    marcar_impedido(j.id)
                    st.rerun()


            st.subheader("📋 Suplentes")
            for j in suplentes:
                col1, col2 = st.columns([4, 1])
                col1.write(f"{j.nome} — {j.endereco}, {j.numero}, {j.bairro} ({j.cidade})")
                if col2.button("⛔ Impedir", key=f"impedir_s_{j.id}"):
                    marcar_impedido(j.id)
                    st.rerun()


            # Gerar ata após sorteio
            nome_arquivo = gerar_ata(titulares, suplentes, cidade_processo)

    if nome_arquivo:
        with open(nome_arquivo, "rb") as f:
            st.download_button(
                label="📄 Baixar Ata de Sorteio",
                data=f,
                file_name=nome_arquivo,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )



# Funções que já temos (sortear, impedir) permanecem...

# 🔽 NOVO BLOCO – Cadastro de jurados
with tabs[0]:
    st.subheader("Cadastro de Novo Jurado")

    # Pega as cidades da comarca (sem depender de helper externo)
    from database import obter_comarca
    comarca = obter_comarca()
    cidades = [c.strip() for c in (comarca.cidades.split(",") if (comarca and comarca.cidades) else []) if c.strip()]

    if not cidades:
        st.info("⚠️ Nenhuma cidade configurada. Cadastre a comarca e suas cidades primeiro.")
    else:
        with st.form(key="form_cadastro"):
            nome = st.text_input("Nome completo")
            endereco = st.text_input("Endereço")
            numero = st.text_input("Número")
            bairro = st.text_input("Bairro")
            # Use SEMPRE a MESMA variável que será gravada no banco:
            cidade_escolhida = st.selectbox("Cidade", cidades, key="cidade_cadastro")
            profissao = st.text_input("Profissão (opcional)")


            cadastrar = st.form_submit_button("Cadastrar")

            if cadastrar:
                if not nome.strip():
                    st.warning("⚠️ O nome não pode estar vazio.")
                elif not cidade_escolhida:
                    st.warning("⚠️ Selecione uma cidade.")
                else:
                    session = Session()
                    novo = Jurado(
                        nome=nome.strip(),
                        endereco=endereco.strip(),
                        numero=numero.strip(),
                        bairro=bairro.strip(),
                        cidade=cidade_escolhida,  # <- aqui usamos a MESMA variável do selectbox
                        profissao=profissao.strip() or None  # ✅ salva se informado
                    )
                    session.add(novo)
                    session.commit()
                    session.close()
                    st.success(f"✅ Jurado '{nome.strip()}' cadastrado com sucesso!")




# st.markdown("---")
# st.header("👥 Visualização dos Jurados")

# # Filtros
# filtro_cidade = st.selectbox("Filtrar por cidade:", ["Todos", "Inhuma", "Ipiranga"], key="filtro_cidade_vis")

# filtro_status = st.selectbox("Filtrar por status:", ["Todos", "Disponíveis", "Impedidos"], key="status_jurados_vis")

# Buscar jurados
# -------------------------------
# 👥 VISUALIZAÇÃO DOS JURADOS
# -------------------------------

with tabs[2]:
    st.subheader("Lista de Jurados")

    # opções de cidade dinâmicas + "Todas"
    cidades = cidades_da_comarca()
    opcoes_cidade = ["Todas"] + cidades

    filtro_cidade = st.selectbox("Filtrar por cidade:", opcoes_cidade, key="filtro_cidade_vis")
    filtro_status = st.selectbox("Filtrar por status:", ["Todos", "Disponíveis", "Impedidos", "Sorteados"], key="filtro_status_vis")
    busca_nome = st.text_input("Buscar por nome:")

    session = Session()
    query = session.query(Jurado)

    # aplica filtro de cidade apenas se for diferente de "Todas"
    if filtro_cidade != "Todas":
        # importante: garantir comparação sem espaços
        query = query.filter(Jurado.cidade == filtro_cidade.strip())

    if filtro_status == "Disponíveis":
        query = query.filter(Jurado.impedido == False)
    elif filtro_status == "Impedidos":
        query = query.filter(Jurado.impedido == True)
    elif filtro_status == "Sorteados":
        query = query.filter(Jurado.sorteios_passados > 0)


    # ordena por nome para facilitar leitura
    query = query.order_by(Jurado.nome.asc())

    jurados = query.all()
    session.close()

    # busca por nome (case-insensitive)
    if busca_nome:
        termo = busca_nome.strip().lower()
        def _s(v): return (v or "").lower()
        jurados = [j for j in jurados if termo in _s(j.nome) or termo in _s(getattr(j, "profissao", ""))]


    if jurados:
        st.write(f"Total encontrados: {len(jurados)}")

        for j in jurados:
            with st.container():
                col1, col2, col3 = st.columns([5, 4, 3])
                # Dentro do for j in jurados:
                prof_txt = f" — {j.profissao}" if getattr(j, "profissao", None) else ""
                col1.markdown(f"**{j.nome}**{prof_txt} — {j.endereco}, {j.numero}, {j.bairro}, {j.cidade}")


                contagem = j.sorteios_passados or 0
                contagem_txt  = f"🎟️ Sorteios: {contagem}"
                sorteado_txt  = "✅ Já sorteado" if contagem > 0 else "🕗 Ainda não sorteado"
                status_txt    = "🟢 Disponível" if not j.impedido else "🔴 Impedido"

                # Exibir motivo e data (se houver)
                motivo_info = ""
                if j.impedido and getattr(j, "motivo_impedimento", None):
                    data_txt = ""
                    if getattr(j, "data_impedimento", None):
                        try:
                            data_txt = f" — em {j.data_impedimento.strftime('%d/%m/%Y')}"
                        except Exception:
                            pass
                    motivo_info = f" • Motivo: *{j.motivo_impedimento}*{data_txt}"

                prof_txt = f" — {j.profissao}" if getattr(j, "profissao", None) else ""
                col1.markdown(f"**{j.nome}** — {j.endereco}, {j.numero}, {j.bairro}, {j.cidade}")
                col2.markdown(f"{contagem_txt}  •  {sorteado_txt}  •  {status_txt}{motivo_info}")

                # --- CHAVES ESTÁVEIS POR LINHA ---
                key_open    = f"vis_imp_open_{j.id}"
                key_motivo  = f"vis_imp_motivo_{j.id}"
                key_outro   = f"vis_imp_outro_{j.id}"
                key_confirm = f"vis_imp_confirma_{j.id}"
                key_cancel  = f"vis_imp_cancela_{j.id}"
                key_toggle  = f"vis_imp_toggle_{j.id}"

                if j.impedido:
                    if col3.button("✅ Disponibilizar", key=key_toggle):
                        session = Session()
                        jur = session.query(Jurado).get(j.id)
                        jur.impedido = False
                        jur.motivo_impedimento = None
                        jur.data_impedimento = None
                        session.commit()
                        session.close()
                        st.rerun()
                else:
                    if col3.button("⛔ Impedir", key=key_toggle):
                        st.session_state[key_open] = True

                # Mini-form de motivo
                if st.session_state.get(key_open):
                    st.info("Informe o **motivo do impedimento**:")
                    motivo = st.selectbox(
                        "Motivo",
                        ["Não localizado", "Falecimento", "Mudou-se", "Saúde", "Isenção legal", "Outro"],
                        key=key_motivo
                    )
                    outro_txt = ""
                    if motivo == "Outro":
                        outro_txt = st.text_input("Descreva o motivo", key=key_outro)

                    c1, c2 = st.columns([1,1])
                    if c1.button("Confirmar", key=key_confirm):
                        motivo_final = outro_txt.strip() if motivo == "Outro" else motivo
                        marcar_impedido(j.id, motivo_final)
                        st.session_state.pop(key_open, None)
                        st.rerun()

                    if c2.button("Cancelar", key=key_cancel):
                        st.session_state.pop(key_open, None)
                        st.rerun()
    else:
        st.info("Nenhum jurado encontrado.")


        





with tabs[3]:
   with tabs[3]:
    st.subheader("⚙️ Atualizar Lista de Jurados")
    st.info("Você pode importar jurados de duas formas: \n"
            "- 📂 Arquivo único (com coluna 'Cidade')\n"
            "- 🏙️ Arquivo separado por cidade")
        # --- BACKUP ATUAL ---
    st.subheader("💾 Backup dos jurados atuais")
    try:
        csv_backup = exportar_jurados_csv()
        nome_backup = f"backup_jurados_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        st.download_button(
            label="📥 Baixar backup (CSV)",
            data=csv_backup,
            file_name=nome_backup,
            mime="text/csv"
        )
        st.caption("Recomendo baixar o backup antes de sobrescrever a lista.")
    except Exception as e:
        st.error(f"Não foi possível gerar o backup agora: {e}")

    st.subheader("📤 Atualizar Jurados por Arquivo")

    # Pergunta se será upload único ou por cidade
    modo_upload = st.radio("Modo de upload:", ["Arquivo único", "Cidade por cidade"], horizontal=True)

    tipo_arquivo = st.radio("Tipo de arquivo a importar:", ["Excel (.xlsx)", "Texto (.txt)"], horizontal=True)

    # ---------- MODO: ARQUIVO ÚNICO ----------
    if modo_upload == "Arquivo único":
        # Excel ÚNICO
        if tipo_arquivo == "Excel (.xlsx)":
            arquivo_excel = st.file_uploader("Envie a planilha Excel com os jurados (colunas: Nome, Endereço, Número, Bairro, Cidade):", type=["xlsx"])
            if arquivo_excel and st.button("🔄 Importar do Excel"):
                from importar_excel import importar_jurados_excel
                try:
                    importar_jurados_excel(arquivo_excel)
                    st.success("✅ Jurados importados com sucesso do Excel!")
                except Exception as e:
                    st.error(f"❌ Erro ao importar: {e}")

        # TXT ÚNICO
        else:
            st.warning("⚠️ Esta ação **apagará todos os jurados atuais** e os substituirá pelos do arquivo enviado.")
            arquivo_txt = st.file_uploader("Envie um arquivo .txt com as colunas: Nome, Endereço, Número, Bairro, Cidade", type=["txt"])

            if arquivo_txt and st.button("🔄 Atualizar Lista de Jurados (.txt)"):
                try:
                    conteudo = arquivo_txt.read().decode("utf-8", errors="ignore")
                    from importar_jurados import atualizar_jurados_multiplos
                    atualizar_jurados_multiplos([("jurados_unico.txt", conteudo)])
                    st.success("✅ Lista de jurados atualizada com sucesso a partir do arquivo .txt único!")
                except Exception as e:
                    st.error(f"❌ Erro ao importar: {e}")

    # ---------- MODO: CIDADE POR CIDADE ----------
    else:
        st.warning("⚠️ Esta ação **apagará todos os jurados atuais** e os substituirá pelos enviados abaixo.")

        comarca = obter_comarca()
        cidades = comarca.cidades.split(",") if comarca else []

        arquivos_por_cidade = {}
        for cidade in cidades:
            arquivos_por_cidade[cidade] = st.file_uploader(f"Arquivo de jurados de {cidade}", type=[tipo_arquivo.split()[0].lower()], key=f"{cidade}_file")

        if all(arquivos_por_cidade.values()) and st.button("🔄 Atualizar Lista Cidade por Cidade"):
            conteudos = []
            try:
                for cidade, file in arquivos_por_cidade.items():
                    if tipo_arquivo == "Excel (.xlsx)":
                        import pandas as pd
                        df = pd.read_excel(file)
                        conteudos.append((cidade, df.to_csv(index=False)))
                    else:  # TXT
                        conteudo = file.read().decode("utf-8", errors="ignore")
                        conteudos.append((cidade, conteudo))

                from importar_jurados import atualizar_jurados_multiplos
                atualizar_jurados_multiplos(conteudos)
                st.success("✅ Lista de jurados atualizada com sucesso a partir de arquivos por cidade!")
            except Exception as e:
                st.error(f"❌ Erro ao importar: {e}")


with tabs[4]:
    st.subheader("📄 Relatório em PDF de Jurados")

    if st.button("Gerar Relatório PDF"):
        session = Session()
        sorteados = session.query(Jurado).filter(Jurado.sorteios_passados == True).all()
        impedidos = session.query(Jurado).filter(Jurado.impedido == True).all()
        nao_sorteados = session.query(Jurado).filter(
            Jurado.foi_sorteado == False,
            Jurado.impedido == False
        ).all()

        # nome_pdf = gerar_relatorio_pdf(sorteados, impedidos, nao_sorteados)
        from database import obter_comarca

        comarca = obter_comarca()
        nome_comarca = comarca.nome if comarca else None
        nome_pdf = gerar_relatorio_pdf(sorteados, impedidos, nao_sorteados, nome_comarca=nome_comarca)

        st.success("✅ Relatório gerado com sucesso!")

        with open(nome_pdf, "rb") as file:
            st.download_button(
                label="📥 Baixar Relatório PDF",
                data=file,
                file_name=nome_pdf,
                mime="application/pdf"
            )

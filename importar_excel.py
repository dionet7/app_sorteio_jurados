import pandas as pd
import unicodedata
from database import Session, Jurado

def _strip_accents_lower(s: str) -> str:
    s = str(s).strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch))
    return s.lower()

# ✅ Inclui PROFISSÃO e sinônimos
COL_MAP = {
    "nome": {"nome", "jurado", "jurados"},
    "endereco": {"endereco", "endereço", "logradouro", "rua"},
    "numero": {"numero", "número", "nº", "n°", "no", "n"},
    "bairro": {"bairro"},
    "cidade": {"cidade", "municipio", "município", "comarca"},
    "profissao": {"profissao", "profissão", "ocupacao", "ocupação", "cargo", "atividade", "funcao", "função"}
}

def _build_rename_map(cols):
    rename = {}
    norm2orig = { _strip_accents_lower(c): c for c in cols }
    for target, synonyms in COL_MAP.items():
        for norm, orig in norm2orig.items():
            if norm in synonyms and target not in rename.values():
                rename[orig] = target
                break
    return rename

def _try_promote_first_row_as_header(df: pd.DataFrame) -> pd.DataFrame:
    if all(isinstance(c, (int, float)) for c in df.columns):
        new_header = df.iloc[0].astype(str).tolist()
        df = df[1:].copy()
        df.columns = new_header
    return df

def _to_str_safe(x):
    if pd.isna(x):
        return ""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)

def importar_jurados_excel(arquivo_excel):
    df = pd.read_excel(arquivo_excel, dtype=str)
    df = _try_promote_first_row_as_header(df)
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # Renomeia colunas reconhecidas
    rename = _build_rename_map(df.columns)
    df_ren = df.rename(columns=rename)

    obrigatorias = {"nome", "endereco", "numero", "bairro", "cidade"}
    faltantes = [c for c in sorted(obrigatorias) if c not in df_ren.columns]
    if faltantes:
        existentes_norm = [_strip_accents_lower(c) for c in df.columns]
        raise ValueError(
            "❌ Coluna(s) obrigatória(s) ausente(s): "
            + ", ".join(f"'{c.capitalize()}'" for c in faltantes)
            + f".\nColunas encontradas: {list(df.columns)}\n"
            + f"(normalizadas: {existentes_norm})"
        )

    tem_prof = "profissao" in df_ren.columns

    # ✅ Monta DF final, incluindo 'profissao' se existir
    data = {
        "nome": df_ren["nome"].apply(_to_str_safe).str.strip(),
        "endereco": df_ren["endereco"].apply(_to_str_safe).str.strip(),
        "numero": df_ren["numero"].apply(_to_str_safe).str.strip(),
        "bairro": df_ren["bairro"].apply(_to_str_safe).str.strip(),
        "cidade": df_ren["cidade"].apply(_to_str_safe).str.strip(),
    }
    if tem_prof:
        data["profissao"] = df_ren["profissao"].apply(_to_str_safe).str.strip()
    df_final = pd.DataFrame(data)
    df_final = df_final.replace("", pd.NA).dropna(how="all").fillna("")

    # Grava
    session = Session()
    session.query(Jurado).delete()
    session.commit()

    for _, row in df_final.iterrows():
        session.add(Jurado(
            nome=row["nome"],
            endereco=row["endereco"],
            numero=row["numero"],
            bairro=row["bairro"],
            cidade=row["cidade"],
            profissao=(row.get("profissao", None) or None)  # ✅ usa a coluna se existir
        ))

    session.commit()
    session.close()
    print("✅ Jurados importados do Excel com sucesso!")

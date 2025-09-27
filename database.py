from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, text


import datetime


# from database import Session, Jurado

def atualizar_jurados(caminho_txt):
    session = Session()

    # 🧹 1. Apagar todos os jurados antigos
    session.query(Jurado).delete()
    session.commit()

    # 📥 2. Importar novos jurados
    with open(caminho_txt, "r", encoding="utf-8") as f:
        for linha in f:
            partes = linha.strip().split(",")
            if len(partes) == 5:
                nome, endereco, numero, bairro, cidade = [p.strip() for p in partes]
                jurado = Jurado(
                    nome=nome,
                    endereco=endereco,
                    numero=numero,
                    bairro=bairro,
                    cidade=cidade
                )
                session.add(jurado)

    session.commit()
    session.close()
    print("✅ Lista de jurados atualizada com sucesso!")


engine = create_engine("sqlite:///jurados.db")
# Session = sessionmaker(bind=engine)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

class Jurado(Base):
   __tablename__ = "jurados"
   id = Column(Integer, primary_key=True)
   nome = Column(String, nullable=False)
#    profissao = Column(String)  # ✅ novo campo
   endereco = Column(String)
   numero = Column(String)
   bairro = Column(String)
   cidade = Column(String, nullable=False)
   profissao = Column(String)  # opcional
   impedido = Column(Boolean, default=False)
   sorteios_passados = Column(Integer, default=0)
   foi_sorteado = Column(Boolean, default=False)
   impedido = Column(Boolean, default=False)
   motivo_impedimento = Column(String)   # texto curto do motivo
   data_impedimento = Column(Date)       # quando foi marcado impedido
   participou_ultimo = Column(Boolean, default=False)  # bloqueia repetição imediata



class Sorteio(Base):
    __tablename__ = "sorteios"
    id = Column(Integer, primary_key=True)
    data = Column(Date, default=datetime.date.today)
    cidade_processo = Column(String)

class Comarca(Base):
    __tablename__ = "comarcas"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    cidades = Column(String, nullable=False)  # Exemplo: "Inhuma,Ipiranga"

def comarca_existe():
    session = Session()
    existe = session.query(Comarca).first() is not None
    session.close()
    return existe

def obter_comarca():
    session = Session()
    comarca = session.query(Comarca).first()
    session.close()
    return comarca

Base.metadata.create_all(engine)

def garantir_colunas_jurados():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info('jurados')")).fetchall()]

        if 'participou_ultimo' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN participou_ultimo BOOLEAN DEFAULT 0"))
        if 'motivo_impedimento' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN motivo_impedimento TEXT"))
        if 'data_impedimento' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN data_impedimento DATE"))
        # ✅ NOVO: profissão
        if 'profissao' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN profissao TEXT"))

garantir_colunas_jurados()
def garantir_coluna_participou_ultimo():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info('jurados')")).fetchall()]
        if 'participou_ultimo' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN participou_ultimo BOOLEAN DEFAULT 0"))
garantir_coluna_participou_ultimo()


def garantir_colunas_impedimento():
    # cria colunas se ainda não existirem (SQLite)
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info('jurados')")).fetchall()]
        if 'motivo_impedimento' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN motivo_impedimento TEXT"))
        if 'data_impedimento' not in cols:
            conn.execute(text("ALTER TABLE jurados ADD COLUMN data_impedimento DATE"))

# chama automaticamente quando o módulo é importado
garantir_colunas_impedimento()



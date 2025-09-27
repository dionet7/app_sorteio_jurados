from database import Session, Jurado

# Lista de jurados (nome, cidade)
jurados_iniciais = [
    ("Ana Paula", "Cidade A"),
    ("Carlos Silva", "Cidade A"),
    ("Juliana Souza", "Cidade B"),
    ("Marcos Vinicius", "Cidade A"),
    ("Fernanda Lima", "Cidade B"),
    ("Ricardo Gomes", "Cidade A"),
    ("Luciana Rocha", "Cidade B"),
    ("Paulo Henrique", "Cidade B"),
    ("Beatriz Almeida", "Cidade A"),
    ("João Pedro", "Cidade B"),
    # Adicione mais conforme necessário
]

session = Session()

for nome, cidade in jurados_iniciais:
    jurado = Jurado(nome=nome, cidade=cidade)
    session.add(jurado)

session.commit()
session.close()

print("Jurados inseridos com sucesso!")

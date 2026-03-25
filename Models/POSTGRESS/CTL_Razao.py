# Models/POSTGRESS/CTL_Razao.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Substitui a tua classe CtlRazaoConsolidado atual por esta:

class CtlRazaoConsolidado(Base):
    """
    Modelo de dados para a tabela Consolidada do Razão.
    Armazena todos os lançamentos contábeis unificados das diferentes origens.
    """
    __tablename__ = 'Tb_CTL_Razao_Consolidado'
    __table_args__ = {'schema': 'Dre_Schema'}
    
    # --- CHAVE PRIMÁRIA COMPOSTA ---
    Id = Column('Id', Integer, primary_key=True)
    Fonte = Column('Fonte', Text, primary_key=True)
    
    # --- COLUNAS DE CONTROLO DE AJUSTES ---
    Tipo_Operacao = Column('Tipo_Operacao', String(20))
    Status = Column('Status', String(20), default='Pendente')
    Is_Nao_Operacional = Column('Is_Nao_Operacional', Boolean, default=False)
    Is_Intergrupo = Column('Is_Intergrupo', Boolean, default=False)
    Exibir_Saldo = Column('Exibir_Saldo', Boolean, default=True)
    Invalido = Column('Invalido', Boolean, default=False)
    Criado_Por = Column('Criado_Por', String(100))
    Data_Criacao = Column('Data_Criacao', DateTime)
    Aprovado_Por = Column('Aprovado_Por', String(100))
    Data_Aprovacao = Column('Data_Aprovacao', DateTime)

    # --- COLUNAS EXISTENTES DE DADOS ---
    origem = Column('origem', Text)
    Conta = Column('Conta', Text)
    Titulo_Conta = Column('Título Conta', Text)
    Data = Column('Data', DateTime)
    Numero = Column('Numero', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Filial = Column('Filial', BigInteger)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)
    Saldo = Column('Saldo', Float)
    Mes = Column('Mes', Text)
    CC_Cod = Column('CC', Text)
    Nome_CC = Column('Nome CC', Text)
    Cliente = Column('Cliente', Text)
    Filial_Cliente = Column('Filial Cliente', Text)
    
    Chv_Mes_Conta = Column('Chv_Mes_Conta', Text)
    Chv_Mes_Conta_CC = Column('Chv_Mes_Conta_CC', Text)
    Chv_Mes_NomeCC_Conta = Column('Chv_Mes_NomeCC_Conta', Text)
    Chv_Mes_NomeCC_Conta_CC = Column('Chv_Mes_NomeCC_Conta_CC', Text)
    Chv_Conta_Formatada = Column('Chv_Conta_Formatada', Text)
    Chv_Conta_CC = Column('Chv_Conta_CC', Text)
    
class CtlRazaoFarma(Base):
    __tablename__ = 'Tb_CTL_Razao_Farma'
    __table_args__ = {'schema': 'Dre_Schema'}

    # Novo ID Central Adicionado
    Id = Column(Integer, primary_key=True, autoincrement=True)
    # Removidos os primary_key=True dos campos abaixo
    Conta = Column('Conta', Text)
    Data = Column('Data', DateTime)
    Numero = Column('Numero', Text)
    Filial = Column('Filial', BigInteger)
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)

class CtlRazaoFarmaDist(Base):
    __tablename__ = 'Tb_CTL_Razao_FarmaDist'
    __table_args__ = {'schema': 'Dre_Schema'}

    # Novo ID Central Adicionado
    Id = Column(Integer, primary_key=True, autoincrement=True)
    # Removidos os primary_key=True dos campos abaixo
    Conta = Column('Conta', Text)
    Data = Column('Data', DateTime)
    Numero = Column('Numero', Text)
    Filial = Column('Filial', BigInteger)
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)

class CtlRazaoIntec(Base):
    __tablename__ = 'Tb_CTL_Razao_Intec'
    __table_args__ = {'schema': 'Dre_Schema'}

    # Esta tabela já estava correta no teu modelo original!
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Conta = Column('Conta', Text)
    Data = Column('Data', DateTime)
    Numero = Column('Numero', Text)
    Filial = Column('Filial', BigInteger)
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)
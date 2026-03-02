# Models/POSTGRESS/CTL_Razao.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CtlRazaoConsolidado(Base):
    __tablename__ = 'Vw_CTL_Razao_Consolidado'
    __table_args__ = {'schema': 'Dre_Schema'}
    
    origem = Column('origem', Text)
    Conta = Column('Conta', Text, primary_key=True)
    Titulo_Conta = Column('Título Conta', Text)
    Data = Column('Data', DateTime, primary_key=True)
    Numero = Column('Numero', Text, primary_key=True)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Filial = Column('Filial', BigInteger, primary_key=True)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float, primary_key=True)
    Credito = Column('Credito', Float, primary_key=True)
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

    Conta = Column('Conta', Text, primary_key=True)
    Data = Column('Data', DateTime, primary_key=True)
    Numero = Column('Numero', Text, primary_key=True)
    Filial = Column('Filial', BigInteger, primary_key=True)
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

    Conta = Column('Conta', Text, primary_key=True)
    Data = Column('Data', DateTime, primary_key=True)
    Numero = Column('Numero', Text, primary_key=True)
    Filial = Column('Filial', BigInteger, primary_key=True)
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
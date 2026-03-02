# Models/POSTGRESS/CTL_Ajustes.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class CtlAjusteRazao(Base):
    __tablename__ = 'Tb_CTL_Ajuste_Razao'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Tipo_Operacao = Column(String(20))
    Hash_Linha_Original = Column(String(100), index=True, nullable=True)
    Status = Column(String(20), default='Pendente')
    Origem = Column(String(50))
    Conta = Column(String(50))
    Titulo_Conta = Column(String(255))
    Data = Column(DateTime)
    Numero = Column(String(50))
    Descricao = Column(Text)
    Contra_Partida = Column(String(255))
    Filial = Column(String(10))
    Centro_Custo = Column(String(50))
    Item = Column(String(50))
    Cod_Cl_Valor = Column(String(50))
    Debito = Column(Float, default=0.0)
    Credito = Column(Float, default=0.0)
    Is_Nao_Operacional = Column(Boolean, default=False)
    Exibir_Saldo = Column(Boolean, default=True)
    Invalido = Column(Boolean, default=False)
    Criado_Por = Column(String(100))
    Data_Criacao = Column(DateTime, default=datetime.datetime.now)
    Aprovado_Por = Column(String(100))
    Data_Aprovacao = Column(DateTime)

class CtlAjusteLog(Base):
    __tablename__ = 'Tb_CTL_Ajuste_Log'
    __table_args__ = {"schema": "Dre_Schema"}

    Id_Log = Column(Integer, primary_key=True)
    Id_Ajuste = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Ajuste_Razao.Id'))
    Campo_Alterado = Column(String)
    Valor_Antigo = Column(String)
    Valor_Novo = Column(String)
    Usuario_Acao = Column(String)
    Data_Acao = Column(DateTime, default=datetime.datetime.now)
    Tipo_Acao = Column(String)

class CtlAjusteIntergrupoLog(Base):
    __tablename__ = 'Tb_CTL_Ajuste_Intergrupo_Log'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Data_Processamento = Column(DateTime, default=datetime.datetime.now)
    Ano = Column(Integer)
    Mes = Column(Integer)
    Conta_Origem = Column(String(50))
    Origem_ERP = Column(String(50))
    Valor_Encontrado_ERP = Column(Float)
    Tipo_Fluxo = Column(String(20))
    Id_Ajuste_Origem = Column(Integer)
    Id_Ajuste_Destino = Column(Integer)
    Acao_Realizada = Column(String(50))
    Hash_Gerado = Column(String(100))
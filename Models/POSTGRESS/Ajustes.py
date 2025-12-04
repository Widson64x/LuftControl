from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text ,ForeignKey
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class AjustesRazao(Base):
    __table_args__ = {"schema": "Dre_Schema"}
    __tablename__ = 'Ajustes_Razao'

    Id = Column(Integer, primary_key=True)
    
    # Controle
    Tipo_Operacao = Column(String(20))
    Hash_Linha_Original = Column(String(100), index=True, nullable=True)
    Status = Column(String(20), default='Pendente')
    
    # Dados Espelho
    Origem = Column(String(50))
    Conta = Column(String(50))
    Titulo_Conta = Column(String(255))      # <---
    Data = Column(Date)
    Numero = Column(String(50))
    Descricao = Column(Text)
    Contra_Partida = Column(String(255))    # <---
    Filial = Column(String(10))
    Centro_Custo = Column(String(50))
    Item = Column(String(50))
    Cod_Cl_Valor = Column(String(50))       # <---
    
    # Valores
    Debito = Column(Float, default=0.0)
    Credito = Column(Float, default=0.0)
    
    # Regras
    Is_Nao_Operacional = Column(Boolean, default=False)
    Exibir_Saldo = Column(Boolean, default=True) # <---
    
    # Auditoria
    Criado_Por = Column(String(100))
    Data_Criacao = Column(DateTime, default=datetime.datetime.now)
    Aprovado_Por = Column(String(100))
    Data_Aprovacao = Column(DateTime)

class AjustesLog(Base):
    __table_args__ = {"schema": "Dre_Schema"}
    __tablename__ = 'Ajustes_Log'

    Id_Log = Column(Integer, primary_key=True)
    Id_Ajuste = Column(Integer, ForeignKey('Dre_Schema.Ajustes_Razao.Id'))
    Campo_Alterado = Column(String)
    Valor_Antigo = Column(String)
    Valor_Novo = Column(String)
    Usuario_Acao = Column(String)
    Data_Acao = Column(DateTime, default=datetime.datetime.now)
    Tipo_Acao = Column(String)
# Models/POSTGRESS/CTL_Cadastros.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()
"""
-- Tabela fora de uso, pois a estrutura de agrupamento de contas foi alterada para ser mais flexível e permitir múltiplos níveis de agrupamento.

class CtlCadAgrupamentoConta(Base):
    __tablename__ = 'Tb_CTL_Cad_Agrupamento_Conta'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Conta = Column(String(50))
    Nome_Conta = Column(String(100))
    Grupo_Nivel1 = Column(String(100))
    Grupo_Nivel2 = Column(String(100))
    Ordem = Column(Integer)
    Data_Criacao = Column(DateTime, default=datetime.now)
    Data_Atualizacao = Column(DateTime, onupdate=datetime.now)
"""
class CtlCadCentroCusto(Base):
    __tablename__ = 'Tb_CTL_Cad_Centro_Custo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Codigo = Column(Integer, primary_key=True)
    Nome = Column(Text)
    Tipo = Column(Text)  # 'Adm', 'Oper', 'Coml'

class CtlCadDespesaPessoal(Base):
    __tablename__ = 'Tb_CTL_Cad_Despesa_Pessoal'
    __table_args__ = {'schema': 'Dre_Schema'}

    Fornecedor = Column(Text, primary_key=True)
    Servico = Column(Text, primary_key=True)
    Classe = Column(Text)

class CtlCadPlanoContaFilial(Base):
    __tablename__ = 'Tb_CTL_Cad_Plano_Conta_Filial'
    __table_args__ = {'schema': 'Dre_Schema'}

    Item_Conta = Column(String(50), primary_key=True)
    Denominacao = Column(Text)
    Filial = Column(Text)
# Models/POSTGRESS/CTL_Dre_Estrutura.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CtlDreNoVirtual(Base):
    __tablename__ = 'Tb_CTL_Dre_No_Virtual'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String)
    Ordem = Column(Integer)
    Is_Calculado = Column(Boolean, default=False)
    Formula_JSON = Column(Text, nullable=True)
    Formula_Descricao = Column(String, nullable=True)
    Tipo_Exibicao = Column(String, default='valor')
    Estilo_CSS = Column(String, nullable=True)
    Base_Percentual_Id = Column(Integer, nullable=True)

class CtlDreHierarquia(Base):
    __tablename__ = 'Tb_CTL_Dre_Hierarquia'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False)
    Id_Pai = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Dre_Hierarquia.Id'), nullable=True)
    
    Raiz_Centro_Custo_Codigo = Column(Integer, nullable=True) 
    Raiz_Centro_Custo_Tipo = Column(String, nullable=True)
    Raiz_Centro_Custo_Nome = Column(String, nullable=True)
    
    Raiz_No_Virtual_Id = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Dre_No_Virtual.Id'), nullable=True)
    Raiz_No_Virtual_Nome = Column(String, nullable=True)

class CtlDreContaVinculo(Base):
    __tablename__ = 'Tb_CTL_Dre_Conta_Vinculo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True) 
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Dre_Hierarquia.Id'), nullable=False)
    Chave_Conta_Tipo_CC = Column(String, nullable=True)
    Chave_Conta_Codigo_CC = Column(String, nullable=True)

class CtlDreContaPersonalizada(Base):
    __tablename__ = 'Tb_CTL_Dre_Conta_Personalizada'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True)
    Nome_Personalizado = Column(String, nullable=True)
    
    Id_No_Virtual = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Dre_No_Virtual.Id'), nullable=True)
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Dre_Hierarquia.Id'), nullable=True)
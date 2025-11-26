# Models/POSTGRESS/DreEstrutura.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class DreSubgrupo(Base):
    __tablename__ = 'Tb_Dre_Subgrupos'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    parent_subgrupo_id = Column(Integer, ForeignKey('Dre_Schema.Tb_Dre_Subgrupos.id'), nullable=True)
    
    # Raiz de Centro de Custo
    root_cc_codigo = Column(Integer, nullable=True) 
    root_cc_tipo = Column(String, nullable=True)    
    root_cc_nome = Column(String, nullable=True)

    # NOVA: Raiz de Nó Virtual
    root_virtual_id = Column(Integer, ForeignKey('Dre_Schema.Tb_Dre_No_Virtual.id'), nullable=True)
    root_virtual_nome = Column(String, nullable=True)

class DreContaVinculo(Base):
    __tablename__ = 'Tb_Dre_Conta_Vinculo'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True)
    conta_contabil = Column(String, nullable=False, unique=True) 
    subgrupo_id = Column(Integer, ForeignKey('Dre_Schema.Tb_Dre_Subgrupos.id'), nullable=False)
    
    # NOVAS CHAVES PARA RELATÓRIO
    key_conta_tipo_cc = Column(String, nullable=True) # Ex: '60601010102Adm'
    key_conta_cod_cc = Column(String, nullable=True)  # Ex: '060101010225110501'
    
    
# Adicione ao final do arquivo Models/POSTGRESS/DreEstrutura.py

class DreNoVirtual(Base):
    __tablename__ = 'Tb_Dre_No_Virtual'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False, unique=True)
    ordem = Column(Integer, default=0)

class DreContaDetalhe(Base):
    __tablename__ = 'Tb_Dre_Conta_Detalhe'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True)
    conta_contabil = Column(String, nullable=False, unique=True)
    nome_personalizado = Column(String, nullable=True)
    
    # FKs opcionais (uma conta pode estar ligada a um Nó Virtual OU Subgrupo)
    no_virtual_id = Column(Integer, ForeignKey('Dre_Schema.Tb_Dre_No_Virtual.id'), nullable=True)
    subgrupo_id = Column(Integer, ForeignKey('Dre_Schema.Tb_Dre_Subgrupos.id'), nullable=True)
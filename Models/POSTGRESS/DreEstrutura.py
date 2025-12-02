# Models/POSTGRESS/DreEstrutura.py
"""
Modelos ORM para Estrutura da DRE (Demonstração do Resultado do Exercício)
Gerencia a hierarquia de grupos, subgrupos e vínculos de contas contábeis.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DreNoVirtual(Base):
    """
    Nós Virtuais para estruturas personalizadas da DRE.
    Permite criar agrupamentos customizados além da estrutura do ERP.
    """
    __tablename__ = 'DRE_Estrutura_No_Virtual'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String)
    Ordem = Column(Integer)
    
    # Campos para nós calculados
    Is_Calculado = Column(Boolean, default=False)
    Formula_JSON = Column(Text, nullable=True)
    Formula_Descricao = Column(String, nullable=True)
    Tipo_Exibicao = Column(String, default='valor')
    Estilo_CSS = Column(String, nullable=True)
    Base_Percentual_Id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<DreNoVirtual(Id={self.Id}, Nome='{self.Nome}')>"


class DreHierarquia(Base):
    """
    Hierarquia de grupos e subgrupos da DRE.
    Suporta estruturas baseadas em Centros de Custo (ERP) e Nós Virtuais (personalizados).
    """
    __tablename__ = 'DRE_Estrutura_Hierarquia'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False)
    Id_Pai = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)
    
    # Raiz de Centro de Custo (Estrutura do ERP)
    Raiz_Centro_Custo_Codigo = Column(Integer, nullable=True) 
    Raiz_Centro_Custo_Tipo = Column(String, nullable=True)
    Raiz_Centro_Custo_Nome = Column(String, nullable=True)
    
    # Raiz de Nó Virtual (Estrutura Personalizada)
    Raiz_No_Virtual_Id = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Raiz_No_Virtual_Nome = Column(String, nullable=True)

    def __repr__(self):
        return f"<DreHierarquia(Id={self.Id}, Nome='{self.Nome}')>"


class DreContaVinculo(Base):
    """
    Vínculo entre Contas Contábeis e Grupos da Hierarquia.
    """
    __tablename__ = 'DRE_Estrutura_Conta_Vinculo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True) 
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=False)
    
    Chave_Conta_Tipo_CC = Column(String, nullable=True)
    Chave_Conta_Codigo_CC = Column(String, nullable=True)

    def __repr__(self):
        return f"<DreContaVinculo(Conta='{self.Conta_Contabil}', Hierarquia={self.Id_Hierarquia})>"


class DreContaPersonalizada(Base):
    """
    Contas com nomes personalizados e vínculos diretos a Nós Virtuais ou Subgrupos.
    """
    __tablename__ = 'DRE_Estrutura_Conta_Personalizada'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True)
    Nome_Personalizado = Column(String, nullable=True)
    
    Id_No_Virtual = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)

    def __repr__(self):
        return f"<DreContaPersonalizada(Conta='{self.Conta_Contabil}', Nome='{self.Nome_Personalizado}')>"
# Models/POSTGRESS/DreEstrutura.py
"""
Modelos ORM para Estrutura da DRE (Demonstração do Resultado do Exercício)
Gerencia a hierarquia de grupos, subgrupos e vínculos de contas contábeis.
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DreHierarquia(Base):
    """
    Hierarquia de grupos e subgrupos da DRE.
    Suporta estruturas baseadas em Centros de Custo (ERP) e Nós Virtuais (personalizados).
    
    Antiga: Tb_Dre_Subgrupos
    Nova: DRE_Estrutura_Hierarquia
    """
    __tablename__ = 'DRE_Estrutura_Hierarquia'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False)
    Id_Pai = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)
    
    # Raiz de Centro de Custo (Estrutura do ERP)
    Raiz_Centro_Custo_Codigo = Column(Integer, nullable=True) 
    Raiz_Centro_Custo_Tipo = Column(String, nullable=True)    # Ex: 'Adm', 'Oper', 'Coml'
    Raiz_Centro_Custo_Nome = Column(String, nullable=True)
    
    # Raiz de Nó Virtual (Estrutura Personalizada)
    Raiz_No_Virtual_Id = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Raiz_No_Virtual_Nome = Column(String, nullable=True)

    def __repr__(self):
        return f"<DreHierarquia(Id={self.Id}, Nome='{self.Nome}')>"


class DreContaVinculo(Base):
    """
    Vínculo entre Contas Contábeis e Grupos da Hierarquia.
    Permite classificar contas em diferentes grupos sem renomeá-las.
    
    Antiga: Tb_Dre_Conta_Vinculo
    Nova: DRE_Estrutura_Conta_Vinculo
    """
    __tablename__ = 'DRE_Estrutura_Conta_Vinculo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True) 
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=False)
    
    # Chaves compostas para relatórios e agregações
    Chave_Conta_Tipo_CC = Column(String, nullable=True)   # Ex: '60601010102Adm'
    Chave_Conta_Codigo_CC = Column(String, nullable=True) # Ex: '060101010225110501'

    def __repr__(self):
        return f"<DreContaVinculo(Conta='{self.Conta_Contabil}', Hierarquia={self.Id_Hierarquia})>"


class DreNoVirtual(Base):
    """
    Nós Virtuais - Grupos personalizados da DRE (ex: Faturamento Líquido, Impostos).
    Permitem criar estruturas fora da hierarquia padrão do ERP.
    
    Antiga: Tb_Dre_No_Virtual
    Nova: DRE_Estrutura_No_Virtual
    """
    __tablename__ = 'DRE_Estrutura_No_Virtual'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False, unique=True)
    Ordem = Column(Integer, default=0)  # Define posição na DRE (10, 20, 30...)

    def __repr__(self):
        return f"<DreNoVirtual(Id={self.Id}, Nome='{self.Nome}', Ordem={self.Ordem})>"


class DreContaPersonalizada(Base):
    """
    Contas com nomes personalizados e vínculos diretos a Nós Virtuais ou Subgrupos.
    Permite renomear contas para exibição customizada nos relatórios.
    
    Antiga: Tb_Dre_Conta_Detalhe
    Nova: DRE_Estrutura_Conta_Personalizada
    """
    __tablename__ = 'DRE_Estrutura_Conta_Personalizada'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True)
    Nome_Personalizado = Column(String, nullable=True)
    
    # Pode estar ligada a um Nó Virtual OU a um Subgrupo (mutuamente exclusivo)
    Id_No_Virtual = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)

    def __repr__(self):
        return f"<DreContaPersonalizada(Conta='{self.Conta_Contabil}', Nome='{self.Nome_Personalizado}')>"# Models/POSTGRESS/DreEstrutura.py
"""
Modelos ORM para Estrutura da DRE (Demonstração do Resultado do Exercício)
Gerencia a hierarquia de grupos, subgrupos e vínculos de contas contábeis.
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DreHierarquia(Base):
    """
    Hierarquia de grupos e subgrupos da DRE.
    Suporta estruturas baseadas em Centros de Custo (ERP) e Nós Virtuais (personalizados).
    
    Antiga: Tb_Dre_Subgrupos
    Nova: DRE_Estrutura_Hierarquia
    """
    __tablename__ = 'DRE_Estrutura_Hierarquia'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False)
    Id_Pai = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)
    
    # Raiz de Centro de Custo (Estrutura do ERP)
    Raiz_Centro_Custo_Codigo = Column(Integer, nullable=True) 
    Raiz_Centro_Custo_Tipo = Column(String, nullable=True)    # Ex: 'Adm', 'Oper', 'Coml'
    Raiz_Centro_Custo_Nome = Column(String, nullable=True)
    
    # Raiz de Nó Virtual (Estrutura Personalizada)
    Raiz_No_Virtual_Id = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Raiz_No_Virtual_Nome = Column(String, nullable=True)

    def __repr__(self):
        return f"<DreHierarquia(Id={self.Id}, Nome='{self.Nome}')>"


class DreContaVinculo(Base):
    """
    Vínculo entre Contas Contábeis e Grupos da Hierarquia.
    Permite classificar contas em diferentes grupos sem renomeá-las.
    
    Antiga: Tb_Dre_Conta_Vinculo
    Nova: DRE_Estrutura_Conta_Vinculo
    """
    __tablename__ = 'DRE_Estrutura_Conta_Vinculo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True) 
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=False)
    
    # Chaves compostas para relatórios e agregações
    Chave_Conta_Tipo_CC = Column(String, nullable=True)   # Ex: '60601010102Adm'
    Chave_Conta_Codigo_CC = Column(String, nullable=True) # Ex: '060101010225110501'

    def __repr__(self):
        return f"<DreContaVinculo(Conta='{self.Conta_Contabil}', Hierarquia={self.Id_Hierarquia})>"


class DreNoVirtual(Base):
    """
    Nós Virtuais - Grupos personalizados da DRE (ex: Faturamento Líquido, Impostos).
    Permitem criar estruturas fora da hierarquia padrão do ERP.
    
    Antiga: Tb_Dre_No_Virtual
    Nova: DRE_Estrutura_No_Virtual
    """
    __tablename__ = 'DRE_Estrutura_No_Virtual'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Nome = Column(String, nullable=False, unique=True)
    Ordem = Column(Integer, default=0)  # Define posição na DRE (10, 20, 30...)

    def __repr__(self):
        return f"<DreNoVirtual(Id={self.Id}, Nome='{self.Nome}', Ordem={self.Ordem})>"


class DreContaPersonalizada(Base):
    """
    Contas com nomes personalizados e vínculos diretos a Nós Virtuais ou Subgrupos.
    Permite renomear contas para exibição customizada nos relatórios.
    
    Antiga: Tb_Dre_Conta_Detalhe
    Nova: DRE_Estrutura_Conta_Personalizada
    """
    __tablename__ = 'DRE_Estrutura_Conta_Personalizada'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    Conta_Contabil = Column(String, nullable=False, unique=True)
    Nome_Personalizado = Column(String, nullable=True)
    
    # Pode estar ligada a um Nó Virtual OU a um Subgrupo (mutuamente exclusivo)
    Id_No_Virtual = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_No_Virtual.Id'), nullable=True)
    Id_Hierarquia = Column(Integer, ForeignKey('Dre_Schema.DRE_Estrutura_Hierarquia.Id'), nullable=True)

    def __repr__(self):
        return f"<DreContaPersonalizada(Conta='{self.Conta_Contabil}', Nome='{self.Nome_Personalizado}')>"
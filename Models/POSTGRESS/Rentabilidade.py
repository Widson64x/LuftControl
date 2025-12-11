# Models/POSTGRESS/Rentabilidade.py
"""
Modelos ORM para Dados de Rentabilidade e Razão Contábil.
Consolida lançamentos contábeis de múltiplas origens (FARMA, FARMADIST).
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ClassificacaoContaAgrupamento(Base):
    """
    Agrupamentos de Contas Contábeis para análises gerenciais.
    
    Antiga: Tb_Agrupamento_Conta
    Nova: Classificacao_Conta_Agrupamento
    """
    __tablename__ = 'Classificacao_Conta_Agrupamento'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Conta = Column(String(50))
    Nome_Conta = Column(String(100))  # ⚠️ Coluna real do banco
    Grupo_Nivel1 = Column(String(100))
    Grupo_Nivel2 = Column(String(100))
    Ordem = Column(Integer)
    Data_Criacao = Column(DateTime, default=datetime.now)
    Data_Atualizacao = Column(DateTime, onupdate=datetime.now)

    def __repr__(self):
        return f"<ClassificacaoContaAgrupamento(Conta='{self.Conta}', Nome='{self.Nome_Conta}')>"


class ClassificacaoCentroCusto(Base):
    """
    Classificação dos Centros de Custo do ERP.
    Define tipos (Adm, Oper, Coml) e hierarquia dos CCs.
    
    Antiga: Tb_Centro_Custo_Classificacao
    Nova: Classificacao_Centro_Custo
    """
    __tablename__ = 'Classificacao_Centro_Custo'
    __table_args__ = {'schema': 'Dre_Schema'}

    Codigo = Column(Integer, primary_key=True)
    Nome = Column(Text)
    Tipo = Column(Text)  # 'Adm', 'Oper', 'Coml'

    def __repr__(self):
        return f"<ClassificacaoCentroCusto(Codigo={self.Codigo}, Nome='{self.Nome}', Tipo='{self.Tipo}')>"


class ClassificacaoDespesasPessoal(Base):
    """
    Classificação de Despesas com Pessoal por Fornecedor/Serviço.
    
    ⚠️ IMPORTANTE: Esta tabela NÃO possui coluna "id" - é apenas uma tabela auxiliar.
    
    Antiga: Tb_Classificacao_Despesas_Pesso
    Nova: Classificacao_Despesas_Pessoal
    """
    __tablename__ = 'Classificacao_Despesas_Pessoal'
    __table_args__ = {'schema': 'Dre_Schema'}

    Fornecedor = Column(Text, primary_key=True)  # Usamos como PK composta
    Servico = Column(Text, primary_key=True)
    Classe = Column(Text)

    def __repr__(self):
        return f"<ClassificacaoDespesasPessoal(Fornecedor='{self.Fornecedor}', Classe='{self.Classe}')>"


class ClassificacaoPlanoContasFilial(Base):
    """
    Plano de Contas por Filial.
    Permite mapeamento específico de contas para cada unidade.
    
    Antiga: Tb_Plano_Contas_Filiais
    Nova: Classificacao_Plano_Contas_Filial
    """
    __tablename__ = 'Classificacao_Plano_Contas_Filial'
    __table_args__ = {'schema': 'Dre_Schema'}

    Item_Conta = Column(String(50), primary_key=True)
    Denominacao = Column(Text)  # Corrigido: era "Denomicao"
    Filial = Column(Text)

    def __repr__(self):
        return f"<ClassificacaoPlanoContasFilial(Item='{self.Item_Conta}', Filial='{self.Filial}')>"


class RazaoConsolidado(Base):
    """
    VIEW que consolida Razao_Dados_Origem_FARMA e Razao_Dados_Origem_FARMADIST.
    
    ⚠️ IMPORTANTE: Esta é uma VIEW, não uma tabela física.
    ⚠️ MANTÉM OS NOMES ORIGINAIS DAS COLUNAS DO EXCEL (não renomeia)
    
    Chave Composta: (Conta, Data, Numero, Filial, Debito, Credito)
    
    Antiga: Tb_Razao_CONSOLIDADA
    Nova: Razao_Dados_Consolidado (VIEW)
    """
    __tablename__ = 'Razao_Dados_Consolidado'
    __table_args__ = {'schema': 'Dre_Schema'}
    
    # ⚠️ Mantém nomes originais do Excel
    origem = Column('origem', Text)
    
    # Chave Composta
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
    
    # Chaves auxiliares
    Chv_Mes_Conta = Column('Chv_Mes_Conta', Text)
    Chv_Mes_Conta_CC = Column('Chv_Mes_Conta_CC', Text)
    Chv_Mes_NomeCC_Conta = Column('Chv_Mes_NomeCC_Conta', Text)
    Chv_Mes_NomeCC_Conta_CC = Column('Chv_Mes_NomeCC_Conta_CC', Text)
    Chv_Conta_Formatada = Column('Chv_Conta_Formatada', Text)
    Chv_Conta_CC = Column('Chv_Conta_CC', Text)

    def __repr__(self):
        return f"<RazaoConsolidado(Conta='{self.Conta}', Data='{self.Data}', Saldo={self.Saldo})>"


class RazaoOrigemFARMA(Base):
    """
    Lançamentos contábeis da origem FARMA.
    
    ⚠️ CRÍTICO: Tabela SEM coluna "id" - dados importados do Excel
    ⚠️ TODOS os nomes de colunas são mantidos do Excel (não renomear)
    
    Antiga: Tb_Razao_FARMA
    Nova: Razao_Dados_Origem_FARMA
    """
    __tablename__ = 'Razao_Dados_Origem_FARMA'
    __table_args__ = {'schema': 'Dre_Schema'}

    # ⚠️ NÃO TEM "Id" - Usamos chave composta
    Conta = Column('Conta', Text, primary_key=True)
    Data = Column('Data', DateTime, primary_key=True)
    Numero = Column('Numero', Text, primary_key=True)
    Filial = Column('Filial', BigInteger, primary_key=True)
    
    # Mantém nomes originais do Excel
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)

    def __repr__(self):
        return f"<RazaoOrigemFARMA(Conta='{self.Conta}', Data='{self.Data}')>"


class RazaoOrigemFARMADIST(Base):
    """
    Lançamentos contábeis da origem FARMADIST.
    
    ⚠️ CRÍTICO: Tabela SEM coluna "id" - dados importados do Excel
    ⚠️ TODOS os nomes de colunas são mantidos do Excel (não renomear)
    
    Antiga: Tb_Razao_FARMADIST
    Nova: Razao_Dados_Origem_FARMADIST
    """
    __tablename__ = 'Razao_Dados_Origem_FARMADIST'
    __table_args__ = {'schema': 'Dre_Schema'}

    # ⚠️ NÃO TEM "Id" - Usamos chave composta
    Conta = Column('Conta', Text, primary_key=True)
    Data = Column('Data', DateTime, primary_key=True)
    Numero = Column('Numero', Text, primary_key=True)
    Filial = Column('Filial', BigInteger, primary_key=True)

    # Mantém nomes originais do Excel
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)

    def __repr__(self):
        return f"<RazaoOrigemFARMADIST(Conta='{self.Conta}', Data='{self.Data}')>"
    
class RazaoOrigemINTEC(Base):
    """
    Lançamentos contábeis da origem INTEC.
    Adicionado ID para permitir lançamentos múltiplos com mesmo Numero/Conta.
    """
    __tablename__ = 'Razao_Dados_Origem_INTEC'
    __table_args__ = {'schema': 'Dre_Schema'}

    # ✅ CORREÇÃO: Adicionamos um ID autoincrementável como chave primária
    Id = Column(Integer, primary_key=True, autoincrement=True)

    # Removemos primary_key=True destes campos para permitir repetição
    Conta = Column('Conta', Text)
    Data = Column('Data', DateTime)
    Numero = Column('Numero', Text)
    Filial = Column('Filial', BigInteger)
    
    # Restante das colunas continua igual
    Titulo_Conta = Column('Título Conta', Text)
    Descricao = Column('Descricao', Text)
    Contra_Partida_Credito = Column('Contra Partida - Credito', Text)
    Centro_Custo = Column('Centro de Custo', BigInteger)
    Item = Column('Item', String(50))
    Cod_Cl_Valor = Column('Cod Cl. Valor', Text)
    Debito = Column('Debito', Float)
    Credito = Column('Credito', Float)

    def __repr__(self):
        return f"<RazaoOrigemINTEC(Id={self.Id}, Conta='{self.Conta}')>"
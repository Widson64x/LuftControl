from sqlalchemy import Column, Integer, String, Text, DateTime, Float, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AgrupamentoConta(Base):
    __tablename__ = 'Tb_Agrupamento_Conta'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    conta = Column('Conta', String(50))
    agrupamento = Column('Agrupamento', String(100))
    grupo_nivel1 = Column('Grupo_nivel1', String(100))
    grupo_nivel2 = Column('Grupo_nivel2', String(100))
    ordem = Column('Ordem', Integer)
    data_criacao = Column('Data_Criacao', DateTime, default=datetime.now)
    data_atualizacao = Column('Data_Atualizacao', DateTime, onupdate=datetime.now)

    def __repr__(self):
        return f"<Agrupamento {self.conta} - {self.agrupamento}>"


class CentroCustoClassificacao(Base):
    __tablename__ = 'Tb_Centro_Custo_Classificacao'
    __table_args__ = {'schema': 'Dre_Schema'}

    codigo_cc = Column('Codigo CC.', Integer, primary_key=True)
    nome = Column('Nome', Text)
    tipo = Column('Tipo', Text)


class ClassificacaoDespesasPessoal(Base):
    __tablename__ = 'Tb_Classificacao_Despesas_Pesso'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(Integer, primary_key=True, autoincrement=True) 
    fornecedor = Column('Fornecedor', Text)
    servico = Column('Servico', Text)
    classe = Column('Classe', Text)


class PlanoContasFiliais(Base):
    __tablename__ = 'Tb_Plano_Contas_Filiais'
    __table_args__ = {'schema': 'Dre_Schema'}

    item_conta = Column('Item Conta', String(50), primary_key=True)
    denominacao = Column('Denomicao', Text)
    filial = Column('Filial', Text)


class RazaoConsolidada(Base):
    """
    VIEW que consolida Tb_Razao_FARMA e Tb_Razao_FARMADIST
    Localização: Dre_Schema.Tb_Razao_CONSOLIDADA
    ALTERAÇÃO: Adicionado primary_key=True em múltiplas colunas para criar uma 
    chave composta única e evitar a desduplicação de linhas pelo SQLAlchemy.
    """
    __tablename__ = 'Tb_Razao_CONSOLIDADA'
    __table_args__ = {'schema': 'Dre_Schema'}
    
    origem = Column('origem', Text)
    # Chave Composta Expandida: Garante que linhas com mesma conta/data mas valores diferentes apareçam
    conta = Column('Conta', Text, primary_key=True)
    titulo_conta = Column('Título Conta', Text)
    data = Column('Data', DateTime, primary_key=True)
    numero = Column('Numero', Text, primary_key=True) # Adicionado como PK
    descricao = Column('Descricao', Text)
    contra_partida_credito = Column('Contra Partida - Credito', Text)
    filial_id = Column('Filial', BigInteger, primary_key=True) # Adicionado como PK
    centro_custo_id = Column('Centro de Custo', BigInteger)
    item = Column('Item', String(50))
    cod_cl_valor = Column('Cod Cl. Valor', Text)
    debito = Column('Debito', Float, primary_key=True) # Adicionado como PK (Diferencia valores iguais)
    credito = Column('Credito', Float, primary_key=True) # Adicionado como PK
    saldo = Column('Saldo', Float)
    mes = Column('Mes', Text)
    cc_cod = Column('CC', Text)
    nome_cc = Column('Nome CC', Text)
    cliente = Column('Cliente', Text)
    filial_cliente = Column('Filial Cliente', Text)
    
    # Chaves auxiliares
    chv_mes_conta = Column('Chv_Mes_Conta', Text)
    chv_mes_conta_cc = Column('Chv_Mes_Conta_CC', Text)
    chv_mes_nomecc_conta = Column('Chv_Mes_NomeCC_Conta', Text)
    chv_mes_nomecc_conta_cc = Column('Chv_Mes_NomeCC_Conta_CC', Text)
    chv_conta_formatada = Column('Chv_Conta_Formatada', Text)
    chv_conta_cc = Column('Chv_Conta_CC', Text)


class RazaoFarma(Base):
    __tablename__ = 'Tb_Razao_FARMA'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    conta = Column('Conta', Text)
    titulo_conta = Column('Título Conta', Text)
    data = Column('Data', DateTime)
    numero = Column('Numero', Text)
    descricao = Column('Descricao', Text)
    contra_partida_credito = Column('Contra Partida - Credito', Text)
    filial_id = Column('Filial', BigInteger)
    centro_custo_id = Column('Centro de Custo', BigInteger)
    item = Column('Item', String(50))
    cod_cl_valor = Column('Cod Cl. Valor', Text)
    debito = Column('Debito', Float)
    credito = Column('Credito', Float)


class RazaoFarmaDist(Base):
    __tablename__ = 'Tb_Razao_FARMADIST'
    __table_args__ = {'schema': 'Dre_Schema'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    conta = Column('Conta', Text)
    titulo_conta = Column('Título Conta', Text)
    data = Column('Data', DateTime)
    numero = Column('Numero', Text)
    descricao = Column('Descricao', Text)
    contra_partida_credito = Column('Contra Partida - Credito', Text)
    filial_id = Column('Filial', BigInteger)
    centro_custo_id = Column('Centro de Custo', BigInteger)
    item = Column('Item', String(50))
    cod_cl_valor = Column('Cod Cl. Valor', Text)
    debito = Column('Debito', Float)
    credito = Column('Credito', Float)
    
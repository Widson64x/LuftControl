from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mssql import MONEY

from .Base import SqlServerModel


class PlanoConta(SqlServerModel):
    """Estrutura do plano de contas contábil."""

    __tablename__ = 'PlanoConta'

    Codigo_ContaContabil = Column(Numeric, primary_key=True)
    Codigo_ContaContabilMasc = Column(String)
    Numero_ContaContabil = Column(String)
    Descricao_ContaContabil = Column(String)
    Nivel_ContaContabil = Column(Integer)
    Codigo_ContaReduzida = Column(Numeric)
    Grupo_ContaContabil = Column(Integer)
    Natureza_ContaContabil = Column(String)
    Tipo_ContaContabil = Column(String)
    Tipo_CondicaoNormal = Column(String)
    Codigo_GrupoContabil = Column(Numeric)
    Data_InicioValidade = Column(DateTime)
    Data_FimValidade = Column(DateTime)
    Codigo_ContaContabilPai = Column(Numeric)
    Obs_ContaContabil = Column(Text)

    itensOrcamento = relationship("BudgetItem", back_populates="contaContabil")
    contasPagar = relationship("ContaPagar", back_populates="contaContabil")


class CentroCusto(SqlServerModel):
    """Centro de custo da empresa."""

    __tablename__ = 'CentroCusto'

    Codigo_CentroCusto = Column(Numeric, primary_key=True)
    Codigo_CentroCustoMasc = Column(String)
    Numero_CentroCusto = Column(String)
    Codigo_CentroCustoFim = Column(Numeric)
    Nome_CentroCusto = Column(String)
    Nivel_CentroCusto = Column(String)
    Opcao_UltimoNivel = Column(String)
    Codigo_Integracao = Column(String)
    Codigo_Empresa = Column(Integer)
    Data_Obsoleto = Column(DateTime)
    Obs_CentroCusto = Column(Text)

    itensOrcamento = relationship("BudgetItem", back_populates="centroResponsavel")
    contasPagar = relationship("ContaPagar", back_populates="centroCusto")


class ContaPagar(SqlServerModel):
    """Fluxo principal de contas a pagar."""

    __tablename__ = 'ContaPagar'

    Codigo_ContaPagar = Column(Integer, primary_key=True)
    Codigo_Empresa = Column(Integer)
    Codigo_EmpresaMatriz = Column(Integer)
    Codigo_Fornecedor = Column(Integer, ForeignKey('Luftinforma.dbo.Fornecedor.Codigo_Fornecedor'))
    Codigo_ContaContabil = Column(Numeric, ForeignKey('Luftinforma.dbo.PlanoConta.Codigo_ContaContabil'))
    Codigo_CentroCusto = Column(Numeric, ForeignKey('Luftinforma.dbo.CentroCusto.Codigo_CentroCusto'))
    Opcao_TipoDocumento = Column(String)
    Numero_Documento = Column(String)
    Sequencia_Item = Column(String)
    Codigo_Item = Column(String)
    Descricao_Item = Column(String)
    Data_Emissao = Column(DateTime)
    Data_Digitacao = Column(DateTime)
    Data_Aprovacao = Column(DateTime)
    Valor_ContaPagar = Column(MONEY)
    Valor_RecebidoNotaFiscal = Column(MONEY)
    Opcao_StatusContaPagar = Column(Integer)
    Codigo_UltimoAprovador = Column(Integer)
    Nome_UltimoAprovador = Column(String)
    Data_Importacao = Column(DateTime)
    Opcao_AlteracaoManual = Column(Boolean)
    Codigo_UsuarioAlteracaoManual = Column(Integer)
    Codigo_BudgetItem = Column(Integer, ForeignKey('Luftinforma.dbo.BudgetItem.Codigo_BudgetItem'))
    Codigo_CondicaoPagamento = Column(String)
    DescricaoCondicaoPagamento = Column(String)

    budgetItem = relationship("BudgetItem", back_populates="contasPagar")
    centroCusto = relationship("CentroCusto", back_populates="contasPagar")
    fornecedor = relationship("Fornecedor", back_populates="contasPagar")
    contaContabil = relationship("PlanoConta", back_populates="contasPagar")
    notasFiscais = relationship("ContaPagarNotaFiscal", back_populates="contaPagar")


class ContaPagarNotaFiscal(SqlServerModel):
    """Documentos fiscais associados a pagamentos."""

    __tablename__ = 'ContaPagarNotaFiscal'

    Codigo_ContaPagar = Column(Integer, ForeignKey('Luftinforma.dbo.ContaPagar.Codigo_ContaPagar'), primary_key=True)
    Numero_NotaFiscal = Column(String, primary_key=True)
    Serie_NotaFiscal = Column(String, primary_key=True)
    Data_Emissao = Column(DateTime)
    Data_Digitacao = Column(DateTime)
    Valor_NotaFiscal = Column(MONEY)
    Data_Importacao = Column(DateTime)

    contaPagar = relationship("ContaPagar", back_populates="notasFiscais")
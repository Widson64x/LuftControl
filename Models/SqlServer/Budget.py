from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mssql import MONEY

from .Base import SqlServerModel


class Budget(SqlServerModel):
    """Cabeçalho dos orçamentos."""

    __tablename__ = 'Budget'

    Codigo_Budget = Column(Integer, primary_key=True)
    Descricao_Budget = Column(String)
    Ano_Vigencia = Column(Integer)
    Obs_Budget = Column(Text)

    itensOrcamento = relationship("BudgetItem", back_populates="budgetOriginal")


class BudgetGrupo(SqlServerModel):
    """Grupo de classificação dos itens orçamentários."""

    __tablename__ = 'BudgetGrupo'

    Codigo_BudgetGrupo = Column(Integer, primary_key=True)
    Descricao_BudgetGrupo = Column(String)

    itensOrcamento = relationship("BudgetItem", back_populates="grupoOrcamento")


class BudgetClienteGrupo(SqlServerModel):
    """Orçamentos categorizados por grupos de clientes."""

    __tablename__ = 'BudgetClienteGrupo'

    Codigo_ClienteGrupo = Column(Integer, primary_key=True)
    Ano_Vigencia = Column(Integer)
    Mes_Budget = Column(Integer)
    Valor_Frete = Column(MONEY)
    Valor_Armazenagem = Column(MONEY)
    Valor_TotalBudget = Column(MONEY)


class BudgetItem(SqlServerModel):
    """Linhas e valores do orçamento."""

    __tablename__ = 'BudgetItem'

    Codigo_BudgetItem = Column(Integer, primary_key=True)
    Codigo_Budget = Column(Integer, ForeignKey('Luftinforma.dbo.Budget.Codigo_Budget'))
    Codigo_Empresa = Column(Integer)
    Codigo_EmpresaMatriz = Column(Integer)
    Codigo_ContaContabil = Column(Numeric, ForeignKey('Luftinforma.dbo.PlanoConta.Codigo_ContaContabil'))
    Descricao_BudgetItem = Column(String)
    Codigo_BudgetGrupo = Column(Integer, ForeignKey('Luftinforma.dbo.BudgetGrupo.Codigo_BudgetGrupo'))
    Codigo_Fornecedor = Column(Integer, ForeignKey('Luftinforma.dbo.Fornecedor.Codigo_Fornecedor'))
    Codigo_Cliente = Column(Integer)
    Codigo_CentroCusto = Column(Numeric, ForeignKey('Luftinforma.dbo.CentroCusto.Codigo_CentroCusto'))
    Valor_JaneiroO = Column(MONEY)
    Valor_JaneiroR = Column(MONEY)
    Valor_FevereiroO = Column(MONEY)
    Valor_FevereiroR = Column(MONEY)
    Valor_MarcoO = Column(MONEY)
    Valor_MarcoR = Column(MONEY)
    Valor_AbrilO = Column(MONEY)
    Valor_AbrilR = Column(MONEY)
    Valor_MaioO = Column(MONEY)
    Valor_MaioR = Column(MONEY)
    Valor_JunhoO = Column(MONEY)
    Valor_JunhoR = Column(MONEY)
    Valor_JulhoO = Column(MONEY)
    Valor_JulhoR = Column(MONEY)
    Valor_AgostoO = Column(MONEY)
    Valor_AgostoR = Column(MONEY)
    Valor_SetembroO = Column(MONEY)
    Valor_SetembroR = Column(MONEY)
    Valor_OutubroO = Column(MONEY)
    Valor_OutubroR = Column(MONEY)
    Valor_NovembroO = Column(MONEY)
    Valor_NovembroR = Column(MONEY)
    Valor_DezembroO = Column(MONEY)
    Valor_DezembroR = Column(MONEY)
    Valor_TotalAnoO = Column(MONEY)
    Valor_TotalAnoR = Column(MONEY)
    Valor_SaldoDisponivel = Column(MONEY)
    Obs_BudgetItem = Column(String)

    budgetOriginal = relationship("Budget", back_populates="itensOrcamento")
    grupoOrcamento = relationship("BudgetGrupo", back_populates="itensOrcamento")
    contaContabil = relationship("PlanoConta", back_populates="itensOrcamento")
    fornecedorOrigem = relationship("Fornecedor", back_populates="itensOrcamento")
    centroResponsavel = relationship("CentroCusto", back_populates="itensOrcamento")
    historicosRecalculo = relationship("BudgetItemRecHistorico", back_populates="budgetItem")
    contasPagar = relationship("ContaPagar", back_populates="budgetItem")


class BudgetItemRecHistorico(SqlServerModel):
    """Histórico de recálculo ou versionamento do orçamento."""

    __tablename__ = 'BudgetItemRecHistorico'

    Codigo_Reclassificacao = Column(Integer, primary_key=True)
    Codigo_BudgetItem = Column(Integer, ForeignKey('Luftinforma.dbo.BudgetItem.Codigo_BudgetItem'))
    Acao_Reclassificacao = Column(String)
    Mes_Reclassificado = Column(String)
    Valor_Reclassificado = Column(MONEY)
    Codigo_UsuarioReclassificacao = Column(Integer)
    Data_Reclassificacao = Column(DateTime)

    budgetItem = relationship("BudgetItem", back_populates="historicosRecalculo")
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .Base import SqlServerModel


class Fornecedor(SqlServerModel):
    """Cadastro geral de fornecedores."""

    __tablename__ = 'Fornecedor'

    Codigo_Fornecedor = Column(Integer, primary_key=True)
    Nome_Fornecedor = Column(String)
    Telefone_Fornecedor = Column(String)
    Fax_Fornecedor = Column(String)
    Email_Fornecedor = Column(String)
    Endereco_Fornecedor = Column(String)
    Numero_Fornecedor = Column(Integer)
    End_Comp_Fornecedor = Column(String)
    Bairro_Fornecedor = Column(String)
    Codigo_Pais = Column(Numeric)
    Sigla_Estado = Column(String)
    Codigo_Municipio = Column(Numeric)
    Cep_Fornecedor = Column(String)
    Opcao_TipoFornecedor = Column(String)
    CNP_Fornecedor = Column(String)
    IE_Fornecedor = Column(String)
    IM_Fornecedor = Column(String)
    Obs_Fornecedor = Column(Text)

    itensOrcamento = relationship("BudgetItem", back_populates="fornecedorOrigem")
    contasPagar = relationship("ContaPagar", back_populates="fornecedor")
    integracoesSistema = relationship("FornecedorIntegracaoSistema", back_populates="fornecedor")


class FornecedorIntegracaoSistema(SqlServerModel):
    """Parâmetros de integração dos fornecedores com sistemas externos."""

    __tablename__ = 'FornecedorIntegracaoSistema'

    Codigo_Fornecedor = Column(Integer, ForeignKey('Luftinforma.dbo.Fornecedor.Codigo_Fornecedor'), primary_key=True)
    Nome_SistemaOrigem = Column(String, primary_key=True)
    Codigo_Integracao = Column(String)

    fornecedor = relationship("Fornecedor", back_populates="integracoesSistema")
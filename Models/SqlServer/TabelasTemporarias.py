from sqlalchemy import Column, DateTime, Float, Integer, Numeric, String
from sqlalchemy.dialects.mssql import MONEY

from .Base import TemporarySqlServerModel


class ContaPagarAprovTempA(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarAprovTempA."""

    __tablename__ = 'ContaPagarAprovTempA'

    Codigo = Column(Integer, primary_key=True)
    CR_NIVEL = Column(Integer)
    CR_STATUS = Column(Integer)
    CR_DATALIB = Column(DateTime)
    CR_USERLIB = Column(Integer)
    AL_DESC = Column(String)


class ContaPagarAprovTempATemp(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarAprovTempA_Temp."""

    __tablename__ = 'ContaPagarAprovTempA_Temp'

    Codigo = Column(Integer, primary_key=True)
    CR_NIVEL = Column(Integer)
    CR_STATUS = Column(Integer)
    CR_DATALIB = Column(DateTime)
    CR_USERLIB = Column(Integer)
    AL_DESC = Column(String)


class ContaPagarNotaFiscalTempA(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarNotaFiscalTempA."""

    __tablename__ = 'ContaPagarNotaFiscalTempA'

    codigo = Column(Integer, primary_key=True)
    numNF = Column(String)
    serieNF = Column(String)
    dataEmissao = Column(DateTime)
    dataDigitacao = Column(DateTime)
    valorNF = Column(MONEY)


class ContaPagarNotaFiscalTempATemp(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarNotaFiscalTempA_Temp."""

    __tablename__ = 'ContaPagarNotaFiscalTempA_Temp'

    codigo = Column(Integer, primary_key=True)
    numNF = Column(String)
    serieNF = Column(String)
    dataEmissao = Column(DateTime)
    dataDigitacao = Column(DateTime)
    valorNF = Column(MONEY)


class ContaPagarTempA(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarTempA."""

    __tablename__ = 'ContaPagarTempA'

    Codigo = Column(Integer, primary_key=True)
    Empresa = Column(Integer)
    Filial = Column(String)
    Fornecedor = Column(String)
    ContaContabil = Column(Numeric)
    CentroCusto = Column(Numeric)
    TipoDocumento = Column(String)
    NumeroDocumento = Column(String)
    SeqItem = Column(String)
    DescItem = Column(String)
    DataEmissao = Column(DateTime)
    DataDigitacao = Column(DateTime)
    DataAprovacao = Column(DateTime)
    ValorPagar = Column(MONEY)
    Status = Column(Integer)
    CodigoUltimoAprovador = Column(Integer)
    NomeUltimoAprovador = Column(String)


class ContaPagarTempATemp(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarTempA_Temp."""

    __tablename__ = 'ContaPagarTempA_Temp'

    Codigo = Column(Integer, primary_key=True)
    Empresa = Column(Integer)
    Filial = Column(String)
    Fornecedor = Column(String)
    ContaContabil = Column(Numeric)
    CentroCusto = Column(Numeric)
    TipoDocumento = Column(String)
    NumeroDocumento = Column(String)
    SeqItem = Column(String)
    DescItem = Column(String)
    DataEmissao = Column(DateTime)
    DataDigitacao = Column(DateTime)
    DataAprovacao = Column(DateTime)
    ValorPagar = Column(MONEY)
    Status = Column(Integer)
    CodigoUltimoAprovador = Column(Integer)
    NomeUltimoAprovador = Column(String)


class ContaPagarTempB(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarTempB."""

    __tablename__ = 'ContaPagarTempB'

    Codigo = Column(Integer, primary_key=True)
    Empresa = Column(Integer)
    Filial = Column(String)
    Fornecedor = Column(String)
    ContaContabil = Column(Numeric)
    CentroCusto = Column(Numeric)
    TipoDocumento = Column(String)
    NumeroDocumento = Column(String)
    SeqItem = Column(String)
    CodItem = Column(String)
    DescItem = Column(String)
    DataEmissao = Column(DateTime)
    DataDigitacao = Column(DateTime)
    DataAprovacao = Column(DateTime)
    ValorPagar = Column(MONEY)
    Status = Column(Integer)
    CodigoUltimoAprovador = Column("CodigContaPagarNotaFiscaloUltimoAprovador", Integer)
    NomeUltimoAprovador = Column(String)
    CodigoCondicaoPagamento = Column(String)
    DescricaoCondicaoPagamento = Column(String)


class ContaPagarTempBTemp(TemporarySqlServerModel):
    """Mapeia a tabela temporária ContaPagarTempB_Temp."""

    __tablename__ = 'ContaPagarTempB_Temp'

    Codigo = Column(Integer, primary_key=True)
    Empresa = Column(Integer)
    Filial = Column(String)
    Fornecedor = Column(String)
    ContaContabil = Column(Numeric)
    CentroCusto = Column(Numeric)
    TipoDocumento = Column(String)
    NumeroDocumento = Column(String)
    SeqItem = Column(String)
    CodItem = Column(String)
    DescItem = Column(String)
    DataEmissao = Column(DateTime)
    DataDigitacao = Column(DateTime)
    DataAprovacao = Column(DateTime)
    ValorPagar = Column(MONEY)
    Status = Column(Integer)
    CodigoUltimoAprovador = Column("CodigContaPagarNotaFiscaloUltimoAprovador", Integer)
    NomeUltimoAprovador = Column(String)
    CodigoCondicaoPagamento = Column(String)
    DescricaoCondicaoPagamento = Column(String)


class FornecedorMicrosigaTemp(TemporarySqlServerModel):
    """Tabela temporária de importação de fornecedores do Microsiga."""

    __tablename__ = 'FornecedorMicrosiga_Temp'

    Codigo_Seq = Column(Integer, primary_key=True)
    NomeFornecedor = Column(String)
    TelFornecedor = Column(String)
    FaxFornecedor = Column(String)
    EmailFornecedor = Column(String)
    EndFornecedor = Column(String)
    EndNumFornecedor = Column(Integer)
    end_comp = Column(String)
    BairroFornecedor = Column(String)
    cod_pais = Column(Float)
    Sigla_Estado = Column(String)
    CodMunicipio = Column(String)
    Municipio = Column(String)
    CepFornecedor = Column(String)
    TipoFornecedor = Column(String)
    CnpFornecedor = Column(String)
    IeFornecedor = Column(String)
    ImFornecedor = Column(String)
    CodigoIntegracao = Column(String)
    data_proc = Column(DateTime)

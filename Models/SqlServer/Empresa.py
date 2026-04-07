from sqlalchemy import Column, Integer, String

from .Base import SqlServerModel


class Empresa(SqlServerModel):
    __tablename__ = 'Empresa'

    Codigo_Empresa = Column(Integer, primary_key=True)
    CNPJ_Empresa = Column(String)
    Nome_Empresa = Column(String)


class TbFilial(SqlServerModel):
    __tablename__ = 'tb_filial'
    __table_args__ = {"schema": "intec.dbo"}

    cgc = Column(String, primary_key=True)
    nomefilial = Column(String)
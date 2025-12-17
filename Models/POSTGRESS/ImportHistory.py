from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class ImportHistory(Base):
    """
    Tabela de auditoria para importações de dados.
    Controla duplicidade por competência e permite reversão (rollback).
    """
    __tablename__ = 'System_Import_History'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Usuario = Column(String(100), nullable=False)
    Tabela_Destino = Column(String(100), nullable=False) # Ex: Razao_Dados_Origem_INTEC
    Competencia = Column(String(7), nullable=False)      # Formato: YYYY-MM
    Nome_Arquivo = Column(String(255), nullable=False)
    Data_Importacao = Column(DateTime, default=datetime.now)
    
    Status = Column(String(20), default='Ativo')         # Ativo, Revertido
    
    # Campos de Reversão
    Data_Reversao = Column(DateTime, nullable=True)
    Usuario_Reversao = Column(String(100), nullable=True)
    Motivo_Reversao = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ImportHistory({self.Tabela_Destino}, {self.Competencia}, {self.Status})>"

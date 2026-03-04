# Models/POSTGRESS/CTL_Ajustes.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class CtlAjusteLog(Base):
    __tablename__ = 'Tb_CTL_Ajuste_Log'
    __table_args__ = {"schema": "Dre_Schema"}

    Id_Log = Column(Integer, primary_key=True, autoincrement=True)
    
    # Vinculo com a Tabela Consolidada (usamos o Id e a Fonte juntos)
    Id_Registro = Column(Integer)
    Fonte_Registro = Column(Text)
    
    Campo_Alterado = Column(String)
    Valor_Antigo = Column(String)
    Valor_Novo = Column(String)
    Usuario_Acao = Column(String)
    Data_Acao = Column(DateTime, default=datetime.datetime.now)
    Tipo_Acao = Column(String) # Ex: 'UPDATE', 'INATIVADO', 'APROVADO'

# Se a tabela CtlAjusteIntergrupoLog for necessária, podes mantê-la aqui também.
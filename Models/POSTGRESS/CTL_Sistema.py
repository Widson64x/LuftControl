# Models/POSTGRESS/CTL_Sistema.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class CtlSysHistImportacao(Base):
    __tablename__ = 'Tb_CTL_Sys_Hist_Importacao'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True)
    Usuario = Column(String(100), nullable=False)
    Tabela_Destino = Column(String(100), nullable=False) 
    Competencia = Column(String(7), nullable=False)      
    Nome_Arquivo = Column(String(255), nullable=False)
    Data_Importacao = Column(DateTime, default=datetime.now)
    Status = Column(String(20), default='Ativo')         
    
    Data_Reversao = Column(DateTime, nullable=True)
    Usuario_Reversao = Column(String(100), nullable=True)
    Motivo_Reversao = Column(Text, nullable=True)

class CtlSysConfigImportacao(Base):
    __tablename__ = 'Tb_CTL_Sys_Config_Importacao'
    __table_args__ = {"schema": "Dre_Schema"}

    Source_Table = Column(String(100), primary_key=True) 
    Mapping_Json = Column(Text, nullable=True)           
    Transforms_Json = Column(Text, nullable=True)        
    Last_Updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def set_mapping(self, mapping_dict):
        self.Mapping_Json = json.dumps(mapping_dict)

    def get_mapping(self):
        if not self.Mapping_Json: return {}
        return json.loads(self.Mapping_Json)

    def set_transforms(self, transforms_dict):
        self.Transforms_Json = json.dumps(transforms_dict)

    def get_transforms(self):
        if not self.Transforms_Json: return {}
        return json.loads(self.Transforms_Json)
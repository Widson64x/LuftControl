from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class ImportConfig(Base):
    """
    Armazena a última configuração de mapeamento e transformação usada para cada origem.
    """
    __tablename__ = 'System_Import_Config'
    __table_args__ = {"schema": "Dre_Schema"}

    Source_Table = Column(String(100), primary_key=True) # Ex: Razao_Dados_Origem_INTEC
    Mapping_Json = Column(Text, nullable=True)           # Dicionário salvo como Texto/JSON
    Transforms_Json = Column(Text, nullable=True)        # Dicionário salvo como Texto/JSON
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
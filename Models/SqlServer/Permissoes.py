# Arquivo: Luft-Control/Models/SqlServer/Permissoes.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from datetime import datetime
from .Base import SqlServerModel

class Tb_Sistema(SqlServerModel):
    __tablename__ = "Tb_Sistema"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Sistema = Column(Integer, primary_key=True, autoincrement=True)
    Nome_Sistema = Column(String(100), unique=True, nullable=False)
    Descricao_Sistema = Column(String(255))
    Ativo = Column(Boolean, default=True)

class Tb_Permissao(SqlServerModel):
    __tablename__ = "Tb_Permissao"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Permissao = Column(Integer, primary_key=True, autoincrement=True)
    Id_Sistema = Column(Integer, ForeignKey("intec.dbo.Tb_Sistema.Id_Sistema"), nullable=False)
    Chave_Permissao = Column(String(100), nullable=False)
    Descricao_Permissao = Column(String(255))
    Categoria_Permissao = Column(String(50))

class Tb_PermissaoGrupo(SqlServerModel):
    __tablename__ = "Tb_PermissaoGrupo"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    
    # REMOVIDO o ForeignKey para evitar o erro de Cross-Database com o LuftInforma
    Codigo_UsuarioGrupo = Column(Integer, nullable=False) 
    
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_Permissao.Id_Permissao"))

class Tb_PermissaoUsuario(SqlServerModel):
    __tablename__ = "Tb_PermissaoUsuario"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Vinculo = Column(Integer, primary_key=True, autoincrement=True)
    
    # REMOVIDO o ForeignKey para evitar o erro de Cross-Database com o LuftInforma
    Codigo_Usuario = Column(Integer, nullable=False) 
    
    Id_Permissao = Column(Integer, ForeignKey("intec.dbo.Tb_Permissao.Id_Permissao"))
    Conceder = Column(Boolean, default=True)

class Tb_LogAcesso(SqlServerModel):
    __tablename__ = "Tb_LogAcesso"
    __table_args__ = {"schema": "intec.dbo"}

    Id_Log = Column(Integer, primary_key=True, autoincrement=True)
    Id_Sistema = Column(Integer, ForeignKey("intec.dbo.Tb_Sistema.Id_Sistema"), nullable=True)
    Id_Usuario = Column(Integer, nullable=True)
    Nome_Usuario = Column(String(150))
    Rota_Acessada = Column(String(200))
    Metodo_Http = Column(String(10))
    Ip_Origem = Column(String(50))
    Permissao_Exigida = Column(String(100))
    Acesso_Permitido = Column(Boolean)
    Data_Hora = Column(DateTime, default=datetime.now)

    # NOVAS COLUNAS:
    Parametros_Requisicao = Column(Text, nullable=True) # Vai armazenar o que o usuário enviou
    Resposta_Acao = Column(Text, nullable=True)
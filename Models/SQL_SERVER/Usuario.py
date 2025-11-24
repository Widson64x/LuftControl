from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

# Cria a base para os modelos ORM
Base = declarative_base()

# Modelo ORM para a tabela de usuários
class Usuario(Base):
    __tablename__ = "usuario"

    Codigo_Usuario = Column(Integer, primary_key=True, autoincrement=True)  # Chave primária
    Login_Usuario = Column(String)                      # Nome do usuário
    Nome_Usuario = Column(String)                 
    Email_Usuario = Column(String)                      
    codigo_usuariogrupo = Column(Integer, ForeignKey("usuariogrupo.codigo_usuariogrupo"))

class UsuarioGrupo(Base):
    __tablename__ = "usuariogrupo"

    codigo_usuariogrupo = Column(Integer, primary_key=True, autoincrement=True)
    
    # Adicione os campos necessários
    Sigla_UsuarioGrupo = Column(String) 
    Descricao_UsuarioGrupo = Column(String)  
    Permite_Cadastrar = Column(Integer)  
    Permite_Alterar = Column(Integer)  
    Permite_Excluir = Column(Integer)  

class MenuAcesso(Base):
    __tablename__ = "MenuAcesso"

    Codigo_MenuAcesso = Column(Integer, primary_key=True, autoincrement=True)
    Codigo_UsuarioGrupo = Column(Integer, ForeignKey("usuariogrupo.codigo_usuariogrupo"))
    Codigo_Menu = Column(Integer, ForeignKey("Menu.Codigo_Menu"))

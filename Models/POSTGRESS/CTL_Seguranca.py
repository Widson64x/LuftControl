# Models/POSTGRESS/CTL_Seguranca.py
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Tabela associativa: Perfil <-> Permissao
perfil_permissao_table = Table('Tb_CTL_Seg_Perfil_Permissao', Base.metadata,
    Column('perfil_id', Integer, ForeignKey('Dre_Schema.Tb_CTL_Seg_Perfil.Id'), primary_key=True),
    Column('permissao_id', Integer, ForeignKey('Dre_Schema.Tb_CTL_Seg_Permissao.Id'), primary_key=True),
    schema='Dre_Schema'
)

# Tabela associativa: Usuario <-> Permissao (Exceções/Diretas)
usuario_permissao_table = Table('Tb_CTL_Seg_Usuario_Permissao', Base.metadata,
    Column('usuario_id', Integer, ForeignKey('Dre_Schema.Tb_CTL_Seg_Usuario.Id'), primary_key=True),
    Column('permissao_id', Integer, ForeignKey('Dre_Schema.Tb_CTL_Seg_Permissao.Id'), primary_key=True),
    schema='Dre_Schema'
)

class CtlSegPermissao(Base):
    __tablename__ = 'Tb_CTL_Seg_Permissao'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Slug = Column(String(50), unique=True, nullable=False)
    Descricao = Column(String(100))

class CtlSegPerfil(Base):
    __tablename__ = 'Tb_CTL_Seg_Perfil'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Nome = Column(String(50), unique=True, nullable=False)
    Descricao = Column(String(100))
    
    permissions = relationship("CtlSegPermissao", secondary=perfil_permissao_table, backref="perfis")

class CtlSegUsuario(Base):
    __tablename__ = 'Tb_CTL_Seg_Usuario'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Login_Usuario = Column(String(100), unique=True, nullable=False)
    
    # Aqui removemos o 'RoleId', agora o Python vai buscar PerfilId normalmente!
    PerfilId = Column(Integer, ForeignKey('Dre_Schema.Tb_CTL_Seg_Perfil.Id'), nullable=True)
    perfil = relationship("CtlSegPerfil")

    direct_permissions = relationship("CtlSegPermissao", secondary=usuario_permissao_table)
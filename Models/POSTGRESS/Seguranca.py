# Models/POSTGRESS/Seguranca.py
from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Tabela: Role <-> Permission (Já existia)
role_permission_table = Table('SEC_Role_Permissions', Base.metadata,
    Column('role_id', Integer, ForeignKey('Dre_Schema.SEC_Roles.Id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('Dre_Schema.SEC_Permissions.Id'), primary_key=True),
    schema='Dre_Schema'
)

# [NOVO] Tabela: User <-> Permission (Permissão direta/exceção)
user_permission_table = Table('SEC_User_Permissions', Base.metadata,
    Column('user_id', Integer, ForeignKey('Dre_Schema.SEC_Users.Id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('Dre_Schema.SEC_Permissions.Id'), primary_key=True),
    schema='Dre_Schema'
)

class SecPermission(Base):
    __tablename__ = 'SEC_Permissions'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Slug = Column(String(50), unique=True, nullable=False)
    Descricao = Column(String(100))

class SecRole(Base):
    __tablename__ = 'SEC_Roles'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Nome = Column(String(50), unique=True, nullable=False)
    Descricao = Column(String(100))
    
    # Relação com Permissões
    permissions = relationship("SecPermission", secondary=role_permission_table, backref="roles")

class SecUserExtension(Base):
    __tablename__ = 'SEC_Users'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Login_Usuario = Column(String(100), unique=True, nullable=False)
    
    # Vinculo com Grupo (1 para N)
    RoleId = Column(Integer, ForeignKey('Dre_Schema.SEC_Roles.Id'), nullable=True)
    role = relationship("SecRole")

    # [NOVO] Vinculo Direto com Permissões (N para N)
    direct_permissions = relationship("SecPermission", secondary=user_permission_table)
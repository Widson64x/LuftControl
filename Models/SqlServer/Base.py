from sqlalchemy.orm import declarative_base

SQLSERVER_SCHEMA = "Luftinforma.dbo"

# Base compartilhada por todos os models ORM do SQL Server.
Base = declarative_base()


class SqlServerModel(Base):
	__abstract__ = True
	__table_args__ = {"schema": SQLSERVER_SCHEMA}


class TemporarySqlServerModel(SqlServerModel):
	__abstract__ = True
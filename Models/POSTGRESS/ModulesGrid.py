# Models/POSTGRESS/ModulesGrid.py
"""
Modelos ORM para o módulo Modules-Grid.
Gerencia ajustes manuais sobre a view Razao_Dados_Consolidado.

Tabelas:
- RazaoAjusteManual: Sobrescrições de valores aprovadas
- RazaoAjusteLog: Log de todas as alterações (pendentes, aprovadas, reprovadas)
- RazaoAjusteAprovacao: Controle de aprovações/reprovações
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class RazaoAjusteManual(Base):
    """
    Armazena os ajustes manuais APROVADOS que devem sobrescrever valores da view.
    Cada registro representa uma sobrescrição ativa para uma linha específica da view.

    A chave única da linha na view é composta por: origem + Data + Numero + Conta + Item
    """
    __tablename__ = 'Razao_Ajuste_Manual'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True, autoincrement=True)

    # Chave composta para identificar a linha na view
    Origem = Column(String(50), nullable=False)  # 'FARMA' ou 'FARMADIST'
    Data = Column(DateTime, nullable=False)
    Numero = Column(String(100), nullable=False)
    Conta = Column(String(100), nullable=False)
    Item = Column(String(100), nullable=True)

    # Campos que podem ser sobrescritos (nullable = valor não sobrescrito)
    Titulo_Conta_Ajustado = Column(String(255), nullable=True)
    Descricao_Ajustado = Column(Text, nullable=True)
    Contra_Partida_Ajustado = Column(String(255), nullable=True)
    Filial_Ajustado = Column(String(100), nullable=True)
    Centro_Custo_Ajustado = Column(String(100), nullable=True)
    Item_Ajustado = Column(String(100), nullable=True)
    Cod_Cl_Valor_Ajustado = Column(String(100), nullable=True)
    Debito_Ajustado = Column(Float, nullable=True)
    Credito_Ajustado = Column(Float, nullable=True)
    Saldo_Ajustado = Column(Float, nullable=True)  # Para zerar ou sobrescrever o saldo calculado

    # Campo NaoOperacional (True se Item = 10190 ou se usuário marcou manualmente)
    NaoOperacional = Column(Boolean, default=False)
    NaoOperacional_Manual = Column(Boolean, default=False)  # True se foi alterado manualmente

    # Metadados
    Ativo = Column(Boolean, default=True)
    Data_Criacao = Column(DateTime, server_default=func.now())
    Data_Atualizacao = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<RazaoAjusteManual(Id={self.Id}, Conta='{self.Conta}', Data='{self.Data}')>"


class RazaoAjusteLog(Base):
    """
    Log completo de todas as alterações realizadas no módulo.
    Cada alteração de campo gera um registro aqui, independente do status de aprovação.
    """
    __tablename__ = 'Razao_Ajuste_Log'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True, autoincrement=True)

    # Referência ao ajuste (pode ser null antes de criar o ajuste)
    Id_Ajuste = Column(Integer, ForeignKey('Dre_Schema.Razao_Ajuste_Manual.Id'), nullable=True)

    # Identificação da linha na view (para rastreabilidade mesmo sem ajuste criado)
    Origem = Column(String(50), nullable=False)
    Data_Registro = Column(DateTime, nullable=False)  # Data do registro na view
    Numero = Column(String(100), nullable=False)
    Conta = Column(String(100), nullable=False)
    Item = Column(String(100), nullable=True)

    # Detalhes da alteração
    Campo_Alterado = Column(String(100), nullable=False)  # Nome do campo que foi alterado
    Valor_Anterior = Column(Text, nullable=True)  # Valor antes da alteração (serializado como string)
    Valor_Novo = Column(Text, nullable=True)  # Novo valor proposto

    # Auditoria da alteração
    Usuario_Alteracao = Column(String(100), nullable=False)
    Data_Alteracao = Column(DateTime, server_default=func.now())

    # Status do log
    # Pendente: aguardando aprovação
    # Aprovado: aprovado e aplicado
    # Reprovado: rejeitado pelo aprovador
    # Cancelado: cancelado pelo próprio solicitante
    Status = Column(String(20), default='Pendente')

    # Auditoria da aprovação/reprovação
    Usuario_Aprovacao = Column(String(100), nullable=True)
    Data_Aprovacao = Column(DateTime, nullable=True)
    Motivo_Reprovacao = Column(Text, nullable=True)

    def __repr__(self):
        return f"<RazaoAjusteLog(Id={self.Id}, Campo='{self.Campo_Alterado}', Status='{self.Status}')>"


class RazaoAjusteAprovacao(Base):
    """
    Controle de aprovações em lote e histórico de decisões.
    Permite aprovar/reprovar múltiplas alterações de uma vez.
    """
    __tablename__ = 'Razao_Ajuste_Aprovacao'
    __table_args__ = {"schema": "Dre_Schema"}

    Id = Column(Integer, primary_key=True, autoincrement=True)

    # Referência ao log de alteração
    Id_Log = Column(Integer, ForeignKey('Dre_Schema.Razao_Ajuste_Log.Id'), nullable=False)

    # Decisão
    Decisao = Column(String(20), nullable=False)  # 'Aprovado' ou 'Reprovado'

    # Auditoria
    Usuario_Decisao = Column(String(100), nullable=False)
    Data_Decisao = Column(DateTime, server_default=func.now())
    Observacao = Column(Text, nullable=True)

    # IP e contexto (para auditoria de segurança)
    IP_Origem = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<RazaoAjusteAprovacao(Id={self.Id}, Decisao='{self.Decisao}')>"


# ============================================================================
# QUERIES SQL PARA CRIAÇÃO DAS TABELAS
# ============================================================================
"""
Execute as queries abaixo diretamente no PostgreSQL para criar as tabelas:

-- ==========================================================================
-- TABELA: Razao_Ajuste_Manual
-- Armazena os ajustes manuais APROVADOS que sobrescrevem valores da view
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Manual" (
    "Id" SERIAL PRIMARY KEY,

    -- Chave composta para identificar a linha na view
    "Origem" VARCHAR(50) NOT NULL,
    "Data" TIMESTAMP NOT NULL,
    "Numero" VARCHAR(100) NOT NULL,
    "Conta" VARCHAR(100) NOT NULL,
    "Item" VARCHAR(100),

    -- Campos que podem ser sobrescritos
    "Titulo_Conta_Ajustado" VARCHAR(255),
    "Descricao_Ajustado" TEXT,
    "Contra_Partida_Ajustado" VARCHAR(255),
    "Filial_Ajustado" VARCHAR(100),
    "Centro_Custo_Ajustado" VARCHAR(100),
    "Item_Ajustado" VARCHAR(100),
    "Cod_Cl_Valor_Ajustado" VARCHAR(100),
    "Debito_Ajustado" DOUBLE PRECISION,
    "Credito_Ajustado" DOUBLE PRECISION,
    "Saldo_Ajustado" DOUBLE PRECISION,

    -- Campo NaoOperacional
    "NaoOperacional" BOOLEAN DEFAULT FALSE,
    "NaoOperacional_Manual" BOOLEAN DEFAULT FALSE,

    -- Metadados
    "Ativo" BOOLEAN DEFAULT TRUE,
    "Data_Criacao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Data_Atualizacao" TIMESTAMP,

    -- Índice único para evitar duplicatas
    CONSTRAINT "uq_razao_ajuste_linha" UNIQUE ("Origem", "Data", "Numero", "Conta", "Item")
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_origem" ON "Dre_Schema"."Razao_Ajuste_Manual" ("Origem");
CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_data" ON "Dre_Schema"."Razao_Ajuste_Manual" ("Data");
CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_conta" ON "Dre_Schema"."Razao_Ajuste_Manual" ("Conta");
CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_ativo" ON "Dre_Schema"."Razao_Ajuste_Manual" ("Ativo");

-- ==========================================================================
-- TABELA: Razao_Ajuste_Log
-- Log completo de todas as alterações
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Log" (
    "Id" SERIAL PRIMARY KEY,

    -- Referência ao ajuste
    "Id_Ajuste" INTEGER REFERENCES "Dre_Schema"."Razao_Ajuste_Manual"("Id"),

    -- Identificação da linha na view
    "Origem" VARCHAR(50) NOT NULL,
    "Data_Registro" TIMESTAMP NOT NULL,
    "Numero" VARCHAR(100) NOT NULL,
    "Conta" VARCHAR(100) NOT NULL,
    "Item" VARCHAR(100),

    -- Detalhes da alteração
    "Campo_Alterado" VARCHAR(100) NOT NULL,
    "Valor_Anterior" TEXT,
    "Valor_Novo" TEXT,

    -- Auditoria da alteração
    "Usuario_Alteracao" VARCHAR(100) NOT NULL,
    "Data_Alteracao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Status
    "Status" VARCHAR(20) DEFAULT 'Pendente',

    -- Auditoria da aprovação
    "Usuario_Aprovacao" VARCHAR(100),
    "Data_Aprovacao" TIMESTAMP,
    "Motivo_Reprovacao" TEXT
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_log_ajuste" ON "Dre_Schema"."Razao_Ajuste_Log" ("Id_Ajuste");
CREATE INDEX IF NOT EXISTS "idx_razao_log_status" ON "Dre_Schema"."Razao_Ajuste_Log" ("Status");
CREATE INDEX IF NOT EXISTS "idx_razao_log_usuario" ON "Dre_Schema"."Razao_Ajuste_Log" ("Usuario_Alteracao");
CREATE INDEX IF NOT EXISTS "idx_razao_log_data" ON "Dre_Schema"."Razao_Ajuste_Log" ("Data_Alteracao");

-- ==========================================================================
-- TABELA: Razao_Ajuste_Aprovacao
-- Histórico de decisões de aprovação
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Aprovacao" (
    "Id" SERIAL PRIMARY KEY,

    -- Referência ao log
    "Id_Log" INTEGER NOT NULL REFERENCES "Dre_Schema"."Razao_Ajuste_Log"("Id"),

    -- Decisão
    "Decisao" VARCHAR(20) NOT NULL,

    -- Auditoria
    "Usuario_Decisao" VARCHAR(100) NOT NULL,
    "Data_Decisao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Observacao" TEXT,

    -- Contexto de segurança
    "IP_Origem" VARCHAR(50)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_aprov_log" ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Id_Log");
CREATE INDEX IF NOT EXISTS "idx_razao_aprov_decisao" ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Decisao");
CREATE INDEX IF NOT EXISTS "idx_razao_aprov_usuario" ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Usuario_Decisao");
"""

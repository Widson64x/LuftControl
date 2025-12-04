-- ============================================================================
-- MÓDULO: Modules-Grid - Ajustes Manuais sobre Razao_Dados_Consolidado
-- ============================================================================
-- Execute este script no PostgreSQL para criar as tabelas necessárias.
-- Schema: Dre_Schema
-- ============================================================================

-- ==========================================================================
-- TABELA: Razao_Ajuste_Manual
-- Armazena os ajustes manuais APROVADOS que sobrescrevem valores da view
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Manual" (
    "Id" SERIAL PRIMARY KEY,

    -- Chave composta para identificar a linha na view
    -- A combinação origem + Data + Numero + Conta + Item identifica unicamente uma linha
    "Origem" VARCHAR(50) NOT NULL,          -- 'FARMA' ou 'FARMADIST'
    "Data" TIMESTAMP NOT NULL,               -- Data do lançamento
    "Numero" VARCHAR(100) NOT NULL,          -- Número do documento
    "Conta" VARCHAR(100) NOT NULL,           -- Conta contábil
    "Item" VARCHAR(100),                     -- Item (pode ser NULL)

    -- Campos que podem ser sobrescritos (NULL = usar valor original da view)
    "Titulo_Conta_Ajustado" VARCHAR(255),
    "Descricao_Ajustado" TEXT,
    "Contra_Partida_Ajustado" VARCHAR(255),
    "Filial_Ajustado" VARCHAR(100),
    "Centro_Custo_Ajustado" VARCHAR(100),
    "Item_Ajustado" VARCHAR(100),
    "Cod_Cl_Valor_Ajustado" VARCHAR(100),
    "Debito_Ajustado" DOUBLE PRECISION,
    "Credito_Ajustado" DOUBLE PRECISION,
    "Saldo_Ajustado" DOUBLE PRECISION,       -- Para sobrescrever saldo calculado

    -- Campo NaoOperacional
    -- TRUE se Item = 10190 (padrão) ou se usuário marcou manualmente
    "NaoOperacional" BOOLEAN DEFAULT FALSE,
    "NaoOperacional_Manual" BOOLEAN DEFAULT FALSE,  -- TRUE se alterado manualmente

    -- Metadados de controle
    "Ativo" BOOLEAN DEFAULT TRUE,            -- FALSE = ajuste desativado/excluído
    "Data_Criacao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Data_Atualizacao" TIMESTAMP,

    -- Constraint de unicidade: não pode haver dois ajustes para a mesma linha
    CONSTRAINT "uq_razao_ajuste_linha" UNIQUE ("Origem", "Data", "Numero", "Conta", "Item")
);

-- Comentários da tabela
COMMENT ON TABLE "Dre_Schema"."Razao_Ajuste_Manual" IS 'Armazena ajustes manuais aprovados que sobrescrevem valores da view Razao_Dados_Consolidado';
COMMENT ON COLUMN "Dre_Schema"."Razao_Ajuste_Manual"."NaoOperacional" IS 'TRUE para itens não operacionais. Padrão: TRUE se Item=10190';
COMMENT ON COLUMN "Dre_Schema"."Razao_Ajuste_Manual"."Saldo_Ajustado" IS 'Sobrescreve o saldo calculado (Debito-Credito) da view';

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_origem"
    ON "Dre_Schema"."Razao_Ajuste_Manual" ("Origem");

CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_data"
    ON "Dre_Schema"."Razao_Ajuste_Manual" ("Data");

CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_conta"
    ON "Dre_Schema"."Razao_Ajuste_Manual" ("Conta");

CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_ativo"
    ON "Dre_Schema"."Razao_Ajuste_Manual" ("Ativo");

CREATE INDEX IF NOT EXISTS "idx_razao_ajuste_nao_operacional"
    ON "Dre_Schema"."Razao_Ajuste_Manual" ("NaoOperacional")
    WHERE "NaoOperacional" = TRUE;


-- ==========================================================================
-- TABELA: Razao_Ajuste_Log
-- Log completo de todas as alterações (pendentes, aprovadas, reprovadas)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Log" (
    "Id" SERIAL PRIMARY KEY,

    -- Referência ao ajuste (preenchido após aprovação)
    "Id_Ajuste" INTEGER REFERENCES "Dre_Schema"."Razao_Ajuste_Manual"("Id"),

    -- Identificação da linha na view (para rastreabilidade)
    "Origem" VARCHAR(50) NOT NULL,
    "Data_Registro" TIMESTAMP NOT NULL,      -- Data do registro na view (não confundir com data da alteração)
    "Numero" VARCHAR(100) NOT NULL,
    "Conta" VARCHAR(100) NOT NULL,
    "Item" VARCHAR(100),

    -- Detalhes da alteração
    "Campo_Alterado" VARCHAR(100) NOT NULL,  -- Nome do campo que foi alterado
    "Valor_Anterior" TEXT,                   -- Valor antes da alteração (serializado)
    "Valor_Novo" TEXT,                       -- Novo valor proposto (serializado)

    -- Auditoria da alteração
    "Usuario_Alteracao" VARCHAR(100) NOT NULL,
    "Data_Alteracao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Status do log
    -- Pendente: aguardando aprovação
    -- Aprovado: aprovado e aplicado ao ajuste
    -- Reprovado: rejeitado pelo aprovador
    -- Cancelado: cancelado pelo próprio solicitante
    "Status" VARCHAR(20) DEFAULT 'Pendente'
        CHECK ("Status" IN ('Pendente', 'Aprovado', 'Reprovado', 'Cancelado')),

    -- Auditoria da aprovação/reprovação
    "Usuario_Aprovacao" VARCHAR(100),
    "Data_Aprovacao" TIMESTAMP,
    "Motivo_Reprovacao" TEXT
);

-- Comentários da tabela
COMMENT ON TABLE "Dre_Schema"."Razao_Ajuste_Log" IS 'Log de todas as alterações solicitadas, com histórico de aprovações/reprovações';
COMMENT ON COLUMN "Dre_Schema"."Razao_Ajuste_Log"."Status" IS 'Pendente=aguardando, Aprovado=aplicado, Reprovado=rejeitado, Cancelado=cancelado pelo solicitante';

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_log_ajuste"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Id_Ajuste");

CREATE INDEX IF NOT EXISTS "idx_razao_log_status"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Status");

CREATE INDEX IF NOT EXISTS "idx_razao_log_usuario"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Usuario_Alteracao");

CREATE INDEX IF NOT EXISTS "idx_razao_log_data"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Data_Alteracao");

CREATE INDEX IF NOT EXISTS "idx_razao_log_pendentes"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Status", "Data_Alteracao")
    WHERE "Status" = 'Pendente';

CREATE INDEX IF NOT EXISTS "idx_razao_log_conta"
    ON "Dre_Schema"."Razao_Ajuste_Log" ("Conta");


-- ==========================================================================
-- TABELA: Razao_Ajuste_Aprovacao
-- Histórico detalhado de decisões de aprovação (auditoria)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS "Dre_Schema"."Razao_Ajuste_Aprovacao" (
    "Id" SERIAL PRIMARY KEY,

    -- Referência ao log de alteração
    "Id_Log" INTEGER NOT NULL REFERENCES "Dre_Schema"."Razao_Ajuste_Log"("Id"),

    -- Decisão tomada
    "Decisao" VARCHAR(20) NOT NULL
        CHECK ("Decisao" IN ('Aprovado', 'Reprovado')),

    -- Auditoria
    "Usuario_Decisao" VARCHAR(100) NOT NULL,
    "Data_Decisao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "Observacao" TEXT,

    -- Contexto de segurança (para auditoria)
    "IP_Origem" VARCHAR(50)
);

-- Comentários da tabela
COMMENT ON TABLE "Dre_Schema"."Razao_Ajuste_Aprovacao" IS 'Histórico de todas as decisões de aprovação/reprovação para auditoria';

-- Índices para performance
CREATE INDEX IF NOT EXISTS "idx_razao_aprov_log"
    ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Id_Log");

CREATE INDEX IF NOT EXISTS "idx_razao_aprov_decisao"
    ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Decisao");

CREATE INDEX IF NOT EXISTS "idx_razao_aprov_usuario"
    ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Usuario_Decisao");

CREATE INDEX IF NOT EXISTS "idx_razao_aprov_data"
    ON "Dre_Schema"."Razao_Ajuste_Aprovacao" ("Data_Decisao");


-- ==========================================================================
-- VIEWS AUXILIARES (Opcional)
-- ==========================================================================

-- View para listar alterações pendentes com informações completas
CREATE OR REPLACE VIEW "Dre_Schema"."Razao_Ajuste_Pendentes" AS
SELECT
    l."Id",
    l."Origem",
    l."Data_Registro",
    l."Numero",
    l."Conta",
    l."Item",
    l."Campo_Alterado",
    l."Valor_Anterior",
    l."Valor_Novo",
    l."Usuario_Alteracao",
    l."Data_Alteracao",
    EXTRACT(DAY FROM (CURRENT_TIMESTAMP - l."Data_Alteracao")) AS "Dias_Pendente"
FROM "Dre_Schema"."Razao_Ajuste_Log" l
WHERE l."Status" = 'Pendente'
ORDER BY l."Data_Alteracao" DESC;

COMMENT ON VIEW "Dre_Schema"."Razao_Ajuste_Pendentes" IS 'Lista alterações pendentes de aprovação com dias de espera';


-- View para estatísticas do módulo
CREATE OR REPLACE VIEW "Dre_Schema"."Razao_Ajuste_Estatisticas" AS
SELECT
    (SELECT COUNT(*) FROM "Dre_Schema"."Razao_Ajuste_Manual" WHERE "Ativo" = TRUE) AS "Total_Ajustes_Ativos",
    (SELECT COUNT(*) FROM "Dre_Schema"."Razao_Ajuste_Log" WHERE "Status" = 'Pendente') AS "Pendentes_Aprovacao",
    (SELECT COUNT(*) FROM "Dre_Schema"."Razao_Ajuste_Log" WHERE "Status" = 'Aprovado' AND "Data_Aprovacao"::DATE = CURRENT_DATE) AS "Aprovados_Hoje",
    (SELECT COUNT(*) FROM "Dre_Schema"."Razao_Ajuste_Log" WHERE "Status" = 'Reprovado' AND DATE_TRUNC('month', "Data_Aprovacao") = DATE_TRUNC('month', CURRENT_DATE)) AS "Reprovados_Mes";

COMMENT ON VIEW "Dre_Schema"."Razao_Ajuste_Estatisticas" IS 'Estatísticas gerais do módulo de ajustes';


-- ==========================================================================
-- PERMISSÕES (Ajuste conforme necessário para seu ambiente)
-- ==========================================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON "Dre_Schema"."Razao_Ajuste_Manual" TO seu_usuario;
-- GRANT SELECT, INSERT, UPDATE ON "Dre_Schema"."Razao_Ajuste_Log" TO seu_usuario;
-- GRANT SELECT, INSERT ON "Dre_Schema"."Razao_Ajuste_Aprovacao" TO seu_usuario;
-- GRANT USAGE, SELECT ON SEQUENCE "Dre_Schema"."Razao_Ajuste_Manual_Id_seq" TO seu_usuario;
-- GRANT USAGE, SELECT ON SEQUENCE "Dre_Schema"."Razao_Ajuste_Log_Id_seq" TO seu_usuario;
-- GRANT USAGE, SELECT ON SEQUENCE "Dre_Schema"."Razao_Ajuste_Aprovacao_Id_seq" TO seu_usuario;


-- ==========================================================================
-- FIM DO SCRIPT
-- ==========================================================================

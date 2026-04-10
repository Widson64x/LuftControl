from sqlalchemy import text
from Utils.Logger import RegistrarLog

class SincronizacaoConsolidadoRazaoService:
    """
    Serviço responsável por orquestrar a sincronização dos dados contábeis brutos
    para a tabela consolidada. Efetua a limpeza de registros órfãos, carga de novos
    lançamentos, aplicação de regras automáticas e estruturação das chaves de indexação.
    """
    def __init__(self, session_db):
        """
        Inicializa o serviço estabelecendo o contexto transacional e mapeando as origens.
        
        Parâmetros:
            session_db (Session): Sessão ativa do SQLAlchemy para conexão com o banco de dados.
        """
        self.session = session_db
        self.schema = "Dre_Schema"
        
        self.tabelas_origem = [
            {"tabela": "Tb_CTL_Razao_Farma", "fonte": "FARMA", "origem_txt": "FARMA"},
            {"tabela": "Tb_CTL_Razao_FarmaDist", "fonte": "FARMADIST", "origem_txt": "FARMADIST"},
            {"tabela": "Tb_CTL_Razao_Intec", "fonte": "INTEC", "origem_txt": "INTEC"}
        ]

    def atualizarChaves(self):
        """
        Recalcula as chaves compostas, mês por extenso e vínculos de cadastros de domínio (Filial e Cliente).
        Opera utilizando CTEs (Common Table Expressions) para garantir performance e atualiza o banco
        exclusivamente quando constata divergências, minimizando custos de I/O.
        
        Retorno:
            None
        """
        query_chaves = text(f"""
            WITH Calc AS (
                SELECT
                    r."Id",
                    r."Fonte",
                    -- 1. Mês Extenso
                    CASE TO_CHAR(r."Data", 'MM')
                        WHEN '01' THEN 'Janeiro' WHEN '02' THEN 'Fevereiro'
                        WHEN '03' THEN 'Março'   WHEN '04' THEN 'Abril'
                        WHEN '05' THEN 'Maio'    WHEN '06' THEN 'Junho'
                        WHEN '07' THEN 'Julho'   WHEN '08' THEN 'Agosto'
                        WHEN '09' THEN 'Setembro' WHEN '10' THEN 'Outubro'
                        WHEN '11' THEN 'Novembro' WHEN '12' THEN 'Dezembro'
                    END AS calc_mes,
                    
                    -- 2. Centro de Custo Mapeado
                    ccc."Tipo" AS calc_cc,
                    ccc."Nome" AS calc_nome_cc,
                    
                    -- 3. Plano de Contas Filial Mapeado
                    cpcf."Denominacao" AS calc_cliente,
                    cpcf."Filial" AS calc_filial_cliente,
                    
                    -- 4. Base Conta formatada (sem pontos)
                    REPLACE(r."Conta", '.', '') AS fmt_conta,

                    -- 5. Cálculo do Saldo (Respeitando a flag Exibir_Saldo)
                    CASE 
                        WHEN r."Exibir_Saldo" = TRUE THEN COALESCE(r."Debito", 0) - COALESCE(r."Credito", 0)
                        ELSE 0 
                    END AS calc_saldo
                    
                FROM "{self.schema}"."Tb_CTL_Razao_Consolidado" r
                LEFT JOIN (
                    SELECT DISTINCT ON ("Codigo") "Codigo", "Tipo", "Nome"
                    FROM "{self.schema}"."Tb_CTL_Cad_Centro_Custo" ORDER BY "Codigo"
                ) ccc ON ccc."Codigo"::text = r."Centro de Custo"::text
                LEFT JOIN (
                    SELECT DISTINCT ON ("Item_Conta") "Item_Conta", "Denominacao", "Filial"
                    FROM "{self.schema}"."Tb_CTL_Cad_Plano_Conta_Filial" ORDER BY "Item_Conta"
                ) cpcf ON cpcf."Item_Conta"::text = r."Item"::text
            )
            UPDATE "{self.schema}"."Tb_CTL_Razao_Consolidado" r
            SET
                "Mes" = c.calc_mes,
                "CC" = c.calc_cc,
                "Nome CC" = c.calc_nome_cc,
                "Cliente" = c.calc_cliente,
                "Filial Cliente" = c.calc_filial_cliente,
                
                "Chv_Mes_Conta" = CONCAT(c.calc_mes, c.fmt_conta),
                "Chv_Mes_Conta_CC" = CONCAT(c.calc_mes, c.fmt_conta, c.calc_cc),
                "Chv_Mes_NomeCC_Conta" = CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta),
                "Chv_Mes_NomeCC_Conta_CC" = CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta, c.calc_cc),
                "Chv_Conta_Formatada" = c.fmt_conta,
                "Chv_Conta_CC" = CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta, r."Centro de Custo"),
                
                -- Atualiza o Saldo
                "Saldo" = c.calc_saldo
                
            FROM Calc c
            WHERE r."Id" = c."Id" AND r."Fonte" = c."Fonte"
              -- Verifica todas as colunas mapeadas, garantindo atualização em caso de alteração no cadastro base
              AND (
                  r."Mes" IS DISTINCT FROM c.calc_mes OR
                  r."CC" IS DISTINCT FROM c.calc_cc OR
                  r."Nome CC" IS DISTINCT FROM c.calc_nome_cc OR
                  r."Cliente" IS DISTINCT FROM c.calc_cliente OR
                  r."Filial Cliente" IS DISTINCT FROM c.calc_filial_cliente OR
                  r."Chv_Mes_Conta" IS DISTINCT FROM CONCAT(c.calc_mes, c.fmt_conta) OR
                  r."Chv_Mes_Conta_CC" IS DISTINCT FROM CONCAT(c.calc_mes, c.fmt_conta, c.calc_cc) OR
                  r."Chv_Mes_NomeCC_Conta" IS DISTINCT FROM CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta) OR
                  r."Chv_Mes_NomeCC_Conta_CC" IS DISTINCT FROM CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta, c.calc_cc) OR
                  r."Chv_Conta_Formatada" IS DISTINCT FROM c.fmt_conta OR
                  r."Chv_Conta_CC" IS DISTINCT FROM CONCAT(c.calc_mes, c.calc_nome_cc, c.fmt_conta, r."Centro de Custo") OR
                  r."Saldo" IS DISTINCT FROM c.calc_saldo
              );
        """)
        self.session.execute(query_chaves)

    def sincronizarDados(self):
        """
        Executa o pipeline completo de sincronização de dados das tabelas subjacentes para a consolidada.
        Processa em lotes e emite commits sequenciais para mitigar bloqueios em nível de tabela (RowExclusiveLock),
        liberando o banco de dados rapidamente para interações concorrentes, como a geração de intergrupos.
        
        Retorno:
            None
        """
        try:
            for config in self.tabelas_origem:
                tabela_origem = config["tabela"]
                fonte = config["fonte"]
                origem_txt = config["origem_txt"]
                
                # 1. REMOVER ÓRFÃOS (Reversão de Importação)
                query_delete = text(f"""
                    DELETE FROM "{self.schema}"."Tb_CTL_Razao_Consolidado"
                    WHERE "Fonte" = :fonte
                    AND "Id" NOT IN (SELECT "Id" FROM "{self.schema}"."{tabela_origem}")
                """)
                self.session.execute(query_delete, {"fonte": fonte})
                self.session.commit() # Libera o lock de exclusão
                
                # 2. INSERIR NOVOS REGISTROS (Processados automaticamente como Aprovados pelo Sistema)
                query_insert = text(f"""
                    INSERT INTO "{self.schema}"."Tb_CTL_Razao_Consolidado" (
                        "Id", "Fonte", "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", 
                        "Contra Partida - Credito", "Filial", "Centro de Custo", "Item", "Cod Cl. Valor", 
                        "Debito", "Credito", "Tipo_Operacao", "Status", "Is_Nao_Operacional", "Exibir_Saldo", 
                        "Invalido", "Criado_Por", "Aprovado_Por", "Data_Aprovacao", "Data_Criacao"
                    )
                    SELECT 
                        orig."Id", :fonte, :origem_txt, orig."Conta", orig."Título Conta", orig."Data", 
                        orig."Numero", orig."Descricao", orig."Contra Partida - Credito", orig."Filial", 
                        orig."Centro de Custo", orig."Item", orig."Cod Cl. Valor", orig."Debito", orig."Credito",
                        'ORIGINAL', 'Aprovado', FALSE, TRUE, FALSE, 'Sistema', 'Sistema', NOW(), NOW()
                    FROM "{self.schema}"."{tabela_origem}" orig
                    LEFT JOIN "{self.schema}"."Tb_CTL_Razao_Consolidado" cons 
                        ON cons."Id" = orig."Id" AND cons."Fonte" = :fonte
                    WHERE cons."Id" IS NULL
                """)
                self.session.execute(query_insert, {"fonte": fonte, "origem_txt": origem_txt})
                self.session.commit() # Libera o lock de inserção
            
            # 3. CORREÇÃO AUTOMÁTICA: Padronização de status preexistentes
            query_limpeza = text(f"""
                UPDATE "{self.schema}"."Tb_CTL_Razao_Consolidado"
                SET "Status" = 'Aprovado',
                    "Aprovado_Por" = 'Sistema',
                    "Criado_Por" = 'Sistema'
                WHERE "Tipo_Operacao" = 'ORIGINAL' AND ("Status" IS NULL OR "Status" = 'Pendente')
            """)
            self.session.execute(query_limpeza)
            self.session.commit() # Libera o lock de atualização estrutural

            # 4. APLICAÇÃO DE REGRA AUTOMÁTICA (Item 10190)
            query_update_10190 = text(f"""
                UPDATE "{self.schema}"."Tb_CTL_Razao_Consolidado"
                SET "Tipo_Operacao" = 'NO-OPER_AUTO',
                    "Status" = 'Aprovado',
                    "Is_Nao_Operacional" = TRUE,
                    "Aprovado_Por" = 'Sistema',
                    "Data_Aprovacao" = NOW()
                WHERE "Item" = '10190' AND "Tipo_Operacao" != 'NO-OPER_AUTO'
            """)
            self.session.execute(query_update_10190)
            self.session.commit() # Libera o lock de regra de negócios
            
            # 5. ATUALIZAR CHAVES
            self.atualizarChaves()
            self.session.commit() # Libera o lock de chaves relacionais
            
        except Exception as e:
            self.session.rollback()
            RegistrarLog("Erro na sincronização de dados consolidados", "ERROR", e)
            raise e
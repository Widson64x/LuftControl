import pandas as pd
import sys
import os
from sqlalchemy import text

# Adiciona o diretório raiz ao path para conseguir importar 'Db.Connections'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Db.Connections import GetPostgresEngine

def processar_relacao_contas():
    # Caminho do arquivo
    file_path = os.path.join('Data', 'RelaçãoDeContasGruposADM.xlsx')
    
    if not os.path.exists(file_path):
        print(f"❌ Erro: Arquivo não encontrado em {file_path}")
        return

    print(f"📂 Lendo arquivo: {file_path}...")
    
    try:
        # Lê todas as abas do Excel. O retorno é um dict: {'NomeAba': DataFrame}
        xls = pd.read_excel(file_path, sheet_name=None)
    except Exception as e:
        print(f"❌ Erro ao abrir Excel: {e}")
        return

    engine = GetPostgresEngine()
    
    # Abre conexão com o banco
    with engine.connect() as conn:
        trans = conn.begin() # Inicia transação
        
        try:
            # 0. Limpa travas antigas (Executa uma vez só)
            print("🛠️ Ajustando constraints do banco...")
            conn.execute(text("""
                ALTER TABLE "Dre_Schema"."Tb_Dre_Conta_Vinculo" 
                DROP CONSTRAINT IF EXISTS "Tb_Dre_Conta_Vinculo_conta_contabil_key";
                
                ALTER TABLE "Dre_Schema"."Tb_Dre_Conta_Vinculo" 
                DROP CONSTRAINT IF EXISTS unique_conta_cc;

                ALTER TABLE "Dre_Schema"."Tb_Dre_Conta_Vinculo" 
                ADD CONSTRAINT unique_conta_cc UNIQUE (key_conta_cod_cc);
            """))

            # Itera sobre cada aba (Cada Aba = Um Subgrupo)
            for nome_subgrupo, df in xls.items():
                print(f"\nProcessing Subgrupo: [ {nome_subgrupo} ]")
                
                # Pega a lista de contas da Coluna A, remove vazios e converte pra string
                lista_contas = df.iloc[:, 0].dropna().astype(str).tolist()
                
                # Limpa espaços em branco das contas (trim)
                lista_contas = [c.strip() for c in lista_contas if c.strip()]
                
                if not lista_contas:
                    print(f"   ⚠️ Aba '{nome_subgrupo}' está vazia ou sem contas válidas. Pulando.")
                    continue

                # Formata a lista para SQL (ex: 'SALARIOS', 'FGTS', ...)
                # Usamos replace para garantir que aspas simples dentro do texto não quebrem a query
                titulos_sql = ", ".join([f"'{t.replace("'", "''")}'" for t in lista_contas])

                # =================================================================
                # PASSO 1: CRIAR O SUBGRUPO PARA TODOS OS CCs 'ADM'
                # =================================================================
                query_criar_grupo = text(f"""
                    INSERT INTO "Dre_Schema"."Tb_Dre_Subgrupos" (
                        nome, 
                        root_cc_codigo, 
                        root_cc_tipo, 
                        root_cc_nome, 
                        parent_subgrupo_id
                    )
                    SELECT DISTINCT 
                        :nome_grupo,                
                        CAST(tcc."Codigo CC." AS INTEGER),
                        tcc."Tipo",               
                        tcc."Nome",               
                        CAST(NULL AS INTEGER)
                    FROM "Dre_Schema"."Tb_Centro_Custo_Classificacao" tcc
                    WHERE tcc."Tipo" = 'Adm'
                    AND NOT EXISTS (
                        SELECT 1 FROM "Dre_Schema"."Tb_Dre_Subgrupos" s 
                        WHERE s.root_cc_codigo = CAST(tcc."Codigo CC." AS INTEGER)
                        AND s.nome = :nome_grupo
                    );
                """)
                
                result_grupo = conn.execute(query_criar_grupo, {"nome_grupo": nome_subgrupo})
                print(f"   ✅ Grupos criados/verificados ({result_grupo.rowcount} linhas afetadas)")

                # =================================================================
                # PASSO 2: VINCULAR AS CONTAS AO GRUPO ESPECÍFICO
                # =================================================================
                # Aqui inserimos a lista de titulos diretamente na query f-string 
                # pois passar lista via bind parameter em text() do sqlalchemy as vezes é chato com IN clause
                
                query_vincular = text(f"""
                    INSERT INTO "Dre_Schema"."Tb_Dre_Conta_Vinculo" (
                        conta_contabil, 
                        subgrupo_id, 
                        key_conta_tipo_cc, 
                        key_conta_cod_cc
                    )
                    SELECT DISTINCT
                        trc."Conta",
                        sg.id AS subgrupo_id, 
                        (trc."Conta" || sg.root_cc_tipo) AS key_conta_tipo_cc,
                        (trc."Conta" || CAST(sg.root_cc_codigo AS TEXT)) AS key_conta_cod_cc

                    FROM "Dre_Schema"."Tb_Razao_CONSOLIDADA" trc
                    JOIN "Dre_Schema"."Tb_Dre_Subgrupos" sg 
                        ON CAST(trc."Centro de Custo" AS INTEGER) = sg.root_cc_codigo 
                        AND sg.nome = :nome_grupo 
                        AND sg.root_cc_tipo = 'Adm'

                    WHERE 
                        trc."CC" = 'Adm' 
                        AND trc."Título Conta" IN ({titulos_sql}) -- Lista Dinâmica vinda do Excel
                    
                    ON CONFLICT (key_conta_cod_cc) DO NOTHING;
                """)

                result_vinculo = conn.execute(query_vincular, {"nome_grupo": nome_subgrupo})
                print(f"   🔗 Contas vinculadas ({result_vinculo.rowcount} novos vínculos)")

            # Se tudo der certo, commita
            trans.commit()
            print("\n✅ SUCESSO TOTAL! Todos os grupos e contas foram processados.")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ ERRO CRÍTICO: Transação revertida.")
            print(e)

if __name__ == "__main__":
    processar_relacao_contas()
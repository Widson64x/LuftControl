import pandas as pd
import os
import sys
from sqlalchemy import text

# Adiciona diretório ao path para importar módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Db.Connections import get_postgres_engine

def corrigir_constraints(conn):
    """
    Ajusta as regras de unicidade do banco de dados para permitir
    que a mesma conta exista em múltiplos grupos (hierarquias),
    mas não duplicada dentro do mesmo grupo.
    """
    print("🛠️  Ajustando constraints (travas) do banco de dados...")
    
    # 1. Remove a trava de unicidade global da conta (se existir)
    sql_drop_global = text("""
        ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" 
        DROP CONSTRAINT IF EXISTS "DRE_Estrutura_Conta_Vinculo_Conta_Contabil_key";
    """)
    conn.execute(sql_drop_global)
    
    # 2. Remove a trava composta antiga se existir
    sql_drop_composite = text("""
        ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" 
        DROP CONSTRAINT IF EXISTS "uq_conta_hierarquia";
    """)
    conn.execute(sql_drop_composite)

    # 3. Cria a NOVA trava correta: (Conta + Grupo) deve ser único.
    sql_create_constraint = text("""
        ALTER TABLE "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" 
        ADD CONSTRAINT "uq_conta_hierarquia" UNIQUE ("Conta_Contabil", "Id_Hierarquia");
    """)
    conn.execute(sql_create_constraint)
    print("✅ Constraints ajustadas com sucesso!\n")


def processar_aba(conn, df, tipo_cc):
    """
    Processa uma aba específica do Excel.
    
    Args:
        conn: Conexão com o banco de dados
        df: DataFrame com os dados da aba
        tipo_cc: Tipo do Centro de Custo ('Adm', 'Oper', 'Coml')
    
    Returns:
        tuple: (grupos_criados, contas_processadas)
    """
    print(f"\n{'='*50}")
    print(f"📋 PROCESSANDO ABA: {tipo_cc}")
    print(f"{'='*50}")
    print(f"   -> Colunas detectadas: {len(df.columns)}")
    print(f"   -> Linhas detectadas: {len(df)}")
    
    grupo_atual = None
    contas_processadas = 0
    grupos_criados = 0
    
    for index, row in df.iterrows():
        # Coluna 9 (index 9): Nomes dos Grupos
        col_desc = str(row[9]) if len(row) > 9 and pd.notna(row[9]) else ""
        
        # --- IDENTIFICAR GRUPO ---
        if "(-)" in col_desc:
            grupo_atual = col_desc.replace("(-)", "").strip()
            print(f"\n📁 Grupo Detectado: {grupo_atual}")
            
            # Cria o grupo para TODOS os CCs do tipo especificado
            sql_grupo = text("""
                INSERT INTO "Dre_Schema"."DRE_Estrutura_Hierarquia" (
                    "Nome", 
                    "Raiz_Centro_Custo_Codigo", 
                    "Raiz_Centro_Custo_Tipo", 
                    "Raiz_Centro_Custo_Nome"
                )
                SELECT DISTINCT 
                    :nome_grupo,                
                    CAST(tcc."Codigo" AS INTEGER),
                    tcc."Tipo",               
                    tcc."Nome"
                FROM "Dre_Schema"."Classificacao_Centro_Custo" tcc
                WHERE tcc."Tipo" = :tipo_cc
                AND NOT EXISTS (
                    SELECT 1 FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" s 
                    WHERE s."Raiz_Centro_Custo_Codigo" = CAST(tcc."Codigo" AS INTEGER)
                    AND s."Nome" = :nome_grupo
                );
            """)
            conn.execute(sql_grupo, {"nome_grupo": grupo_atual, "tipo_cc": tipo_cc})
            grupos_criados += 1
        
        # --- PROCESSAR CONTAS NAS COLUNAS A até I (0 a 8) ---
        if grupo_atual:
            # Itera das colunas 0 a 8
            for i in range(9):
                # Pega valor da célula, verifica se existe e não é nulo
                col_contas = str(row[i]) if len(row) > i and pd.notna(row[i]) else ""
                
                # Validações básicas para saber se é uma conta válida
                if col_contas and col_contas.lower() != 'nan' and 'contas' not in col_contas.lower():
                    
                    # Separa por vírgula caso haja múltiplas contas na mesma célula
                    lista_contas_raw = col_contas.split(',')
                    
                    for conta_suja in lista_contas_raw:
                        # Remove o prefixo do tipo (adm, oper, coml) - case insensitive
                        conta_limpa = conta_suja.lower()
                        conta_limpa = conta_limpa.replace('adm', '').replace('oper', '').replace('coml', '').strip()
                        
                        if not conta_limpa:
                            continue
                            
                        # Insere vínculo com a constraint correta
                        sql_vinculo = text("""
                            INSERT INTO "Dre_Schema"."DRE_Estrutura_Conta_Vinculo" (
                                "Conta_Contabil", 
                                "Id_Hierarquia", 
                                "Chave_Conta_Tipo_CC", 
                                "Chave_Conta_Codigo_CC"
                            )
                            SELECT 
                                CAST(:conta AS VARCHAR),
                                sg."Id", 
                                (CAST(:conta AS VARCHAR) || sg."Raiz_Centro_Custo_Tipo"),
                                (CAST(:conta AS VARCHAR) || CAST(sg."Raiz_Centro_Custo_Codigo" AS TEXT))
                            FROM "Dre_Schema"."DRE_Estrutura_Hierarquia" sg 
                            WHERE sg."Raiz_Centro_Custo_Tipo" = :tipo_cc 
                            AND sg."Nome" = :nome_grupo
                            
                            ON CONFLICT ("Conta_Contabil", "Id_Hierarquia") DO NOTHING;
                        """)
                        
                        conn.execute(sql_vinculo, {"conta": conta_limpa, "nome_grupo": grupo_atual, "tipo_cc": tipo_cc})
                        contas_processadas += 1
    
    print(f"\n✅ Aba {tipo_cc} finalizada:")
    print(f"   📊 Grupos processados: {grupos_criados}")
    print(f"   🔗 Vínculos tentados: {contas_processadas}")
    
    return grupos_criados, contas_processadas


def importar_massivo():
    """
    Função principal que importa dados dos 3 arquivos CSV:
    - AdmGruposContas.csv (Administrativo)
    - OperGruposContas.csv (Operacional)
    - ComlGruposContas.csv (Comercial)
    """
    # Define os arquivos e seus tipos correspondentes
    arquivos = {
        'Adm': os.path.join('Data', 'AdmGruposContas.csv'),
        'Oper': os.path.join('Data', 'OperGruposContas.csv'),
        'Coml': os.path.join('Data', 'ComlGruposContas.csv'),
    }
    
    engine = get_postgres_engine()
    
    total_grupos = 0
    total_contas = 0
    arquivos_processados = []
    
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            # --- PASSO 0: CORRIGIR BANCO ---
            corrigir_constraints(conn)
            
            # --- PASSO 1: PROCESSAR CADA ARQUIVO ---
            for tipo_cc, caminho_csv in arquivos.items():
                
                if not os.path.exists(caminho_csv):
                    print(f"\n⚠️  Arquivo não encontrado: {caminho_csv}. Pulando...")
                    continue
                
                print(f"\n📂 Lendo arquivo: {caminho_csv}...")
                
                try:
                    df = pd.read_csv(caminho_csv, header=None, encoding='latin-1', sep=';')
                    
                    # Processa o arquivo
                    grupos, contas = processar_aba(conn, df, tipo_cc)
                    total_grupos += grupos
                    total_contas += contas
                    arquivos_processados.append(tipo_cc)
                    
                except Exception as e:
                    print(f"\n❌ Erro ao processar arquivo '{caminho_csv}': {e}")
                    continue

            trans.commit()
            
            print("\n" + "="*60)
            print("🎉 IMPORTAÇÃO MASSIVA CONCLUÍDA COM SUCESSO!")
            print("="*60)
            print(f"📊 Total de grupos processados: {total_grupos}")
            print(f"🔗 Total de vínculos tentados: {total_contas}")
            print(f"📋 Arquivos processados: {', '.join(arquivos_processados)}")
            print("="*60)
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ ERRO CRÍTICO DURANTE O PROCESSO: {e}")
            raise


if __name__ == "__main__":
    importar_massivo()
# Reports/Razao.py
from sqlalchemy import text
from Utils.Hash_Utils import gerar_hash
from Utils.Utils import ReportUtils

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

class RazaoReport:
    """
    Classe responsável pelos relatórios detalhados do Razão Contábil.
    Suporta paginação, busca e visualização ajustada (com edições manuais mescladas).
    """
    def __init__(self, session):
        self.session = session

    def _GetAjustesEdicao(self):
        """Busca apenas as edições manuais ativas para substituição rápida."""
        try:
            sql = text("""
                SELECT * FROM "Dre_Schema"."Ajustes_Razao" 
                WHERE "Tipo_Operacao" IN ('EDICAO', 'NO-OPER_AUTO') 
                AND "Status" != 'Reprovado' AND "Invalido" = false
            """)
            rows = self.session.execute(sql).fetchall()
            edicoes = {}
            for row in rows:
                if row.Hash_Linha_Original:
                    edicoes[row.Hash_Linha_Original] = row
            
            if edicoes:
                RegistrarLog(f"Carregadas {len(edicoes)} edições manuais para o Razão.", "DB_QUERY")
            return edicoes
        except Exception as e:
            RegistrarLog("Erro ao buscar ajustes de edição", "ERROR", e)
            return {}

    def GetDados(self, page=1, per_page=50, search_term='', view_type='original'):
        """
        Retorna os lançamentos do Razão com paginação.
        Se view_type='adjusted', faz um UNION ALL com a tabela de ajustes.
        """
        RegistrarLog(f"Consultando Razão (Página {page}). Busca: '{search_term}'. Modo: {view_type}", "REPORT_QUERY")
        
        offset = (page - 1) * per_page
        params = {'limit': per_page, 'offset': offset}
        filter_snippet = ""
        filter_snippet_ajuste = ""
        
        # Filtro de Busca Global
        if search_term:
            filter_snippet = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Título Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"origem\" ILIKE :termo)"
            filter_snippet_ajuste = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Titulo_Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"Origem\" ILIKE :termo)"
            params['termo'] = f"%{search_term}%"

        # Montagem da Query
        if view_type == 'adjusted':
            sql_query = f"""
                SELECT * FROM (
                    -- 1. Dados Originais
                    SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito", CAST("Filial" AS TEXT) as "Filial", CAST("Centro de Custo" AS TEXT) as "Centro de Custo", "Item", COALESCE("Debito", 0) as "Debito", COALESCE("Credito", 0) as "Credito", "Saldo", "Nome do CC", NULL as "Hash_Ajuste_ID"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                    
                    UNION ALL
                    
                    -- 2. Inclusões Manuais (Novas Linhas)
                    SELECT 'AJUSTE' as source_type, "Origem", "Conta", "Titulo_Conta", "Data", "Numero", "Descricao", "Contra_Partida", "Filial", "Centro_Custo", "Item", CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END, NULL, CAST("Id" AS TEXT)
                    FROM "Dre_Schema"."Ajustes_Razao" WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') AND "Status" != 'Reprovado' AND "Invalido" = false {filter_snippet_ajuste}
                ) AS uniao_dados ORDER BY "Data" DESC, "Conta" ASC, "Numero" ASC LIMIT :limit OFFSET :offset
            """
            sql_count = f"""SELECT SUM(cnt) FROM (SELECT COUNT(*) as cnt FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet} UNION ALL SELECT COUNT(*) as cnt FROM "Dre_Schema"."Ajustes_Razao" WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') AND "Status" != 'Reprovado' AND "Invalido" = false {filter_snippet_ajuste}) as total_tbl"""
        else:
            sql_query = f"""SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito", "Filial", "Centro de Custo", "Item", "Debito", "Credito", "Saldo", "Nome do CC", NULL as "Hash_Ajuste_ID" FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet} ORDER BY "Data" DESC, "Conta" ASC, "Numero" ASC LIMIT :limit OFFSET :offset"""
            sql_count = f'SELECT COUNT(*) FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}'

        try:
            # Execução
            total_registros = self.session.execute(text(sql_count), params).scalar() or 0
            total_paginas = (total_registros // per_page) + (1 if total_registros % per_page > 0 else 0)
            rows = self.session.execute(text(sql_query), params).fetchall()
            
            result_list = []
            ajustes_edicao = {}
            
            # Se for visão ajustada, carrega as edições para aplicar "em tempo real"
            if view_type == 'adjusted': 
                ajustes_edicao = self._GetAjustesEdicao()

            for i, r in enumerate(rows, 1):
                row_dict = {
                    'id': i + offset, 'origem': r.origem, 'conta': r.Conta, 'titulo_conta': getattr(r, 'Título Conta', ''), 
                    'data': r.Data.isoformat() if r.Data else None, 'numero': r.Numero, 'descricao': r.Descricao, 
                    'centro_custo': getattr(r, 'Centro de Custo', ''), 'filial': getattr(r, 'Filial', ''), 'item': getattr(r, 'Item', ''),
                    'debito': float(r.Debito or 0), 'credito': float(r.Credito or 0), 'saldo': float(r.Saldo or 0), 'is_ajustado': False
                }
                
                # Caso 1: É uma inclusão manual
                if hasattr(r, 'source_type') and r.source_type == 'AJUSTE':
                    row_dict['is_ajustado'] = True
                    row_dict['origem'] = f"{r.origem} (NOVO)"
                    row_dict['Hash_ID'] = f"NEW_{r.Hash_Ajuste_ID}" 

                # Caso 2: É original mas tem edição
                elif view_type == 'adjusted':
                    r_hash = gerar_hash(r)
                    if r_hash in ajustes_edicao:
                        adj = ajustes_edicao[r_hash]
                        if not adj.Invalido:
                            if adj.Exibir_Saldo: 
                                row_dict['saldo'] = float(adj.Debito or 0) - float(adj.Credito or 0)
                                row_dict['debito'] = float(adj.Debito or 0)
                                row_dict['credito'] = float(adj.Credito or 0)
                            else: 
                                row_dict['saldo'] = 0.0; row_dict['debito'] = 0.0; row_dict['credito'] = 0.0
                            
                            row_dict['is_ajustado'] = True
                            row_dict['origem'] = f"{r.origem} (EDIT)"
                            # Sobrescreve campos visuais
                            if adj.Descricao: row_dict['descricao'] = adj.Descricao
                            if adj.Conta: row_dict['conta'] = adj.Conta
                            if adj.Titulo_Conta: row_dict['titulo_conta'] = adj.Titulo_Conta
                            if adj.Centro_Custo: row_dict['centro_custo'] = adj.Centro_Custo
                            if adj.Filial: row_dict['filial'] = adj.Filial

                result_list.append(row_dict)
                
            return {'pagina_atual': page, 'total_paginas': total_paginas, 'total_registros': total_registros, 'dados': result_list}

        except Exception as e:
            RegistrarLog("Erro Crítico ao buscar dados do Razão", "ERROR", e)
            raise e

    def GetResumo(self, view_type='original'):
        """Retorna os totais (somatórios) para exibição no rodapé."""
        try:
            if view_type == 'adjusted':
                sql = text("""
                    SELECT SUM(cnt), SUM(deb), SUM(cred), SUM(sal) FROM (
                        SELECT COUNT(*) as cnt, SUM("Debito") as deb, SUM("Credito") as cred, SUM("Saldo") as sal 
                        FROM "Dre_Schema"."Razao_Dados_Consolidado"
                        UNION ALL
                        SELECT COUNT(*) as cnt, SUM("Debito") as deb, SUM("Credito") as cred, SUM("Debito" - "Credito") as sal
                        FROM "Dre_Schema"."Ajustes_Razao" WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') AND "Status" != 'Reprovado' AND "Invalido" = false
                    ) as tbl_union
                """)
            else:
                sql = text("SELECT COUNT(*), SUM(\"Debito\"), SUM(\"Credito\"), SUM(\"Saldo\") FROM \"Dre_Schema\".\"Razao_Dados_Consolidado\"")
            base = self.session.execute(sql).fetchone()
            return {
                'total_registros': base[0] or 0, 'total_debito': float(base[1] or 0), 
                'total_credito': float(base[2] or 0), 'saldo_total': float(base[3] or 0)
            }
        except Exception as e:
            RegistrarLog("Erro ao calcular resumo do rodapé", "ERROR", e)
            return {'total_registros': 0, 'total_debito': 0, 'total_credito': 0, 'saldo_total': 0}

    def ExportFull(self, search_term='', view_type='original'):
        """Gera o dataset completo para exportação Excel (sem paginação)."""
        RegistrarLog(f"Iniciando exportação COMPLETA do Razão. Termo: '{search_term}'", "EXPORT")
        
        params = {}
        filter_snippet = ""; filter_snippet_ajuste = ""
        
        if search_term:
            params['termo'] = f"%{search_term}%"
            filter_snippet = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Título Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"origem\" ILIKE :termo)"
            filter_snippet_ajuste = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Titulo_Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"Origem\" ILIKE :termo)"

        try:
            if view_type == 'adjusted':
                sql = text(f"""
                    SELECT * FROM (
                        SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito" as "Contra Partida", CAST("Filial" AS TEXT) as "Filial", CAST("Centro de Custo" AS TEXT) as "Centro de Custo", "Item", "Cod Cl. Valor", "Debito", "Credito", "Saldo"
                        FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                        UNION ALL
                        SELECT 'AJUSTE', "Origem", "Conta", "Titulo_Conta", "Data", "Numero", "Descricao", "Contra_Partida", "Filial", "Centro_Custo", "Item", "Cod_Cl_Valor", CASE WHEN "Exibir_Saldo" THEN COALESCE("Debito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN COALESCE("Credito", 0) ELSE 0 END, CASE WHEN "Exibir_Saldo" THEN (COALESCE("Debito", 0) - COALESCE("Credito", 0)) ELSE 0 END
                        FROM "Dre_Schema"."Ajustes_Razao" WHERE "Tipo_Operacao" IN ('INCLUSAO', 'INTERGRUPO_AUTO') AND "Status" != 'Reprovado' AND "Invalido" = false {filter_snippet_ajuste}
                    ) as tbl_final ORDER BY "Data", "Conta"
                """)
            else:
                sql = text(f"""
                    SELECT 'RAZAO' as source_type, "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito" as "Contra Partida", "Filial", "Centro de Custo", "Item", "Cod Cl. Valor", "Debito", "Credito", "Saldo"
                    FROM "Dre_Schema"."Razao_Dados_Consolidado" WHERE 1=1 {filter_snippet}
                    ORDER BY "Data", "Conta"
                """)
                
            rows = self.session.execute(sql, params).fetchall()
            ajustes_edicao = {}
            if view_type == 'adjusted':
                ajustes_edicao = self._GetAjustesEdicao()

            final_data = []

            for r in rows:
                row_dict = dict(r._mapping)
                if row_dict.get('source_type') == 'AJUSTE':
                    row_dict['origem'] = f"{row_dict['origem']} (NOVO)"
                    del row_dict['source_type']
                    final_data.append(row_dict)
                    continue
                
                del row_dict['source_type']
                if view_type == 'adjusted':
                    r_hash = gerar_hash(r)
                    if r_hash in ajustes_edicao:
                        adj = ajustes_edicao[r_hash]
                        if not adj.Invalido:
                            row_dict['origem'] = f"{row_dict['origem']} (AJUSTE)"
                            if adj.Conta: row_dict['Conta'] = adj.Conta
                            if adj.Titulo_Conta: row_dict['Título Conta'] = adj.Titulo_Conta
                            if adj.Descricao: row_dict['Descricao'] = adj.Descricao
                            if adj.Centro_Custo: row_dict['Centro de Custo'] = adj.Centro_Custo
                            d = float(adj.Debito or 0); c = float(adj.Credito or 0)
                            if adj.Exibir_Saldo:
                                row_dict['Debito'] = d; row_dict['Credito'] = c; row_dict['Saldo'] = d - c
                            else:
                                row_dict['Debito'] = 0; row_dict['Credito'] = 0; row_dict['Saldo'] = 0

                final_data.append(row_dict)
            
            RegistrarLog(f"Exportação gerou {len(final_data)} linhas.", "EXPORT")
            return final_data
        
        except Exception as e:
            RegistrarLog("Erro durante geração de exportação", "ERROR", e)
            raise e
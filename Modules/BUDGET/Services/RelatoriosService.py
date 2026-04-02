"""
Módulo responsável pelos serviços de relatórios referentes ao Budget (Orçamento).
"""

class RelatoriosService:
    """
    Classe que encapsula a lógica de negócio e geração de dados para os relatórios do módulo de Budget.
    """

    def gerarRelatorioFalso(self, ano):
        """
        Gera dados em memória simulando um relatório de Budget para fins de teste de interface.

        Parâmetros:
            ano (int): O ano de referência para filtragem do orçamento.

        Retorno:
            list: Lista de dicionários, onde cada dicionário representa o consolidado de um Centro de Custo,
                  contendo as chaves 'Centro_Custo', 'Orcado', 'Realizado' e 'Desvio'.
        """
        # Simulando uma consulta no banco de dados com base no ano
        fator_ano = 1 if int(ano) == 2026 else 0.85
        
        dados_simulados = [
            {
                "Centro_Custo": "Tecnologia da Informação", 
                "Orcado": 150000 * fator_ano, 
                "Realizado": 145000 * fator_ano, 
                "Desvio": 5000 * fator_ano
            },
            {
                "Centro_Custo": "Recursos Humanos", 
                "Orcado": 80000 * fator_ano, 
                "Realizado": 85000 * fator_ano, 
                "Desvio": -5000 * fator_ano
            },
            {
                "Centro_Custo": "Comercial", 
                "Orcado": 200000 * fator_ano, 
                "Realizado": 190000 * fator_ano, 
                "Desvio": 10000 * fator_ano
            },
            {
                "Centro_Custo": "Operações Logísticas", 
                "Orcado": 500000 * fator_ano, 
                "Realizado": 520000 * fator_ano, 
                "Desvio": -20000 * fator_ano
            }
        ]
        
        return dados_simulados
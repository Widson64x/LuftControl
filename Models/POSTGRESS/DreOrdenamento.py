# Models/POSTGRESS/DreOrdenamento.py
"""
Sistema de Ordenamento Hierárquico da DRE
Permite controle total sobre a posição de cada elemento na árvore.

ESTRUTURA DE NÍVEIS:
- Nível 0 (Raiz): Tipos de CC (Adm, Oper, Coml) e Nós Virtuais
- Nível 1: Centros de Custo (dentro de cada Tipo)
- Nível 2+: Subgrupos (podem ter profundidade infinita: 2.1, 2.2, 2.2.1, etc.)
- Nível N (Folha): Contas Contábeis

TIPOS DE NÓ:
- 'tipo_cc': Pasta de Tipo (Adm, Operacional, Comercial)
- 'virtual': Nó Virtual (Faturamento, Impostos, etc.)
- 'cc': Centro de Custo específico
- 'subgrupo': Grupo/Subgrupo hierárquico
- 'conta': Conta contábil (folha)
"""
from sqlalchemy import Column, Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class DreOrdenamento(Base):
    """
    Tabela centralizada de ordenamento.
    
    Cada registro representa a posição de UM elemento na hierarquia.
    A chave composta (tipo_no, id_referencia, contexto_pai) garante unicidade.
    
    Exemplos de registros:
    - tipo_no='tipo_cc', id_referencia='Adm', contexto_pai='root', ordem=10
    - tipo_no='virtual', id_referencia='1', contexto_pai='root', ordem=5  (aparece antes de Adm)
    - tipo_no='cc', id_referencia='25110501', contexto_pai='tipo_Adm', ordem=10
    - tipo_no='subgrupo', id_referencia='15', contexto_pai='cc_25110501', ordem=20
    - tipo_no='conta', id_referencia='6030101', contexto_pai='sg_15', ordem=100
    """
    __tablename__ = 'DRE_Ordenamento'
    __table_args__ = (
        # Garante que não há duplicatas de posição no mesmo contexto
        UniqueConstraint('contexto_pai', 'ordem', name='uq_ordem_contexto'),
        # Garante unicidade do nó
        UniqueConstraint('tipo_no', 'id_referencia', 'contexto_pai', name='uq_no_unico'),
        # Índice para buscas rápidas
        Index('idx_contexto_ordem', 'contexto_pai', 'ordem'),
        {'schema': 'Dre_Schema'}
    )

    Id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identificação do Nó
    tipo_no = Column(String(50), nullable=False)
    """
    Tipo do elemento:
    - 'tipo_cc': Pasta de tipo (Adm, Oper, Coml)
    - 'virtual': Nó virtual da DRE
    - 'cc': Centro de Custo
    - 'subgrupo': Grupo/Subgrupo
    - 'conta': Conta contábil
    - 'conta_detalhe': Conta com nome personalizado
    """
    
    id_referencia = Column(String(100), nullable=False)
    """
    ID ou código do elemento referenciado:
    - Para tipo_cc: Nome do tipo ('Adm', 'Oper', 'Coml')
    - Para virtual: ID do DreNoVirtual (string)
    - Para cc: Código do Centro de Custo (string)
    - Para subgrupo: ID do DreHierarquia (string)
    - Para conta: Número da conta contábil
    - Para conta_detalhe: ID do DreContaPersonalizada (string)
    """
    
    # Contexto Hierárquico
    contexto_pai = Column(String(100), nullable=False, default='root')
    """
    Identificador do pai na hierarquia:
    - 'root': Elementos de nível 0 (tipos e virtuais)
    - 'tipo_Adm': CCs dentro do tipo Adm
    - 'cc_25110501': Subgrupos dentro do CC 25110501
    - 'sg_15': Subgrupos/Contas dentro do subgrupo 15
    - 'virt_1': Subgrupos/Contas dentro do nó virtual 1
    """
    
    # Ordem
    ordem = Column(Integer, nullable=False, default=0)
    """
    Posição numérica do elemento.
    Recomenda-se usar intervalos de 10 (10, 20, 30...) para facilitar inserções.
    """
    
    # Metadados
    nivel_profundidade = Column(Integer, default=0)
    """
    Profundidade na árvore (para consultas otimizadas):
    - 0: Raiz (tipos e virtuais)
    - 1: CCs
    - 2: Subgrupos de primeiro nível
    - 3+: Subgrupos aninhados
    """
    
    caminho_completo = Column(String(500), nullable=True)
    """
    Path materializado para queries hierárquicas.
    Ex: 'root/tipo_Adm/cc_25110501/sg_15/sg_22'
    """
    
    # Auditoria
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<DreOrdenamento({self.tipo_no}:{self.id_referencia} @{self.contexto_pai} pos={self.ordem})>"


class DreOrdenamentoConfig(Base):
    """
    Configurações globais do sistema de ordenamento.
    Permite definir padrões e comportamentos.
    """
    __tablename__ = 'DRE_Ordenamento_Config'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    chave = Column(String(100), unique=True, nullable=False)
    valor = Column(String(500))
    descricao = Column(String(500))
    
    """
    Configurações disponíveis:
    - 'intervalo_padrao': Intervalo entre ordens (default: 10)
    - 'auto_reordenar': Se deve reordenar automaticamente em conflitos (default: 'true')
    - 'ordem_padrao_tipos': Ordem padrão dos tipos ('Oper,Adm,Coml' ou 'Adm,Oper,Coml')
    """

    def __repr__(self):
        return f"<DreOrdenamentoConfig({self.chave}={self.valor})>"


# ============================================================
# FUNÇÕES AUXILIARES (Para uso nas rotas)
# ============================================================

def gerar_contexto_pai(tipo_no_pai: str, id_pai: str) -> str:
    """
    Gera o contexto_pai baseado no tipo e id do nó pai.
    
    Args:
        tipo_no_pai: 'root', 'tipo_cc', 'virtual', 'cc', 'subgrupo'
        id_pai: ID ou código do pai
    
    Returns:
        String do contexto (ex: 'cc_25110501', 'sg_15', 'virt_1')
    """
    if tipo_no_pai == 'root' or not id_pai:
        return 'root'
    
    prefixos = {
        'tipo_cc': 'tipo_',
        'virtual': 'virt_',
        'cc': 'cc_',
        'subgrupo': 'sg_',
    }
    
    prefixo = prefixos.get(tipo_no_pai, '')
    return f"{prefixo}{id_pai}"


def calcular_proxima_ordem(session, contexto_pai: str, intervalo: int = 10) -> int:
    """
    Calcula a próxima ordem disponível em um contexto.
    
    Args:
        session: Sessão SQLAlchemy
        contexto_pai: Contexto onde inserir
        intervalo: Intervalo entre ordens
    
    Returns:
        Próximo número de ordem disponível
    """
    from sqlalchemy import func as sqlfunc
    
    max_ordem = session.query(sqlfunc.max(DreOrdenamento.ordem)).filter(
        DreOrdenamento.contexto_pai == contexto_pai
    ).scalar()
    
    if max_ordem is None:
        return intervalo
    
    return max_ordem + intervalo


def reordenar_contexto(session, contexto_pai: str, intervalo: int = 10):
    """
    Reordena todos os elementos de um contexto com intervalos uniformes.
    Útil após muitas inserções/remoções.
    
    Args:
        session: Sessão SQLAlchemy
        contexto_pai: Contexto a reordenar
        intervalo: Novo intervalo entre ordens
    """
    elementos = session.query(DreOrdenamento).filter(
        DreOrdenamento.contexto_pai == contexto_pai
    ).order_by(DreOrdenamento.ordem).all()
    
    for i, elem in enumerate(elementos, start=1):
        elem.ordem = i * intervalo
    
    session.flush()


def mover_elemento(session, tipo_no: str, id_ref: str, 
                   contexto_origem: str, contexto_destino: str,
                   nova_ordem: int = None):
    """
    Move um elemento de um contexto para outro (ou reposiciona no mesmo).
    
    Args:
        session: Sessão SQLAlchemy
        tipo_no: Tipo do nó a mover
        id_ref: ID/código do nó
        contexto_origem: Contexto atual
        contexto_destino: Novo contexto
        nova_ordem: Nova posição (None = final)
    """
    # Busca o registro atual
    registro = session.query(DreOrdenamento).filter(
        DreOrdenamento.tipo_no == tipo_no,
        DreOrdenamento.id_referencia == id_ref,
        DreOrdenamento.contexto_pai == contexto_origem
    ).first()
    
    if not registro:
        # Cria novo se não existir
        registro = DreOrdenamento(
            tipo_no=tipo_no,
            id_referencia=id_ref
        )
        session.add(registro)
    
    # Atualiza contexto
    registro.contexto_pai = contexto_destino
    
    # Define ordem
    if nova_ordem is None:
        registro.ordem = calcular_proxima_ordem(session, contexto_destino)
    else:
        registro.ordem = nova_ordem
        # Empurra elementos que estão na mesma posição ou depois
        session.query(DreOrdenamento).filter(
            DreOrdenamento.contexto_pai == contexto_destino,
            DreOrdenamento.ordem >= nova_ordem,
            DreOrdenamento.Id != registro.Id
        ).update({DreOrdenamento.ordem: DreOrdenamento.ordem + 10})
    
    session.flush()
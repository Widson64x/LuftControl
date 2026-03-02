# Models/POSTGRESS/CTL_Dre_Ordenamento.py
from sqlalchemy import Column, Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class CtlDreOrdenamento(Base):
    __tablename__ = 'Tb_CTL_Dre_Ordenamento'
    __table_args__ = (
        UniqueConstraint('contexto_pai', 'ordem', name='uq_ordem_contexto'),
        UniqueConstraint('tipo_no', 'id_referencia', 'contexto_pai', name='uq_no_unico'),
        Index('idx_contexto_ordem', 'contexto_pai', 'ordem'),
        {'schema': 'Dre_Schema'}
    )

    Id = Column(Integer, primary_key=True, autoincrement=True)
    tipo_no = Column(String(50), nullable=False)
    id_referencia = Column(String(100), nullable=False)
    contexto_pai = Column(String(100), nullable=False, default='root')
    ordem = Column(Integer, nullable=False, default=0)
    nivel_profundidade = Column(Integer, default=0)
    caminho_completo = Column(String(500), nullable=True)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, onupdate=func.now())

class CtlDreConfigOrdenamento(Base):
    __tablename__ = 'Tb_CTL_Dre_Config_Ordenamento'
    __table_args__ = {'schema': 'Dre_Schema'}

    Id = Column(Integer, primary_key=True)
    chave = Column(String(100), unique=True, nullable=False)
    valor = Column(String(500))
    descricao = Column(String(500))

# Funções auxiliares mantidas intactas, apenas referenciando a nova classe CtlDreOrdenamento
def gerar_contexto_pai(tipo_no_pai: str, id_pai: str) -> str:
    if tipo_no_pai == 'root' or not id_pai:
        return 'root'
    prefixos = {'tipo_cc': 'tipo_', 'virtual': 'virt_', 'cc': 'cc_', 'subgrupo': 'sg_'}
    prefixo = prefixos.get(tipo_no_pai, '')
    return f"{prefixo}{id_pai}"

def calcular_proxima_ordem(session, contexto_pai: str, intervalo: int = 10) -> int:
    from sqlalchemy import func as sqlfunc
    max_ordem = session.query(sqlfunc.max(CtlDreOrdenamento.ordem)).filter(
        CtlDreOrdenamento.contexto_pai == contexto_pai
    ).scalar()
    return intervalo if max_ordem is None else max_ordem + intervalo

def reordenar_contexto(session, contexto_pai: str, intervalo: int = 10):
    elementos = session.query(CtlDreOrdenamento).filter(
        CtlDreOrdenamento.contexto_pai == contexto_pai
    ).order_by(CtlDreOrdenamento.ordem).all()
    for i, elem in enumerate(elementos, start=1):
        elem.ordem = i * intervalo
    session.flush()

def mover_elemento(session, tipo_no: str, id_ref: str, contexto_origem: str, contexto_destino: str, nova_ordem: int = None):
    registro = session.query(CtlDreOrdenamento).filter(
        CtlDreOrdenamento.tipo_no == tipo_no,
        CtlDreOrdenamento.id_referencia == id_ref,
        CtlDreOrdenamento.contexto_pai == contexto_origem
    ).first()
    if not registro:
        registro = CtlDreOrdenamento(tipo_no=tipo_no, id_referencia=id_ref)
        session.add(registro)
    
    registro.contexto_pai = contexto_destino
    if nova_ordem is None:
        registro.ordem = calcular_proxima_ordem(session, contexto_destino)
    else:
        registro.ordem = nova_ordem
        session.query(CtlDreOrdenamento).filter(
            CtlDreOrdenamento.contexto_pai == contexto_destino,
            CtlDreOrdenamento.ordem >= nova_ordem,
            CtlDreOrdenamento.Id != registro.Id
        ).update({CtlDreOrdenamento.ordem: CtlDreOrdenamento.ordem + 10})
    session.flush()
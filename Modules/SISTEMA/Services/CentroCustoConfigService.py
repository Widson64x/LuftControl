import json
import os
from datetime import datetime
from decimal import Decimal

from Db.Connections import GetSqlServerSession
from Models.SqlServer.ContaPagar import CentroCusto
from Models.SqlServer.Usuario import Usuario
from Utils.Logger import RegistrarLog


class CentroCustoConfigService:
    PASTA_CONFIGURACAO = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../..', 'Data', 'Config')
    )
    ARQUIVO_CONFIGURACAO = os.path.join(PASTA_CONFIGURACAO, 'centro_custo_config.json')
    ARQUIVO_CONFIGURACAO_LEGADO = os.path.join(PASTA_CONFIGURACAO, 'gestores_centro_custo.json')

    _cache = {'mtime': None, 'data': None}

    def __init__(self):
        self._garantir_arquivo_configuracao()

    @classmethod
    def listarCodigosCentrosOff(cls):
        dados = cls._carregar_configuracao_cache()
        return [centro['codigo'] for centro in dados.get('centros_custo_off', [])]

    def listarUsuariosDisponiveis(self):
        sessao = GetSqlServerSession(ignore_centro_custo_off=True)
        try:
            registros = (
                sessao.query(
                    Usuario.Codigo_Usuario,
                    Usuario.Nome_Usuario,
                    Usuario.Login_Usuario,
                )
                .order_by(Usuario.Nome_Usuario)
                .all()
            )

            usuarios = []
            usuarios_vistos = set()
            for registro in registros:
                codigo_usuario = self._normalizar_codigo_usuario(registro.Codigo_Usuario)
                if codigo_usuario is None or codigo_usuario in usuarios_vistos:
                    continue

                usuarios_vistos.add(codigo_usuario)
                usuarios.append(
                    {
                        'codigo_usuario': codigo_usuario,
                        'nome_usuario': self._normalizar_texto(registro.Nome_Usuario) or f'Usuário {codigo_usuario}',
                        'login_usuario': self._normalizar_texto(registro.Login_Usuario) or '',
                    }
                )

            return usuarios
        finally:
            sessao.close()

    def listarCentrosCustoDisponiveis(self):
        sessao = GetSqlServerSession(ignore_centro_custo_off=True)
        try:
            registros = (
                sessao.query(
                    CentroCusto.Codigo_CentroCusto,
                    CentroCusto.Numero_CentroCusto,
                    CentroCusto.Nome_CentroCusto,
                    CentroCusto.Data_Obsoleto,
                )
                .filter(CentroCusto.Data_Obsoleto.is_(None))
                .order_by(CentroCusto.Nome_CentroCusto)
                .all()
            )

            centros = []
            centros_vistos = set()
            for registro in registros:
                codigo_centro = self._serializar_codigo(registro.Codigo_CentroCusto)
                if not codigo_centro or codigo_centro in centros_vistos:
                    continue

                centros_vistos.add(codigo_centro)
                numero_centro = self._normalizar_texto(registro.Numero_CentroCusto) or codigo_centro
                nome_centro = self._normalizar_texto(registro.Nome_CentroCusto) or 'Sem nome'
                centros.append(
                    {
                        'codigo': codigo_centro,
                        'numero': numero_centro,
                        'nome': nome_centro,
                        'rotulo': f'{numero_centro} - {nome_centro}',
                    }
                )

            return centros
        finally:
            sessao.close()

    def carregarConfiguracao(self, force_refresh=False):
        return self._carregar_configuracao_cache(force_refresh)

    def salvarConfiguracao(self, payload, usuario_editor=None):
        gestores_recebidos = payload.get('gestores', []) if isinstance(payload, dict) else []
        centros_off_recebidos = payload.get('centros_custo_off', []) if isinstance(payload, dict) else []

        if not isinstance(gestores_recebidos, list) or not isinstance(centros_off_recebidos, list):
            raise ValueError('A configuração enviada é inválida.')

        usuarios_disponiveis = {
            usuario['codigo_usuario']: usuario
            for usuario in self.listarUsuariosDisponiveis()
        }
        centros_disponiveis = {
            centro['codigo']: centro
            for centro in self.listarCentrosCustoDisponiveis()
        }

        centros_off = self._normalizar_centros_off(centros_off_recebidos, centros_disponiveis)
        codigos_off = {centro['codigo'] for centro in centros_off}

        gestores_normalizados = []
        usuarios_vistos = set()

        for gestor in gestores_recebidos:
            if not isinstance(gestor, dict):
                continue

            codigo_usuario = self._normalizar_codigo_usuario(gestor.get('codigo_usuario'))
            if codigo_usuario is None:
                continue

            if codigo_usuario not in usuarios_disponiveis:
                raise ValueError(f'Usuário inválido na configuração: {codigo_usuario}.')

            if codigo_usuario in usuarios_vistos:
                raise ValueError(f'O usuário {codigo_usuario} foi informado mais de uma vez na configuração.')

            codigos_centros = gestor.get('centros_custo', [])
            if not isinstance(codigos_centros, list):
                raise ValueError(f'Os centros de custo do usuário {codigo_usuario} estão inválidos.')

            centros_gestor = []
            centros_vistos = set()
            for codigo_centro in codigos_centros:
                codigo_normalizado = self._serializar_codigo(codigo_centro)
                if (
                    not codigo_normalizado
                    or codigo_normalizado in centros_vistos
                    or codigo_normalizado in codigos_off
                ):
                    continue

                centro = centros_disponiveis.get(codigo_normalizado)
                if centro is None:
                    raise ValueError(
                        f'Centro de custo inválido para o usuário {codigo_usuario}: {codigo_normalizado}.'
                    )

                centros_vistos.add(codigo_normalizado)
                centros_gestor.append(self._montar_payload_centro(centro))

            if not centros_gestor:
                continue

            usuario = usuarios_disponiveis[codigo_usuario]
            gestores_normalizados.append(
                {
                    'codigo_usuario': codigo_usuario,
                    'nome_usuario': usuario['nome_usuario'],
                    'login_usuario': usuario['login_usuario'],
                    'cargo': self._normalizar_texto(gestor.get('cargo')) or 'Gestor',
                    'centros_custo': self._ordenar_centros(centros_gestor),
                }
            )
            usuarios_vistos.add(codigo_usuario)

        gestores_normalizados.sort(key=lambda item: item['nome_usuario'])

        configuracao_final = {
            'version': 2,
            'atualizado_em': datetime.now().isoformat(timespec='seconds'),
            'atualizado_por': self._montar_identificacao_usuario(usuario_editor),
            'centros_custo_off': self._ordenar_centros(centros_off),
            'gestores': gestores_normalizados,
        }

        self._gravar_configuracao(configuracao_final)

        usuario_log = configuracao_final['atualizado_por'].get('nome') or 'Sistema'
        RegistrarLog(
            (
                'Configuração global de centros de custo atualizada por '
                f'{usuario_log}. Gestores: {len(gestores_normalizados)}. '
                f'Centros OFF: {len(configuracao_final["centros_custo_off"])}.'
            ),
            'System',
        )

        return configuracao_final

    def obterCentrosCustoDoGestor(self, codigo_usuario):
        gestor = self.obterGestorConfigurado(codigo_usuario)
        if not gestor:
            return []
        return [centro['codigo'] for centro in gestor.get('centros_custo', [])]

    def obterGestorConfigurado(self, codigo_usuario):
        codigo_usuario_normalizado = self._normalizar_codigo_usuario(codigo_usuario)
        if codigo_usuario_normalizado is None:
            return None

        configuracao = self.carregarConfiguracao()
        codigos_off = {centro['codigo'] for centro in configuracao.get('centros_custo_off', [])}

        for gestor in configuracao.get('gestores', []):
            if gestor.get('codigo_usuario') != codigo_usuario_normalizado:
                continue

            centros = [
                centro
                for centro in gestor.get('centros_custo', [])
                if centro.get('codigo') not in codigos_off
            ]
            if not centros:
                return None

            return {
                **gestor,
                'centros_custo': self._ordenar_centros(centros),
            }

        return None

    @classmethod
    def _carregar_configuracao_cache(cls, force_refresh=False):
        cls._garantir_arquivo_configuracao()
        try:
            mtime = os.path.getmtime(cls.ARQUIVO_CONFIGURACAO)
        except OSError:
            cls._gravar_configuracao(cls._configuracao_vazia())
            mtime = os.path.getmtime(cls.ARQUIVO_CONFIGURACAO)

        if not force_refresh and cls._cache['mtime'] == mtime and cls._cache['data'] is not None:
            return json.loads(json.dumps(cls._cache['data']))

        dados = cls._ler_arquivo_json(cls.ARQUIVO_CONFIGURACAO)
        configuracao = cls._normalizar_configuracao(dados)
        cls._cache = {'mtime': mtime, 'data': configuracao}
        return json.loads(json.dumps(configuracao))

    @classmethod
    def _garantir_arquivo_configuracao(cls):
        os.makedirs(cls.PASTA_CONFIGURACAO, exist_ok=True)
        if os.path.exists(cls.ARQUIVO_CONFIGURACAO):
            return

        dados_iniciais = cls._configuracao_vazia()
        if os.path.exists(cls.ARQUIVO_CONFIGURACAO_LEGADO):
            dados_iniciais = cls._normalizar_configuracao(cls._ler_arquivo_json(cls.ARQUIVO_CONFIGURACAO_LEGADO))

        cls._gravar_configuracao(dados_iniciais)

    @classmethod
    def _gravar_configuracao(cls, dados):
        with open(cls.ARQUIVO_CONFIGURACAO, 'w', encoding='utf-8') as arquivo_configuracao:
            json.dump(dados, arquivo_configuracao, ensure_ascii=False, indent=2)

        cls._cache = {
            'mtime': os.path.getmtime(cls.ARQUIVO_CONFIGURACAO),
            'data': cls._normalizar_configuracao(dados),
        }

    @classmethod
    def _ler_arquivo_json(cls, caminho):
        with open(caminho, 'r', encoding='utf-8') as arquivo_configuracao:
            try:
                return json.load(arquivo_configuracao)
            except json.JSONDecodeError as erro:
                raise ValueError('O arquivo JSON de configuração de centros de custo está inválido.') from erro

    @classmethod
    def _configuracao_vazia(cls):
        return {
            'version': 2,
            'atualizado_em': None,
            'atualizado_por': {},
            'centros_custo_off': [],
            'gestores': [],
        }

    @classmethod
    def _normalizar_configuracao(cls, dados):
        configuracao = cls._configuracao_vazia()
        if not isinstance(dados, dict):
            return configuracao

        configuracao['version'] = dados.get('version') or 2
        configuracao['atualizado_em'] = cls._normalizar_texto(dados.get('atualizado_em'))

        atualizado_por = dados.get('atualizado_por') if isinstance(dados.get('atualizado_por'), dict) else {}
        configuracao['atualizado_por'] = {
            'id': cls._normalizar_codigo_usuario(atualizado_por.get('id')),
            'nome': cls._normalizar_texto(atualizado_por.get('nome')),
            'login': cls._normalizar_texto(atualizado_por.get('login')),
        }

        centros_off_vistos = set()
        centros_off = []
        for centro in dados.get('centros_custo_off', []):
            centro_normalizado = cls._normalizar_centro(centro)
            if not centro_normalizado:
                continue
            if centro_normalizado['codigo'] in centros_off_vistos:
                continue

            centros_off_vistos.add(centro_normalizado['codigo'])
            centros_off.append(centro_normalizado)

        codigos_off = {centro['codigo'] for centro in centros_off}
        gestores = []
        for gestor in dados.get('gestores', []):
            if not isinstance(gestor, dict):
                continue

            codigo_usuario = cls._normalizar_codigo_usuario(gestor.get('codigo_usuario'))
            if codigo_usuario is None:
                continue

            centros_vistos = set()
            centros = []
            for centro in gestor.get('centros_custo', []):
                centro_normalizado = cls._normalizar_centro(centro)
                if not centro_normalizado:
                    continue
                if (
                    centro_normalizado['codigo'] in centros_vistos
                    or centro_normalizado['codigo'] in codigos_off
                ):
                    continue

                centros_vistos.add(centro_normalizado['codigo'])
                centros.append(centro_normalizado)

            if not centros:
                continue

            gestores.append(
                {
                    'codigo_usuario': codigo_usuario,
                    'nome_usuario': cls._normalizar_texto(gestor.get('nome_usuario')) or f'Usuário {codigo_usuario}',
                    'login_usuario': cls._normalizar_texto(gestor.get('login_usuario')) or '',
                    'cargo': cls._normalizar_texto(gestor.get('cargo')) or 'Gestor',
                    'centros_custo': cls._ordenar_centros(centros),
                }
            )

        configuracao['centros_custo_off'] = cls._ordenar_centros(centros_off)
        configuracao['gestores'] = sorted(gestores, key=lambda item: item['nome_usuario'])
        return configuracao

    @classmethod
    def _normalizar_centros_off(cls, codigos_centros_off, centros_disponiveis):
        centros_off = []
        centros_vistos = set()
        for codigo_centro in codigos_centros_off:
            codigo_normalizado = cls._serializar_codigo(
                codigo_centro.get('codigo') if isinstance(codigo_centro, dict) else codigo_centro
            )
            if not codigo_normalizado or codigo_normalizado in centros_vistos:
                continue

            centro = centros_disponiveis.get(codigo_normalizado)
            if centro is None:
                raise ValueError(f'Centro de custo OFF inválido: {codigo_normalizado}.')

            centros_vistos.add(codigo_normalizado)
            centros_off.append(cls._montar_payload_centro(centro))

        return centros_off

    @classmethod
    def _normalizar_centro(cls, centro):
        if isinstance(centro, dict):
            codigo = cls._serializar_codigo(centro.get('codigo'))
            if not codigo:
                return None
            return {
                'codigo': codigo,
                'numero': cls._normalizar_texto(centro.get('numero')) or codigo,
                'nome': cls._normalizar_texto(centro.get('nome')) or 'Sem nome',
            }

        codigo = cls._serializar_codigo(centro)
        if not codigo:
            return None

        return {
            'codigo': codigo,
            'numero': codigo,
            'nome': 'Sem nome',
        }

    @classmethod
    def _montar_payload_centro(cls, centro):
        return {
            'codigo': centro['codigo'],
            'numero': centro['numero'],
            'nome': centro['nome'],
        }

    @classmethod
    def _ordenar_centros(cls, centros):
        return sorted(centros, key=lambda item: f"{item['numero']} {item['nome']}")

    @classmethod
    def _montar_identificacao_usuario(cls, usuario_editor):
        if usuario_editor is None:
            return {}

        return {
            'id': cls._normalizar_codigo_usuario(usuario_editor.get_id()) if hasattr(usuario_editor, 'get_id') else None,
            'nome': cls._normalizar_texto(
                getattr(usuario_editor, 'nome', None)
                or getattr(usuario_editor, 'Nome_Usuario', None)
                or getattr(usuario_editor, 'nome_completo', None)
            ),
            'login': cls._normalizar_texto(
                getattr(usuario_editor, 'login', None)
                or getattr(usuario_editor, 'Login_Usuario', None)
                or getattr(usuario_editor, 'email', None)
            ),
        }

    @staticmethod
    def _normalizar_codigo_usuario(valor):
        try:
            if valor is None or str(valor).strip() == '':
                return None
            return int(str(valor).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serializar_codigo(valor):
        if valor is None:
            return None

        if isinstance(valor, Decimal):
            if valor == valor.to_integral_value():
                return str(int(valor))
            return format(valor.normalize(), 'f')

        texto = str(valor).strip()
        return texto or None

    @staticmethod
    def _normalizar_texto(valor):
        if valor is None:
            return None
        texto = str(valor).strip()
        return texto or None
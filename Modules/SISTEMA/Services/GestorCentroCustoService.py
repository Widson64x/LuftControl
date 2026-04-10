import json
import os
from datetime import datetime
from decimal import Decimal

from Db.Connections import GetSqlServerSession
from Models.SqlServer.ContaPagar import CentroCusto
from Models.SqlServer.Usuario import Usuario
from Utils.Logger import RegistrarLog


class GestorCentroCustoService:
    PASTA_CONFIGURACAO = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../..', 'Data', 'Config')
    )
    ARQUIVO_CONFIGURACAO = os.path.join(PASTA_CONFIGURACAO, 'gestores_centro_custo.json')

    def __init__(self):
        self._garantir_arquivo_configuracao()

    def listarUsuariosDisponiveis(self):
        sessao = GetSqlServerSession()
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
                if registro.Codigo_Usuario is None:
                    continue

                codigo_usuario = int(registro.Codigo_Usuario)
                if codigo_usuario in usuarios_vistos:
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
        sessao = GetSqlServerSession()
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

    def carregarConfiguracao(self):
        self._garantir_arquivo_configuracao()
        with open(self.ARQUIVO_CONFIGURACAO, 'r', encoding='utf-8') as arquivo_configuracao:
            try:
                dados = json.load(arquivo_configuracao)
            except json.JSONDecodeError as erro:
                raise ValueError('O arquivo JSON de gestores por centro de custo está inválido.') from erro

        return self._normalizar_configuracao(dados)

    def salvarConfiguracao(self, payload, usuario_editor=None):
        gestores_recebidos = payload.get('gestores', []) if isinstance(payload, dict) else []
        if not isinstance(gestores_recebidos, list):
            raise ValueError('A configuração enviada é inválida.')

        usuarios_disponiveis = {
            usuario['codigo_usuario']: usuario
            for usuario in self.listarUsuariosDisponiveis()
        }
        centros_disponiveis = {
            centro['codigo']: centro
            for centro in self.listarCentrosCustoDisponiveis()
        }

        gestores_normalizados = []
        usuarios_vistos = set()

        for gestor in gestores_recebidos:
            if not isinstance(gestor, dict):
                continue

            codigo_usuario = self._normalizar_codigo_usuario(gestor.get('codigo_usuario'))
            cargo = self._normalizar_texto(gestor.get('cargo')) or 'Gestor'
            if codigo_usuario is None:
                continue

            if codigo_usuario not in usuarios_disponiveis:
                raise ValueError(f'Usuário inválido na configuração: {codigo_usuario}.')

            if codigo_usuario in usuarios_vistos:
                raise ValueError(f'O usuário {codigo_usuario} foi informado mais de uma vez na configuração.')

            codigos_centros = gestor.get('centros_custo', [])
            if not isinstance(codigos_centros, list):
                raise ValueError(f'Os centros de custo do usuário {codigo_usuario} estão inválidos.')

            centros_normalizados = []
            centros_vistos = set()
            for codigo_centro in codigos_centros:
                codigo_centro_normalizado = self._serializar_codigo(codigo_centro)
                if not codigo_centro_normalizado or codigo_centro_normalizado in centros_vistos:
                    continue

                centro = centros_disponiveis.get(codigo_centro_normalizado)
                if centro is None:
                    raise ValueError(
                        f'Centro de custo inválido para o usuário {codigo_usuario}: {codigo_centro_normalizado}.'
                    )

                centros_vistos.add(codigo_centro_normalizado)
                centros_normalizados.append(
                    {
                        'codigo': centro['codigo'],
                        'numero': centro['numero'],
                        'nome': centro['nome'],
                    }
                )

            if not centros_normalizados:
                continue

            usuario = usuarios_disponiveis[codigo_usuario]
            gestores_normalizados.append(
                {
                    'codigo_usuario': codigo_usuario,
                    'nome_usuario': usuario['nome_usuario'],
                    'login_usuario': usuario['login_usuario'],
                    'cargo': cargo,
                    'centros_custo': sorted(centros_normalizados, key=lambda item: item['rotulo'] if 'rotulo' in item else item['codigo']),
                }
            )
            usuarios_vistos.add(codigo_usuario)

        gestores_normalizados.sort(key=lambda item: item['nome_usuario'])

        configuracao_final = {
            'version': 1,
            'atualizado_em': datetime.now().isoformat(timespec='seconds'),
            'atualizado_por': self._montar_identificacao_usuario(usuario_editor),
            'gestores': gestores_normalizados,
        }

        self._gravar_configuracao(configuracao_final)

        usuario_log = configuracao_final['atualizado_por'].get('nome') or 'Sistema'
        RegistrarLog(
            f'Configuração de gestores por centro de custo atualizada por {usuario_log}. Total de gestores: {len(gestores_normalizados)}.',
            'System',
        )

        return configuracao_final

    def obterCentrosCustoDoGestor(self, codigo_usuario):
        codigo_usuario_normalizado = self._normalizar_codigo_usuario(codigo_usuario)
        if codigo_usuario_normalizado is None:
            return []

        configuracao = self.carregarConfiguracao()
        for gestor in configuracao.get('gestores', []):
            if gestor.get('codigo_usuario') == codigo_usuario_normalizado:
                return [centro['codigo'] for centro in gestor.get('centros_custo', [])]
        return []

    def _garantir_arquivo_configuracao(self):
        os.makedirs(self.PASTA_CONFIGURACAO, exist_ok=True)
        if not os.path.exists(self.ARQUIVO_CONFIGURACAO):
            self._gravar_configuracao(self._configuracao_vazia())

    def _gravar_configuracao(self, dados):
        with open(self.ARQUIVO_CONFIGURACAO, 'w', encoding='utf-8') as arquivo_configuracao:
            json.dump(dados, arquivo_configuracao, ensure_ascii=False, indent=2)

    def _configuracao_vazia(self):
        return {
            'version': 1,
            'atualizado_em': None,
            'atualizado_por': {},
            'gestores': [],
        }

    def _normalizar_configuracao(self, dados):
        configuracao = self._configuracao_vazia()
        if not isinstance(dados, dict):
            return configuracao

        configuracao['version'] = dados.get('version') or 1
        configuracao['atualizado_em'] = self._normalizar_texto(dados.get('atualizado_em'))

        atualizado_por = dados.get('atualizado_por') if isinstance(dados.get('atualizado_por'), dict) else {}
        configuracao['atualizado_por'] = {
            'id': self._normalizar_codigo_usuario(atualizado_por.get('id')),
            'nome': self._normalizar_texto(atualizado_por.get('nome')),
            'login': self._normalizar_texto(atualizado_por.get('login')),
        }

        gestores_normalizados = []
        for gestor in dados.get('gestores', []):
            if not isinstance(gestor, dict):
                continue

            codigo_usuario = self._normalizar_codigo_usuario(gestor.get('codigo_usuario'))
            if codigo_usuario is None:
                continue

            centros_normalizados = []
            centros_vistos = set()
            for centro in gestor.get('centros_custo', []):
                codigo = self._serializar_codigo(centro.get('codigo') if isinstance(centro, dict) else centro)
                if not codigo or codigo in centros_vistos:
                    continue

                centros_vistos.add(codigo)
                if isinstance(centro, dict):
                    numero = self._normalizar_texto(centro.get('numero')) or codigo
                    nome = self._normalizar_texto(centro.get('nome')) or 'Sem nome'
                else:
                    numero = codigo
                    nome = 'Sem nome'

                centros_normalizados.append(
                    {
                        'codigo': codigo,
                        'numero': numero,
                        'nome': nome,
                    }
                )

            gestores_normalizados.append(
                {
                    'codigo_usuario': codigo_usuario,
                    'nome_usuario': self._normalizar_texto(gestor.get('nome_usuario')) or f'Usuário {codigo_usuario}',
                    'login_usuario': self._normalizar_texto(gestor.get('login_usuario')) or '',
                    'cargo': self._normalizar_texto(gestor.get('cargo')) or 'Gestor',
                    'centros_custo': centros_normalizados,
                }
            )

        configuracao['gestores'] = sorted(gestores_normalizados, key=lambda item: item['nome_usuario'])
        return configuracao

    def _montar_identificacao_usuario(self, usuario_editor):
        if usuario_editor is None:
            return {}

        return {
            'id': self._normalizar_codigo_usuario(usuario_editor.get_id()) if hasattr(usuario_editor, 'get_id') else None,
            'nome': self._normalizar_texto(
                getattr(usuario_editor, 'nome', None)
                or getattr(usuario_editor, 'Nome_Usuario', None)
                or getattr(usuario_editor, 'nome_completo', None)
            ),
            'login': self._normalizar_texto(
                getattr(usuario_editor, 'login', None)
                or getattr(usuario_editor, 'Login_Usuario', None)
                or getattr(usuario_editor, 'email', None)
            ),
        }

    def _normalizar_codigo_usuario(self, valor):
        try:
            if valor is None or str(valor).strip() == '':
                return None
            return int(str(valor).strip())
        except (TypeError, ValueError):
            return None

    def _serializar_codigo(self, valor):
        if valor is None:
            return None

        if isinstance(valor, Decimal):
            if valor == valor.to_integral_value():
                return str(int(valor))
            return format(valor.normalize(), 'f')

        texto = str(valor).strip()
        return texto or None

    def _normalizar_texto(self, valor):
        if valor is None:
            return None
        texto = str(valor).strip()
        return texto or None
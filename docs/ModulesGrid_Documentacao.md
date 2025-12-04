# Módulo Modules-Grid: Ajustes Manuais

## Visão Geral

O módulo **Modules-Grid** permite a edição manual de dados da view `Razao_Dados_Consolidado` sem alterar a view original. Os ajustes são armazenados em tabelas próprias e mesclados na exibição.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLUXO DE DADOS                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────┐         ┌─────────────────────────┐           │
│   │ Razao_Dados_        │         │ Razao_Ajuste_Manual     │           │
│   │ Consolidado (VIEW)  │         │ (Sobrescrições)         │           │
│   │ [Somente Leitura]   │         │ [Editável]              │           │
│   └──────────┬──────────┘         └────────────┬────────────┘           │
│              │                                  │                        │
│              └──────────────┬───────────────────┘                        │
│                             │                                            │
│                             ▼                                            │
│                  ┌─────────────────────┐                                │
│                  │ Função MERGE        │                                │
│                  │ (merge_view_com_    │                                │
│                  │  ajustes)           │                                │
│                  └──────────┬──────────┘                                │
│                             │                                            │
│                             ▼                                            │
│                  ┌─────────────────────┐                                │
│                  │ DADOS FINAIS        │                                │
│                  │ (View + Ajustes)    │                                │
│                  └─────────────────────┘                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Fluxo de Aprovação

```
┌────────────────────────────────────────────────────────────────────────┐
│                     FLUXO DE APROVAÇÃO                                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. SOLICITAÇÃO                                                         │
│     ┌─────────────┐                                                     │
│     │ Usuário A   │──────────► Altera campo                            │
│     └─────────────┘                   │                                │
│                                       ▼                                │
│                              ┌─────────────────┐                       │
│                              │ Razao_Ajuste_   │                       │
│                              │ Log (Status=    │                       │
│                              │ Pendente)       │                       │
│                              └────────┬────────┘                       │
│                                       │                                │
│  2. APROVAÇÃO                         ▼                                │
│     ┌─────────────┐         ┌─────────────────┐                       │
│     │ Usuário B   │◄────────│ Lista Pendentes │                       │
│     │ (Aprovador) │         └─────────────────┘                       │
│     └──────┬──────┘                                                    │
│            │                                                            │
│            ├────────► APROVAR ─────────┐                               │
│            │                           │                                │
│            │                           ▼                                │
│            │                  ┌─────────────────┐                       │
│            │                  │ Log: Aprovado   │                       │
│            │                  │ Ajuste: Criado/ │                       │
│            │                  │ Atualizado      │                       │
│            │                  └─────────────────┘                       │
│            │                                                            │
│            └────────► REPROVAR ────────┐                               │
│                                        │                                │
│                                        ▼                                │
│                               ┌─────────────────┐                       │
│                               │ Log: Reprovado  │                       │
│                               │ Motivo registrado│                      │
│                               └─────────────────┘                       │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

## Tabelas

### 1. Razao_Ajuste_Manual

Armazena os ajustes aprovados que sobrescrevem valores da view.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Id | SERIAL | Chave primária |
| Origem | VARCHAR(50) | 'FARMA' ou 'FARMADIST' |
| Data | TIMESTAMP | Data do lançamento |
| Numero | VARCHAR(100) | Número do documento |
| Conta | VARCHAR(100) | Conta contábil |
| Item | VARCHAR(100) | Item (opcional) |
| *_Ajustado | Vários | Campos sobrescritos |
| NaoOperacional | BOOLEAN | Flag não operacional |
| NaoOperacional_Manual | BOOLEAN | Se foi alterado manualmente |
| Ativo | BOOLEAN | Se o ajuste está ativo |

**Chave única:** (Origem, Data, Numero, Conta, Item)

### 2. Razao_Ajuste_Log

Log de todas as alterações com histórico de aprovações.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Id | SERIAL | Chave primária |
| Id_Ajuste | INTEGER | FK para Razao_Ajuste_Manual |
| Origem, Data_Registro, Numero, Conta, Item | - | Identificação da linha |
| Campo_Alterado | VARCHAR(100) | Nome do campo alterado |
| Valor_Anterior | TEXT | Valor antes da alteração |
| Valor_Novo | TEXT | Novo valor proposto |
| Usuario_Alteracao | VARCHAR(100) | Quem solicitou |
| Data_Alteracao | TIMESTAMP | Quando solicitou |
| Status | VARCHAR(20) | Pendente/Aprovado/Reprovado/Cancelado |
| Usuario_Aprovacao | VARCHAR(100) | Quem aprovou/reprovou |
| Data_Aprovacao | TIMESTAMP | Quando foi decidido |
| Motivo_Reprovacao | TEXT | Motivo (se reprovado) |

### 3. Razao_Ajuste_Aprovacao

Histórico detalhado de decisões para auditoria.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Id | SERIAL | Chave primária |
| Id_Log | INTEGER | FK para Razao_Ajuste_Log |
| Decisao | VARCHAR(20) | 'Aprovado' ou 'Reprovado' |
| Usuario_Decisao | VARCHAR(100) | Quem decidiu |
| Data_Decisao | TIMESTAMP | Quando decidiu |
| Observacao | TEXT | Observações |
| IP_Origem | VARCHAR(50) | IP do aprovador |

## Rotas da API

### Páginas

| Rota | Método | Descrição |
|------|--------|-----------|
| `/ModulesGrid/` | GET | Página principal do grid |

### API de Dados

| Rota | Método | Descrição |
|------|--------|-----------|
| `/ModulesGrid/api/dados` | GET | Lista dados da view + ajustes |
| `/ModulesGrid/api/registro/<chave>` | GET | Detalhes de um registro |
| `/ModulesGrid/api/estatisticas` | GET | Estatísticas do módulo |

**Parâmetros de `/api/dados`:**
- `page`: Número da página (default: 1)
- `per_page`: Registros por página (default: 50, max: 500)
- `origem`: Filtro por origem
- `conta`: Filtro por conta (LIKE)
- `mes`: Filtro por mês
- `data_inicio`: Data inicial
- `data_fim`: Data final
- `apenas_ajustados`: true para mostrar só ajustados
- `apenas_nao_operacional`: true para mostrar só NaoOperacional

### API de Alterações

| Rota | Método | Descrição |
|------|--------|-----------|
| `/ModulesGrid/api/alterar` | POST | Submeter alteração para aprovação |

**Body esperado:**
```json
{
    "origem": "FARMA",
    "data": "2024-01-15T00:00:00",
    "numero": "12345",
    "conta": "1.1.01.001",
    "item": "10190",
    "alteracoes": {
        "titulo_conta": {"valor_anterior": "Antigo", "valor_novo": "Novo"},
        "saldo": {"valor_anterior": 100.50, "valor_novo": 0}
    }
}
```

**Campos válidos para alteração:**
- titulo_conta, descricao, contra_partida, filial
- centro_custo, item, cod_cl_valor
- debito, credito, saldo
- nao_operacional

### API de Aprovação

| Rota | Método | Descrição |
|------|--------|-----------|
| `/ModulesGrid/api/pendentes` | GET | Lista alterações pendentes |
| `/ModulesGrid/api/aprovar` | POST | Aprovar alterações |
| `/ModulesGrid/api/reprovar` | POST | Reprovar alterações |
| `/ModulesGrid/api/logs` | GET | Histórico de alterações |

**Aprovar:**
```json
{
    "ids": [1, 2, 3],
    "observacao": "Aprovado conforme solicitação"
}
```

**Reprovar:**
```json
{
    "ids": [1, 2, 3],
    "motivo": "Valores inconsistentes com a contabilidade"
}
```

## Permissões Necessárias

Configure as seguintes permissões no módulo de segurança:

| Slug | Descrição |
|------|-----------|
| `modules_grid.visualizar` | Visualizar dados e histórico |
| `modules_grid.editar` | Solicitar alterações |
| `modules_grid.aprovar` | Aprovar/reprovar alterações |

## Campo NaoOperacional

O campo `NaoOperacional` segue a regra:

1. **Valor Padrão:** TRUE se `Item = '10190'`
2. **Ajuste Manual:** Usuário pode alterar manualmente
3. **Flag de Controle:** `NaoOperacional_Manual` indica se foi alterado

## Instalação

### 1. Executar SQL

Execute o script `SQL/ModulesGrid_CreateTables.sql` no PostgreSQL:

```bash
psql -h localhost -U seu_usuario -d sua_base -f SQL/ModulesGrid_CreateTables.sql
```

### 2. Verificar Permissões

Certifique-se de que as permissões estão criadas na tabela de segurança:

```sql
INSERT INTO "Dre_Schema"."SEC_Permissions" ("Slug", "Descricao") VALUES
('modules_grid.visualizar', 'Visualizar grid de ajustes manuais'),
('modules_grid.editar', 'Solicitar ajustes manuais'),
('modules_grid.aprovar', 'Aprovar/reprovar ajustes manuais');
```

### 3. Reiniciar Aplicação

Reinicie o Flask para carregar o novo Blueprint:

```bash
python App.py
```

## Arquivos do Módulo

```
T-Controllership/
├── App.py                                    # Blueprint registrado
├── Models/POSTGRESS/ModulesGrid.py          # Models ORM
├── Routes/ModulesGrid.py                    # Blueprint e rotas
├── Templates/MENUS/ModulesGrid.html         # Interface do grid
├── SQL/ModulesGrid_CreateTables.sql         # Script de criação
└── docs/ModulesGrid_Documentacao.md         # Esta documentação
```

## Exemplos de Uso

### Listar dados com filtros (JavaScript)

```javascript
async function buscarDados() {
    const params = new URLSearchParams({
        page: 1,
        per_page: 50,
        origem: 'FARMA',
        mes: 'Janeiro'
    });

    const response = await fetch(`/ModulesGrid/api/dados?${params}`);
    const data = await response.json();

    if (data.success) {
        console.log('Total:', data.pagination.total);
        data.data.forEach(row => {
            console.log(row.Conta, row.Saldo, row.tem_ajuste);
        });
    }
}
```

### Submeter alteração (JavaScript)

```javascript
async function alterarSaldo(row) {
    const response = await fetch('/ModulesGrid/api/alterar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            origem: row.origem,
            data: row.Data,
            numero: row.Numero,
            conta: row.Conta,
            item: row.Item,
            alteracoes: {
                saldo: {
                    valor_anterior: row.Saldo,
                    valor_novo: 0  // Zerar saldo
                }
            }
        })
    });

    const result = await response.json();
    if (result.success) {
        alert('Alteração enviada para aprovação!');
    }
}
```

### Aprovar em lote (JavaScript)

```javascript
async function aprovarPendentes(ids) {
    const response = await fetch('/ModulesGrid/api/aprovar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ids: ids,
            observacao: 'Aprovação em lote'
        })
    });

    const result = await response.json();
    alert(result.msg);
}
```

## Considerações de Segurança

1. **Usuário não pode aprovar própria alteração:** Sistema impede que o solicitante aprove sua própria solicitação
2. **Log de IP:** O IP do aprovador é registrado para auditoria
3. **Histórico imutável:** Logs não podem ser alterados após criação
4. **Permissões granulares:** Visualizar, editar e aprovar são permissões separadas

## Troubleshooting

### Erro: "Permissão negada"
Verifique se o usuário tem a permissão necessária (`modules_grid.*`)

### Erro: "Registro não encontrado"
A chave deve estar no formato: `origem|data|numero|conta|item`

### Erro: "Usuário não pode aprovar própria alteração"
Outro usuário deve aprovar alterações solicitadas

### Ajuste não aparece na view
Verifique se o status do log é "Aprovado" e o ajuste está com `Ativo = TRUE`

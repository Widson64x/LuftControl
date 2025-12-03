# 📋 Mapeamento de Rotas - T-Controllership

## ℹ️ Informações Gerais
- **Base URL:** `http://localhost:5000` (ou `http://seu_dominio:5000`)
- **ROUTE_PREFIX:** Configurado via `.env` (padrão vazio)
- **Autenticação:** Flask-Login (Cookie session)
- **Permissões:** Sistema baseado em Roles e Permissões (Postgres)

---

## 🔐 AUTENTICAÇÃO (Auth Blueprint)

### 1. Login
- **URL:** `/Auth/login`
- **Método:** `GET, POST`
- **Autenticação:** ❌ Não requerida
- **Descrição:** Autentica usuário contra Active Directory + Banco SQL Server
- **Parâmetros (POST):**
  ```json
  {
    "username": "seu_usuario",
    "password": "sua_senha"
  }
  ```
- **Resposta:** Redireciona para Dashboard se sucesso

### 2. Logout
- **URL:** `/Auth/logout`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Descrição:** Desconecta o usuário
- **Resposta:** Redireciona para Login

---

## 📊 MAIN (Main Blueprint)

### 1. Dashboard
- **URL:** `/`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Descrição:** Página principal do sistema
- **Resposta:** Renderiza `Main.html`

### 2. Settings Hub (Centralizador de Configurações)
- **URL:** `/Settings`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Descrição:** Hub central para acessar todas as configurações do sistema
- **Resposta:** Renderiza `MENUS/Configuracoes.html`

---

## 📈 RELATÓRIOS (Reports Blueprint)
**Prefixo:** `/Reports`

### 1. Página Principal de Relatórios
- **URL:** `/Reports/`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Descrição:** Renderiza página de seleção de relatórios
- **Resposta:** Renderiza `MENUS/Relatórios.html`

### 2. Relatório Razão - Dados
- **URL:** `/Reports/RelatorioRazao/Dados`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Query Params:**
  - `page` (int): Número da página [default: 1]
  - `search` (string): Termo de busca
- **Resposta:** JSON com dados paginados do Razão Consolidado
- **Campos retornados:** Conta, Título, Data, Descrição, Débito, Crédito, Saldo, etc.

### 3. Relatório Razão - Resumo
- **URL:** `/Reports/RelatorioRazao/Resumo`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Query Params:**
  - `page` (int)
  - `search` (string)
- **Resposta:** JSON com resumo consolidado

### 4. Relatório Razão - Rentabilidade
- **URL:** `/Reports/RelatorioRazao/Rentabilidade`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Query Params:**
  - `page` (int)
  - `search` (string)
- **Resposta:** JSON com dados de rentabilidade

### 5. Relatório Razão - Rentabilidade por Centro de Custo
- **URL:** `/Reports/RelatorioRazao/RentabilidadePorCC`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Query Params:**
  - `page` (int)
  - `search` (string)
- **Resposta:** JSON com rentabilidade por CC

---

## 📐 CONFIGURAÇÃO DRE (DreConfig Blueprint)
**Prefixo:** `/DreConfig`

### Views/Templates

#### 1. Página de Configuração da Árvore
- **URL:** `/DreConfig/Configuracao/Arvore`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** Renderiza `MENUS/ConfiguracaoDRE.html`

### Consultas (GET)

#### 2. Dados da Árvore DRE Completa
- **URL:** `/DreConfig/Configuracao/GetDadosArvore`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com estrutura completa da DRE (hierarquia, virtuais, contas, etc.)

#### 3. Contas Disponíveis (não vinculadas)
- **URL:** `/DreConfig/Configuracao/GetContasDisponiveis`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com lista de contas disponíveis para vinculação

#### 4. Contas de um Subgrupo
- **URL:** `/DreConfig/Configuracao/GetContasDoSubgrupo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "subgrupo_id": "sg_123"
  }
  ```
- **Resposta:** JSON com contas do subgrupo

#### 5. Subgrupos por Tipo
- **URL:** `/DreConfig/Configuracao/GetSubgruposPorTipo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo": "tipo_cc_name"
  }
  ```
- **Resposta:** JSON com subgrupos filtrados

#### 6. Contas de Grupo em Massa
- **URL:** `/DreConfig/Configuracao/GetContasDoGrupoMassa`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "ids": ["sg_1", "sg_2"]
  }
  ```
- **Resposta:** JSON com contas de múltiplos grupos

#### 7. Nós Calculados
- **URL:** `/DreConfig/Configuracao/GetNosCalculados`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com todos os nós calculados (fórmulas)

#### 8. Operandos Disponíveis
- **URL:** `/DreConfig/Configuracao/GetOperandosDisponiveis`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com elementos que podem ser operandos em fórmulas

### Criação (ADD)

#### 9. Adicionar Subgrupo
- **URL:** `/DreConfig/Configuracao/AddSubgrupo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "nome": "Novo Subgrupo",
    "tipo_cc_id": "tipo_1",
    "descricao": "Descrição opcional"
  }
  ```
- **Resposta:** JSON com ID do novo subgrupo

#### 10. Adicionar Subgrupo Sistemático
- **URL:** `/DreConfig/Configuracao/AddSubgrupoSistematico`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo_cc_id": "tipo_1"
  }
  ```
- **Resposta:** JSON com subgrupos criados automaticamente

#### 11. Adicionar Nó Virtual
- **URL:** `/DreConfig/Configuracao/AddNoVirtual`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "nome": "Novo Nó Virtual",
    "ordem": 10
  }
  ```
- **Resposta:** JSON com ID do nó criado

#### 12. Adicionar Nó Calculado (Fórmula)
- **URL:** `/DreConfig/Configuracao/AddNoCalculado`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "nome": "Total Receitas",
    "formula": {
      "operador": "+",
      "operandos": ["conta_1", "conta_2"]
    }
  }
  ```
- **Resposta:** JSON com ID do nó calculado

#### 13. Vincular Conta
- **URL:** `/DreConfig/Configuracao/VincularConta`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "conta_id": "123456",
    "subgrupo_id": "sg_1"
  }
  ```
- **Resposta:** JSON com status da vinculação

#### 14. Vincular Conta Detalhe
- **URL:** `/DreConfig/Configuracao/VincularContaDetalhe`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "conta_id": "123456",
    "cc_id": "CC001",
    "subgrupo_id": "sg_1"
  }
  ```
- **Resposta:** JSON com status

#### 15. Vincular Contas em Massa
- **URL:** `/DreConfig/Configuracao/VincularContaEmMassa`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "contas": [
      {"conta_id": "123456", "subgrupo_id": "sg_1"},
      {"conta_id": "123457", "subgrupo_id": "sg_1"}
    ]
  }
  ```
- **Resposta:** JSON com resultado da operação

### Atualização (UPDATE/RENAME)

#### 16. Renomear Nó Virtual
- **URL:** `/DreConfig/Configuracao/RenameNoVirtual`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "id": "virt_1",
    "novo_nome": "Novo Nome"
  }
  ```
- **Resposta:** JSON com status

#### 17. Renomear Subgrupo
- **URL:** `/DreConfig/Configuracao/RenameSubgrupo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "sg_id": "sg_1",
    "novo_nome": "Novo Nome"
  }
  ```
- **Resposta:** JSON com status

#### 18. Renomear Conta Personalizada
- **URL:** `/DreConfig/Configuracao/RenameContaPersonalizada`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "conta_id": "cp_1",
    "novo_nome": "Novo Nome"
  }
  ```
- **Resposta:** JSON com status

#### 19. Atualizar Nó Calculado
- **URL:** `/DreConfig/Configuracao/UpdateNoCalculado`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "id": "calc_1",
    "nome": "Novo Nome",
    "formula": {
      "operador": "+",
      "operandos": ["conta_1", "conta_2"]
    }
  }
  ```
- **Resposta:** JSON com status

### Exclusão/Desvincular (DELETE)

#### 20. Deletar Subgrupo
- **URL:** `/DreConfig/Configuracao/DeleteSubgrupo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "sg_id": "sg_1"
  }
  ```
- **Resposta:** JSON com status

#### 21. Desvinular Conta
- **URL:** `/DreConfig/Configuracao/DesvincularConta`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "conta_id": "123456",
    "subgrupo_id": "sg_1"
  }
  ```
- **Resposta:** JSON com status

#### 22. Deletar Nó Virtual
- **URL:** `/DreConfig/Configuracao/DeleteNoVirtual`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "id": "virt_1"
  }
  ```
- **Resposta:** JSON com status

#### 23. Desvincular Contas em Massa
- **URL:** `/DreConfig/Configuracao/DesvincularContaEmMassa`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "contas": [
      {"conta_id": "123456", "subgrupo_id": "sg_1"}
    ]
  }
  ```
- **Resposta:** JSON com resultado

#### 24. Deletar Subgrupos em Massa
- **URL:** `/DreConfig/Configuracao/DeleteSubgrupoEmMassa`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "ids": ["sg_1", "sg_2"]
  }
  ```
- **Resposta:** JSON com resultado

### Operações Avançadas

#### 25. Replicar Estrutura
- **URL:** `/DreConfig/Configuracao/ReplicarEstrutura`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "origem_id": "sg_1"
  }
  ```
- **Resposta:** JSON com estrutura copiada para clipboard

#### 26. Colar Estrutura
- **URL:** `/DreConfig/Configuracao/ColarEstrutura`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "estrutura": {...},
    "pai_id": "sg_1"
  }
  ```
- **Resposta:** JSON com resultado da operação

### Utilitários

#### 27. Corrigir Banco
- **URL:** `/DreConfig/Configuracao/CorrigirBanco`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Descrição:** Corrige inconsistências no banco de dados
- **Resposta:** JSON com resultado

#### 28. Corrigir Constraint Personalizada
- **URL:** `/DreConfig/Configuracao/CorrigirConstraintPersonalizada`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com resultado

#### 29. Verificar Tabela Nó Virtual (Teste)
- **URL:** `/DreConfig/Teste/VerificarTabelaNoVirtual`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com informações de debug

---

## 📋 ORDENAMENTO DRE (DreOrdenamento Blueprint)
**Prefixo:** `/DreOrdenamento`

#### 1. Inicializar Ordenamento
- **URL:** `/DreOrdenamento/Ordenamento/Inicializar`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "limpar": false
  }
  ```
- **Resposta:** JSON com registros criados

#### 2. Obter Ordem
- **URL:** `/DreOrdenamento/Ordenamento/GetOrdem`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo_no": "subgrupo",
    "id_referencia": "sg_1",
    "contexto_pai": "root"
  }
  ```
- **Resposta:** JSON com dados de ordenamento

#### 3. Obter Filhos Ordenados
- **URL:** `/DreOrdenamento/Ordenamento/GetFilhosOrdenados`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "contexto_pai": "sg_1"
  }
  ```
- **Resposta:** JSON com lista de filhos ordenados

#### 4. Mover Elemento
- **URL:** `/DreOrdenamento/Ordenamento/Mover`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo_no": "conta",
    "id_referencia": "c_1",
    "novo_contexto_pai": "sg_2",
    "nova_ordem": 20
  }
  ```
- **Resposta:** JSON com status

#### 5. Reordenar Lote
- **URL:** `/DreOrdenamento/Ordenamento/ReordenarLote`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "elementos": [
      {"tipo_no": "conta", "id_referencia": "c_1", "nova_ordem": 10},
      {"tipo_no": "conta", "id_referencia": "c_2", "nova_ordem": 20}
    ]
  }
  ```
- **Resposta:** JSON com resultado

#### 6. Normalizar Ordenamento
- **URL:** `/DreOrdenamento/Ordenamento/Normalizar`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "contexto_pai": "sg_1"
  }
  ```
- **Resposta:** JSON com resultado

#### 7. Obter Árvore Ordenada
- **URL:** `/DreOrdenamento/Ordenamento/GetArvoreOrdenada`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com árvore completa ordenada

#### 8. Sincronizar Novo
- **URL:** `/DreOrdenamento/Ordenamento/SincronizarNovo`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo_no": "subgrupo",
    "id_referencia": "sg_nova",
    "contexto_pai": "root"
  }
  ```
- **Resposta:** JSON com resultado

#### 9. Remover Elemento do Ordenamento
- **URL:** `/DreOrdenamento/Ordenamento/RemoverElemento`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "tipo_no": "conta",
    "id_referencia": "c_1"
  }
  ```
- **Resposta:** JSON com resultado

---

## 🔐 SEGURANÇA (SecurityConfig Blueprint)
**Prefixo:** `/SecurityConfig`

### Views

#### 1. Gerenciador de Segurança
- **URL:** `/SecurityConfig/Manager`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Permissão:** `security.view`
- **Resposta:** Renderiza `MENUS/ConfiguracaoSeguranca.html`

#### 2. Visualizador de Segurança (Grafo)
- **URL:** `/SecurityConfig/Visualizador`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Permissão:** `security.view`
- **Resposta:** Renderiza `MENUS/SecurityMap.html`

### API

#### 3. Obter Grafo de Segurança
- **URL:** `/SecurityConfig/API/GetSecurityGraph`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com nós (roles, users, permissions) e arestas (relacionamentos)

#### 4. Obter Usuários Ativos
- **URL:** `/SecurityConfig/API/GetActiveUsers`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com lista de usuários ativos

#### 5. Atualizar Role do Usuário
- **URL:** `/SecurityConfig/API/UpdateUserRole`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "user_id": "1",
    "role_id": "2"
  }
  ```
- **Resposta:** JSON com status

#### 6. Obter Roles e Permissões
- **URL:** `/SecurityConfig/API/GetRolesAndPermissions`
- **Método:** `GET`
- **Autenticação:** ✅ Requerida
- **Resposta:** JSON com todas as roles e suas permissões

#### 7. Salvar Role
- **URL:** `/SecurityConfig/API/SaveRole`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "id": "null ou id_existente",
    "nome": "Nova Role",
    "descricao": "Descrição"
  }
  ```
- **Resposta:** JSON com ID da role salva

#### 8. Salvar Permissão
- **URL:** `/SecurityConfig/API/SavePermission`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "id": "null ou id_existente",
    "slug": "security.manage",
    "nome": "Gerenciar Segurança",
    "descricao": "Descrição"
  }
  ```
- **Resposta:** JSON com ID da permissão salva

#### 9. Deletar Role
- **URL:** `/SecurityConfig/API/DeleteRole`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "role_id": "1"
  }
  ```
- **Resposta:** JSON com status

#### 10. Deletar Permissão
- **URL:** `/SecurityConfig/API/DeletePermission`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "permission_id": "1"
  }
  ```
- **Resposta:** JSON com status

#### 11. Toggle Permissão Direta
- **URL:** `/SecurityConfig/API/ToggleDirectPermission`
- **Método:** `POST`
- **Autenticação:** ✅ Requerida
- **Body:**
  ```json
  {
    "user_id": "1",
    "permission_id": "1",
    "adicionar": true
  }
  ```
- **Resposta:** JSON com status

---

## 📝 Notas Importantes

1. **Headers Recomendados:**
   ```
   Content-Type: application/json
   Accept: application/json
   ```

2. **Autenticação:**
   - Use a rota `/Auth/login` para obter uma sessão (cookie)
   - Todos os endpoints com ✅ requerem estar autenticado
   - O cookie de sessão é enviado automaticamente nas requisições subsequentes

3. **Permissões:**
   - Algumas rotas requerem permissões específicas (ex: `security.view`)
   - As permissões são verificadas automaticamente no backend
   - Se sem permissão, retorna HTTP 403

4. **Tratamento de Erros:**
   - Respostas de erro geralmente retornam JSON com `error` ou `message`
   - HTTP 401 para não autenticado
   - HTTP 403 para sem permissão
   - HTTP 400 para requisição inválida

5. **Paginação:**
   - Relatórios suportam paginação com `page` e `per_page`
   - Default: 1000 registros por página

---

## 🚀 Exemplo de Fluxo Completo

### 1. Login
```
POST /Auth/login
Body: {
  "username": "usuario",
  "password": "senha"
}
```

### 2. Acessar Dashboard
```
GET /
```

### 3. Buscar Dados da DRE
```
GET /DreConfig/Configuracao/GetDadosArvore
```

### 4. Criar Novo Subgrupo
```
POST /DreConfig/Configuracao/AddSubgrupo
Body: {
  "nome": "Novo Subgrupo",
  "tipo_cc_id": "tipo_1"
}
```

### 5. Logout
```
GET /Auth/logout
```

---

**Gerado em:** Dezembro 2025
**Versão:** 1.0

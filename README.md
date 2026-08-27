#  Dona Geralda — Automação de Auditoria e Validação de ICs

A **Dona Geralda** é uma solução inteligente desenvolvida em Python para automatizar o processo de auditoria, padronização de arquivos e direcionamento de Indicações de Condutor (ICs). Integrando o **Google Gemini 2.5 Flash**, **Google Drive API** e **Slack Bolt Framework**, o bot reduz a verificação manual e elimina gargalos operacionais.

---

##  Principais Funcionalidades

* 📑 **Padronização Automática no Drive:** Identifica documentos por visão computacional (Gemini 2.5) e renomeia os PDFs para nomes curtos padronizados (`cnh cond.pdf`, `doc prop.pdf`, `cs.pdf`, etc.).
* 🔍 **Auditoria Multimodal:** Analisa contratos, CNHs e formulários para determinar o status do processo (*Pronto para Envio*, *Validação Manual* ou *Solicitar Documentação*).
* 💬 **Integração Interativa com Slack:**
  * Dispara notificações automáticas de auditoria e relatórios diários de progresso.
  * Permite disparo manual de varredura via comando (`@Dona Geralda rodar nova rodada`).
  * Permite atualização de status e mapeamento dinâmico de responsáveis por órgãos autuadores via chat.
* 🎯 **Gestão de Responsáveis Sem Gargalos:** Consulta dinamicamente a tabela `responsaveis.csv` para marcar o analista correto no Slack, evitando que todos os casos caiam para uma única pessoa.

---

## ⚙️ Arquitetura do Projeto

* **`main.py`**: Aplicação principal contendo a escuta do Slack (Socket Mode), integração com Google Drive API, chamadas para a Gemini API e agendadores de tarefas.
* **`responsaveis.csv`**: Tabela de mapeamento contendo os órgãos e seus respectivos responsáveis/IDs do Slack.
* **`historico_geral.csv`**: Base de dados local contendo os históricos de auditorias e status de cada BOBA.

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos
* Python 3.10+
* Credenciais de Conta de Serviço do Google Cloud (com acesso à API do Google Drive)
* Bot no Slack configurado com Socket Mode ativado

### 2. Configuração do Ambiente
Crie um arquivo `.env` na raiz do projeto com base no arquivo `.env.example` preenchendo suas chaves de API e tokens do Slack/Drive.

### 3. Instalação e Execução

Instale as dependências executando:
`pip install google-genai google-api-python-client google-auth pandas slack-bolt python-dotenv`

Para iniciar o bot, execute:
`python main.py`

---

##  Comandos Disponíveis no Slack

| Comando | Descrição |
| :--- | :--- |
| `@Dona Geralda rodar nova rodada` | Inicia uma verificação imediata das pastas no Google Drive |
| `@Dona Geralda orgao PRF = @Tamires` | Mapeia um novo órgão autuador para um responsável na tabela |
| `@Dona Geralda BOBA 14200 aprovado` | Atualiza manualmente o status de um BOBA no histórico |
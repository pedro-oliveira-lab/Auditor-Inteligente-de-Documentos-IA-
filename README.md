### 🧠 Auditor de Documentos (IA)
Este projeto aplica **Inteligência Artificial Multimodal** para segurança e conformidade:
* **Integração com Gemini 1.5 Flash:** Processamento de alta performance para análise de imagens e PDFs.
* **Análise Multimodal:** A IA "lê" e "enxerga" os documentos, permitindo conferir **assinaturas e padrões visuais**.
* **Conferência Cruzada (Cross-check):** Função que valida se o **CPF, Nome e Validade** batem entre três documentos diferentes (ex: CNH vs. Formulário).
* **Relatório de Auditoria:** Gera um feedback imediato com status de **APROVADO** ou **REVISÃO MANUAL**, detalhando qualquer inconsistência encontrada.
  
🚀 O Problema que este projeto resolve
Em processos de cadastro ou contratação, a conferência manual de documentos (como CNH, comprovantes e formulários) é lenta e sujeita a erros humanos. Este script automatiza:

Conferência Cruzada: Garante que Nome, CPF e Data de Validade sejam idênticos em todas as fontes.

Análise Visual: Identifica divergências em assinaturas e padrões visuais.

Detecção de Fraudes: Busca sinais de adulteração ou inconsistência nos arquivos.

🛠️ Tecnologias Utilizadas
Python 3.x

Google GenAI SDK: Integração com o modelo Gemini 1.5 Flash.

Gemini 1.5 Flash: Escolhido pela alta velocidade de processamento e excelente capacidade de análise multimodal (PDFs e Imagens).

📋 Funcionalidades
[x] Upload Automático: Gerenciamento de arquivos e monitoramento do estado de processamento na nuvem.

[x] Auditoria Multimodal: Analisa simultaneamente múltiplos documentos (Ex: CNH, Comprovante de Residência e Formulário de Cadastro).

[x] Relatório Estruturado: Gera automaticamente um status de APROVADO ou REVISÃO MANUAL, incluindo uma tabela comparativa dos dados extraídos.

🔧 Como usar
** 1. Instale as dependências:**

** 2. Configure sua API KEY: Obtenha sua chave no Google AI Studio e insira na variável API_KEY no script.**

** 3. Execute o auditor**

Roadmap / Próximos Passos
[ ] Integrar com o projeto de RPA (Hermes Prospector) para validar documentos de leads automaticamente.

[ ] Criar uma interface gráfica para facilitar o upload por usuários não técnicos.

[ ] Implementar exportação do relatório final em formato JSON ou Excel.

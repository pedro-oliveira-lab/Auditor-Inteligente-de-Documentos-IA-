from google import genai
from google.genai import types 
import time

# 1. Configuração 
API_KEY = ""
client = genai.Client(api_key=API_KEY)

def realizar_upload(caminho):
    print(f"📤 Enviando: {caminho}...")
    arquivo = client.files.upload(file=caminho)
    
    while arquivo.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        arquivo = client.files.get(name=arquivo.name)
    
    print(f"\n✅ {caminho} pronto!")
    return arquivo

def comparar_documentos(caminho1, caminho2, caminho3):
    doc1 = realizar_upload(caminho1)
    doc2 = realizar_upload(caminho2)
    doc3 = realizar_upload(caminho3)

    prompt = """
    Você é um auditor especialista em conferência de documentos. 
    Analise os três arquivos fornecidos e realize as seguintes verificações:
    
    1. **Dados Textuais:** Compare Nome, CPF e Data de Validade. Eles são idênticos em todos os documentos? 
    2. **Assinaturas:** Olhe visualmente para as assinaturas nos documentos. Elas possuem padrões similares ou há divergências óbvias?
    3. **Consistência:** Algum dos documentos parece apresentar sinais de adulteração?
    4. **Preenchimento:** Os formulários enviados estão preenchidos completamente?

    Retorne um relatório estruturado:
    - STATUS (APROVADO / REVISÃO MANUAL)
    - DIVERGÊNCIAS ENCONTRADAS (se houver)
    - TABELA COMPARATIVA DE DADOS (Nome, CPF, Validade)
    """

    print("\n🧐 Iniciando auditoria comparativa com Gemini 1.5 Flash...")
    
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[doc1, doc2, doc3, prompt]
    )
    
    print("\n--- RESULTADO DA ANÁLISE ---")
    print(response.text)

if __name__ == "__main__":
    # Nomes dos arquivos (veja se eles estão na pasta do projeto com o nome correto)
    pdf1 = os.path.join(diretorio_atual, "cs.pdf")
    pdf2 = os.path.join(diretorio_atual, "cnh.pdf")
    pdf3 = os.path.join(diretorio_atual, "formulario.pdf")
    arquivos_existem = True
    for p in [pdf1, pdf2, pdf3]:
        if not os.path.exists(p):
            print(f"❌ Arquivo não encontrado: {p}")
            arquivos_existem = False
    if arquivos_existem:
        try:
            comparar_documentos(pdf1, pdf2, pdf3)
        except Exception as e:
            print(f"❌ Erro na execução: {e}")
    else:
        print("💡 Dica: Verifique se os PDFs estão na mesma pasta que o seu arquivo .py")

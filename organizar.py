import os
import pandas as pd

CAMINHO_HISTORICO = 'historico_geral.csv'

def verificar_cnhs_condutor():
    """
    Lê o histórico geral e filtra todos os casos que possuem
    o número da CNH do condutor preenchido (ignorando N/A, vazios e nulos).
    """
    if not os.path.exists(CAMINHO_HISTORICO):
        print(f"❌ Arquivo '{CAMINHO_HISTORICO}' não foi encontrado na pasta atual.")
        return

    print(f"🔍 Lendo o histórico de '{CAMINHO_HISTORICO}'...\n")
    df = pd.read_csv(CAMINHO_HISTORICO, encoding='utf-8-sig')

    # Identifica a coluna correta de CNH do condutor
    coluna_cnh = None
    for col in ['cnh_condutor', 'condutor_cnh', 'cnh']:
        if col in df.columns:
            coluna_cnh = col
            break

    if not coluna_cnh:
        print("⚠️ Coluna de CNH do condutor não encontrada na planilha.")
        return

    # Normaliza textos e remove espaços extras
    df[coluna_cnh] = df[coluna_cnh].astype(str).str.strip()
    
    # Filtro para ignorar valores vazios, N/A, nan, etc.
    valores_invalidos = ['', 'nan', 'n/a', 'na', 'none', 'null', 'sem cnh', 'sem cnh/doc']
    filtro_validos = ~df[coluna_cnh].str.lower().isin(valores_invalidos)
    
    df_com_cnh = df[filtro_validos].copy()

    total_registros = len(df)
    total_com_cnh = len(df_com_cnh)

    print("=" * 60)
    print(f"🎯 NÚMERO TOTAL DE CNHs DE CONDUTORES ENCONTRADAS: {total_com_cnh}")
    print("=" * 60)
    print(f"• Total de registros analisados na base: {total_registros}")
    print(f"• Registros com CNH preenchida: {total_com_cnh}")
    print("=" * 60 + "\n")

    if df_com_cnh.empty:
        print("ℹ️ Nenhum caso encontrado com CNH do condutor preenchida.")
        return

    # Exibe a lista formatada no terminal
    for idx, linha in df_com_cnh.iterrows():
        boba = linha.get('boba', 'N/A')
        cliente = linha.get('cliente', 'N/A')
        condutor = linha.get('condutor', 'N/A')
        cnh = linha.get(coluna_cnh, 'N/A')
        status = linha.get('status', 'N/A')

        print(f"🔹 BOBA {boba} | Cliente: {cliente}")
        print(f"   👤 Condutor: {condutor}")
        print(f"   🪪 CNH: {cnh}")
        print(f"   📌 Status: {status}")
        print("-" * 50)

    # Opcional: Salva um relatório limpo apenas com esses casos
    caminho_saida = 'relatorio_cnhs_encontradas.csv'
    df_com_cnh.to_csv(caminho_saida, index=False, encoding='utf-8-sig')
    print(f"\n💾 Relatório salvo com sucesso em '{caminho_saida}'!")

if __name__ == "__main__":
    verificar_cnhs_condutor()
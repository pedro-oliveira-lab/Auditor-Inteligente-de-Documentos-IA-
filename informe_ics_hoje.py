import os
import json
import urllib.request
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "#analise-de-ics")
SLACK_URL = os.getenv("SLACK_WEBHOOK_URL")
CAMINHO_HISTORICO = 'historico_geral.csv'

# Inicializa o app Bolt do Slack se as credenciais estiverem presentes
slack_app = App(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None


def enviar_mensagem_slack(mensagem):
    """Envia uma mensagem formatada para o canal do Slack via API do Bot ou Webhook fallback."""
    if slack_app and SLACK_CHANNEL_ID:
        try:
            slack_app.client.chat_postMessage(
                channel=SLACK_CHANNEL_ID,
                text=mensagem
            )
            print("✅ Relatório enviado com sucesso via Slack Bot App!")
            return
        except Exception as e:
            print(f"⚠️ Erro ao enviar via Bot Slack: {e}")

    if SLACK_URL:
        data = json.dumps({"text": mensagem}).encode('utf-8')
        try:
            req = urllib.request.Request(
                SLACK_URL, data=data, headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
            print("✅ Relatório enviado com sucesso via Webhook do Slack!")
        except Exception as e:
            print(f"⚠️ Falha no envio via Webhook do Slack: {e}")
    else:
        print("⚠️ Nenhuma credencial do Slack configurada. Exibindo no terminal:")
        print(mensagem)


def gerar_informe_hoje():
    """Lê o histórico geral, filtra os registros da data atual e calcula o resumo final."""
    if not os.path.exists(CAMINHO_HISTORICO):
        print(f"❌ Arquivo '{CAMINHO_HISTORICO}' não foi encontrado.")
        return

    # Puxa a data de hoje dinamicamente (formatos DD/MM/AAAA e DD/MM)
    hoje_dt = datetime.now()
    data_hoje_completa = hoje_dt.strftime("%d/%m/%Y")
    data_hoje_curta = hoje_dt.strftime("%d/%m")

    print(f"🚀 Lendo arquivo de histórico para o dia de hoje ({data_hoje_completa})...")
    df = pd.read_csv(CAMINHO_HISTORICO, encoding='utf-8-sig')

    # Normaliza colunas principais
    df['boba'] = df['boba'].astype(str).str.strip()
    df['status'] = df['status'].astype(str).str.strip()

    if 'link_drive' not in df.columns:
        df['link_drive'] = ""
    else:
        df['link_drive'] = df['link_drive'].astype(str).str.strip()

    if 'data_processamento' not in df.columns:
        print("⚠️ Coluna 'data_processamento' não encontrada na planilha.")
        return

    df['data_processamento'] = df['data_processamento'].astype(str).str.strip()

    # Filtra registros que correspondam à data de hoje
    filtro_datas = df['data_processamento'].str.contains(
        f"{data_hoje_completa}|{data_hoje_curta}", regex=True, na=False
    )
    df_filtrado = df[filtro_datas].copy()

    if df_filtrado.empty:
        print(f"ℹ️ Nenhum registro encontrado para a data de hoje ({data_hoje_completa}).")
        enviar_mensagem_slack(
            f"📊 *Relatório do Dia ({data_hoje_completa}):* Nenhum registro processado hoje no histórico."
        )
        return

    total_processos = len(df_filtrado)
    print(f"🔍 Encontrados {total_processos} registro(s) para o dia {data_hoje_completa}.")

    verdes = []
    amarelos = []
    vermelhos = []

    for _, linha in df_filtrado.iterrows():
        boba_id = linha.get('boba', 'N/A')
        status = linha.get('status', 'Sem status')
        link_drive = linha.get('link_drive', '')

        # Formata o identificador do BOBA com o link clicável no Slack se houver URL
        if link_drive and link_drive.startswith("http"):
            boba_formatado = f"<{link_drive}|*BOBA {boba_id}*>"
        else:
            boba_formatado = f"*BOBA {boba_id}*"

        item_str = f"• {boba_formatado} — _{status}_"
        status_lower = status.lower()

        # Categoria 🟢 Verde (Aprovados / Prontos para envio)
        if any(termo in status_lower for termo in ["podemos enviar", "validado", "aprovado", "ok"]):
            verdes.append(item_str)
        # Categoria 🟡 Amarelo (Aguardando validação manual)
        elif any(termo in status_lower for termo in ["necessita de validação", "validação manual", "revisão"]):
            amarelos.append(item_str)
        # Categoria 🔴 Vermelho (Solicitar documentação / Reprovados / Erros)
        else:
            vermelhos.append(item_str)

    qtd_verdes = len(verdes)
    qtd_amarelos = len(amarelos)
    qtd_vermelhos = len(vermelhos)

    pct_verdes = (qtd_verdes / total_processos * 100) if total_processos > 0 else 0
    pct_amarelos = (qtd_amarelos / total_processos * 100) if total_processos > 0 else 0
    pct_vermelhos = (qtd_vermelhos / total_processos * 100) if total_processos > 0 else 0

    msg = f"📋 *Informe de ICs — Auditados em {data_hoje_completa}*\n\n"

    # Seção Verde
    msg += f"🟢 *Aprovados / Prontos para Envio ({qtd_verdes}):*\n"
    if verdes:
        msg += "\n".join(verdes) + "\n\n"
    else:
        msg += "└ _Nenhum item nesta categoria_\n\n"

    # Seção Amarela
    msg += f"🟡 *Necessitam de Validação Manual ({qtd_amarelos}):*\n"
    if amarelos:
        msg += "\n".join(amarelos) + "\n\n"
    else:
        msg += "└ _Nenhum item nesta categoria_\n\n"

    # Seção Vermelha
    msg += f"🔴 *Solicitar Documentação / Reprovados ({qtd_vermelhos}):*\n"
    if vermelhos:
        msg += "\n".join(vermelhos) + "\n\n"
    else:
        msg += "└ _Nenhum item nesta categoria_\n\n"

    # Bloco Consolidado no Final
    msg += "──────────────────────────────────────────\n"
    msg += "📊 *CÁLCULO E RESUMO CONSOLIDADO:* \n"
    msg += f"• 🟢 *Aprovados / Prontos para Envio:* `{qtd_verdes}` ({pct_verdes:.1f}%)\n"
    msg += f"• 🟡 *Necessitam de Validação Manual:* `{qtd_amarelos}` ({pct_amarelos:.1f}%)\n"
    msg += f"• 🔴 *Solicitar Documentação / Reprovados:* `{qtd_vermelhos}` ({pct_vermelhos:.1f}%)\n"
    msg += f"📌 *TOTAL GERAL AUDITADO HOJE:* `{total_processos} BOBAs`\n"
    msg += "──────────────────────────────────────────\n"
    msg += "✨ _Relatório gerado automaticamente a partir do Histórico Geral._"

    enviar_mensagem_slack(msg)


if __name__ == "__main__":
    print("🤖 Gerando informe diário de ICs com data automática...")
    gerar_informe_hoje()
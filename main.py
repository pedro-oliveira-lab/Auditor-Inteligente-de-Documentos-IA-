import os
import re
import time
import json
import threading
import urllib.request
import io
from datetime import datetime
import pandas as pd
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Bibliotecas Oficiais do Slack para Botões e Escuta Interativa
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# Inicialização dos serviços
client_pago = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if os.getenv("GEMINI_API_KEY") else None

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
ID_PASTA_RAIZ = os.getenv("ID_PASTA_RAIZ_DRIVE")
SLACK_URL = os.getenv("SLACK_WEBHOOK_URL")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "#analise-de-ics")
CAMINHO_HISTORICO = 'historico_geral.csv'
CAMINHO_RESPONSAVEIS = 'responsaveis.csv'

creds = None
service_drive = None
if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service_drive = build('drive', 'v3', credentials=creds)

# Inicializa o app Bolt do Slack
slack_app = App(token=SLACK_BOT_TOKEN) if (SLACK_BOT_TOKEN and SLACK_APP_TOKEN) else None

# Controle de estado global
varredura_em_andamento = False
relatorios_disparados_hoje = set()
Avisos_comandos_disparados_hoje = set()

# Mapeamento Oficial de Renomeação de Documentos
MAPA_NOMES_CURTOS = {
    "CNH CONDUTOR": "cnh cond.pdf",
    "CNH PROCURADOR": "cnh proc.pdf",
    "DOCUMENTO PROPRIETÁRIO": "doc prop.pdf",
    "DOCUMENTO PROCURADOR": "doc proc.pdf",
    "CNH PROPRIETÁRIO": "cnh prop.pdf",
    "CONTRATO SOCIAL": "cs.pdf",
    "CONTRATO DE LOCAÇÃO": "cl.pdf",
    "PROCURAÇÃO": "proc.pdf",
    "TERMO DE RESPONSABILIDADE": "tr.pdf"
}

# ==========================================
# GESTÃO DE HISTÓRICO E RESPONSÁVEIS
# ==========================================
def carregar_historico():
    if not os.path.exists(CAMINHO_HISTORICO):
        return pd.DataFrame(columns=[
            'boba', 'cliente', 'status', 'data_processamento', 
            'placa', 'condutor', 'proprietario', 'cnh_condutor', 'cnh_proprietario', 'ait', 'orgao', 'link_drive'
        ])
    try:
        df = pd.read_csv(CAMINHO_HISTORICO, encoding='utf-8-sig')
        df['boba'] = df['boba'].astype(str).str.strip()
        if 'data_processamento' in df.columns:
            df['data_processamento'] = df['data_processamento'].astype(str).str.strip()
        if 'link_drive' not in df.columns:
            df['link_drive'] = ""
        return df
    except Exception:
        return pd.DataFrame()

def salvar_no_historico(dados):
    df = carregar_historico()
    novo_df = pd.DataFrame([dados])
    df = pd.concat([df, novo_df], ignore_index=True)
    df = df.drop_duplicates(subset=['boba'], keep='last')
    df.to_csv(CAMINHO_HISTORICO, index=False, encoding='utf-8-sig')

def atualizar_status_boba_no_csv(boba_id, novo_status):
    if not os.path.exists(CAMINHO_HISTORICO):
        return False
    try:
        df = pd.read_csv(CAMINHO_HISTORICO, encoding='utf-8-sig')
        df['boba'] = df['boba'].astype(str).str.strip()
        
        idx = df[df['boba'] == str(boba_id).strip()].index
        if not idx.empty:
            df.loc[idx, 'status'] = novo_status
            df.to_csv(CAMINHO_HISTORICO, index=False, encoding='utf-8-sig')
            return True
    except Exception as e:
        print(f"⚠️ Erro ao atualizar status no CSV: {e}")
    return False

def atualizar_ou_inserir_responsavel(orgao, user_id, email="", nome=""):
    """Atualiza ou insere o responsável pelo órgão no responsaveis.csv"""
    linhas = []
    atualizado = False
    orgao_normalizado = orgao.strip()
    
    if os.path.exists(CAMINHO_RESPONSAVEIS):
        try:
            df_resp = pd.read_csv(CAMINHO_RESPONSAVEIS, sep=';', encoding='utf-8-sig')
            df_resp['orgao'] = df_resp['orgao'].fillna('').astype(str)
            
            # Verifica se órgão já existe
            idx = df_resp[df_resp['orgao'].str.strip().str.upper() == orgao_normalizado.upper()].index
            if not idx.empty:
                df_resp.loc[idx, 'id'] = user_id
                if email: df_resp.loc[idx, 'email'] = email
                if nome: df_resp.loc[idx, 'nome'] = nome
                atualizado = True
            
            if not atualizado:
                novo_row = pd.DataFrame([{"orgao": orgao_normalizado, "id": user_id, "email": email, "nome": nome}])
                df_resp = pd.concat([df_resp, novo_row], ignore_index=True)
            
            df_resp.to_csv(CAMINHO_RESPONSAVEIS, sep=';', index=False, encoding='utf-8-sig')
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar responsável: {e}")
            return False
    return False

def buscar_mencao_responsavel(nome_pasta, orgao_doc=""):
    """Procura no responsaveis.csv a tag do Slack do responsável evitando jogar tudo para o Lucas"""
    ID_LUCAS = "<@U09TMPM0UBS>"
    if not os.path.exists(CAMINHO_RESPONSAVEIS):
        return ID_LUCAS
    try:
        df_resp = pd.read_csv(CAMINHO_RESPONSAVEIS, sep=';', encoding='utf-8-sig')
        texto_busca = f"{nome_pasta} {orgao_doc}".upper()
        
        for _, linha in df_resp.iterrows():
            orgao_csv = str(linha.get('orgao', '')).strip().upper()
            if orgao_csv and orgao_csv in texto_busca:
                slack_id = str(linha.get('id', '')).strip()
                if slack_id and slack_id.lower() != 'nan' and slack_id != '':
                    return f"<@{slack_id}>"
    except Exception as e:
        print(f"⚠️ Erro ao consultar responsável: {e}")
    return ID_LUCAS

def sincronizar_orgaos_historico_sem_dono():
    """Varre o histórico, identifica órgãos não atribuídos e notifica no Slack"""
    df_hist = carregar_historico()
    if df_hist.empty or 'orgao' not in df_hist.columns:
        return

    orgaos_unicos = df_hist['orgao'].dropna().unique()
    orgaos_sem_dono = []

    for orgao in orgaos_unicos:
        orgao_str = str(orgao).strip()
        if not orgao_str or orgao_str.upper() in ["N/A", "NAN"]:
            continue
        resp = buscar_mencao_responsavel("", orgao_str)
        if resp == "<@U09TMPM0UBS>": # Se caiu no Lucas padrão
            # Mapeamentos prévios por regra
            if any(term in orgao_str.upper() for term in ["PRF", "POLICIA RODOVIARIA", "DER"]):
                atualizar_ou_inserir_responsavel(orgao_str, "U0A19TCSASC", "tamires@frota162.com.br", "Tamires")
            elif any(term in orgao_str.upper() for term in ["PMSP", "PREFEITURA DE SAO PAULO", "PREFEITURA DE SÃO PAULO"]):
                atualizar_ou_inserir_responsavel(orgao_str, "U0AQ62G5LKZ", "gabriela.perez@frota162.com.br", "Gabriela")
            elif "DNIT" in orgao_str.upper():
                atualizar_ou_inserir_responsavel(orgao_str, "U08AUL8MUDN", "nicolas@frota162.com.br", "Nicolas")
            else:
                orgaos_sem_dono.append(orgao_str)

    if orgaos_sem_dono:
        lista_fmt = "\n".join([f"• `{o}`" for o in set(orgaos_sem_dono)])
        msg = (
            f"❓ *Atenção Operações! Encontrei órgãos no histórico sem responsável mapeado:*\n\n"
            f"{lista_fmt}\n\n"
            f"Por favor, me avisem respondendo com: `@Dona Geralda orgao NOME_DO_ORGAO = @RESPONSAVEL`"
        )
        enviar_para_slack_nativo(msg)

# ==========================================
# MENAGENS E COMANDOS SLACK
# ==========================================
def enviar_para_slack_nativo(mensagem):
    if slack_app:
        try:
            slack_app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=mensagem)
            return
        except Exception as e:
            print(f"⚠️ Falha no envio via Bot Slack: {e}")
            
    if SLACK_URL:
        data = json.dumps({"text": mensagem}).encode('utf-8')
        try:
            req = urllib.request.Request(SLACK_URL, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
        except Exception as e:
            print(f"⚠️ Falha no Webhook Slack: {e}")

def enviar_instrucoes_comandos_slack():
    msg = (
        "📢 *Comandos disponíveis para a @Dona Geralda:*\n\n"
        "1️⃣ *Iniciar Nova Rodada de Análise:*\n"
        "   └ `@Dona Geralda rodar nova rodada` (Inicia a verificação de pastas no Drive)\n\n"
        "2️⃣ *Mapear Órgão para um Responsável:*\n"
        "   └ `@Dona Geralda orgao PRF = @Tamires` ou `@Dona Geralda orgao DETRAN SP = @Gabriela`\n\n"
        "3️⃣ *Atualizar Status de um BOBA Manualmente:*\n"
        "   └ `@Dona Geralda BOBA 14200 aprovado` ou `@Dona Geralda BOBA 14200 reprovado`"
    )
    enviar_para_slack_nativo(msg)
# ==========================================
# FUNÇÕES DE EXTRAÇÃO E INFORME
# ==========================================
def extrair_dados_do_nome(nome_p):
    """Extrai BOBA, Cliente, AIT e Placa a partir do nome da pasta"""
    nome_limpo = nome_p.replace("-", " ")
    partes = nome_limpo.split(" ")
    try:
        boba_id = partes[partes.index("BOBA") + 1].strip()
    except Exception:
        boba_id = nome_p.strip()

    cliente_limpo, placa_extraida, ait_extraido = nome_p, "", ""
    if " - " in nome_p:
        partes_nome = [p.strip() for p in nome_p.split(" - ")]
        if len(partes_nome) >= 4:
            cliente_limpo, ait_extraido, placa_extraida = partes_nome[1], partes_nome[2], partes_nome[3]
        elif len(partes_nome) == 3:
            cliente_limpo, placa_extraida = partes_nome[1], partes_nome[2]
        elif len(partes_nome) == 2:
            cliente_limpo = partes_nome[1]

    return boba_id, cliente_limpo, ait_extraido, placa_extraida

def gerar_e_enviar_informe_hoje(horario_rotulo=""):
    """Lê o histórico geral, filtra a data atual e publica o relatório formatado no Slack"""
    if not os.path.exists(CAMINHO_HISTORICO):
        return

    hoje_dt = datetime.now()
    data_hoje_completa = hoje_dt.strftime("%d/%m/%Y")
    data_hoje_curta = hoje_dt.strftime("%d/%m")

    df = pd.read_csv(CAMINHO_HISTORICO, encoding='utf-8-sig')
    if df.empty or 'data_processamento' not in df.columns:
        return

    df['boba'] = df['boba'].astype(str).str.strip()
    df['status'] = df['status'].astype(str).str.strip()
    df['link_drive'] = df.get('link_drive', "").astype(str).str.strip()
    df['data_processamento'] = df['data_processamento'].astype(str).str.strip()

    filtro_datas = df['data_processamento'].str.contains(
        f"{data_hoje_completa}|{data_hoje_curta}", regex=True, na=False
    )
    df_filtrado = df[filtro_datas].copy()

    if df_filtrado.empty:
        rotulo = f" [{horario_rotulo}]" if horario_rotulo else ""
        enviar_para_slack_nativo(f"📊 *Informe de ICs{rotulo} ({data_hoje_completa}):* Nenhum registro processado hoje no histórico.")
        return

    total_processos = len(df_filtrado)
    verdes, amarelos, vermelhos = [], [], []

    for _, linha in df_filtrado.iterrows():
        boba_id = linha.get('boba', 'N/A')
        status = linha.get('status', 'Sem status')
        link_drive = linha.get('link_drive', '')

        if link_drive and link_drive.startswith("http"):
            boba_formatado = f"<{link_drive}|*BOBA {boba_id}*>"
        else:
            boba_formatado = f"*BOBA {boba_id}*"

        item_str = f"• {boba_formatado} — _{status}_"
        status_lower = status.lower()

        if any(termo in status_lower for termo in ["podemos enviar", "validado", "aprovado", "ok"]):
            verdes.append(item_str)
        elif any(termo in status_lower for termo in ["necessita de validação", "validação manual", "revisão"]):
            amarelos.append(item_str)
        else:
            vermelhos.append(item_str)

    qtd_verdes, qtd_amarelos, qtd_vermelhos = len(verdes), len(amarelos), len(vermelhos)
    pct_v = (qtd_verdes / total_processos * 100) if total_processos > 0 else 0
    pct_a = (qtd_amarelos / total_processos * 100) if total_processos > 0 else 0
    pct_r = (qtd_vermelhos / total_processos * 100) if total_processos > 0 else 0

    header_rotulo = f" [{horario_rotulo}]" if horario_rotulo else ""
    msg = f"📋 *Informe de ICs{header_rotulo} — Auditados em {data_hoje_completa}*\n\n"

    msg += f"🟢 *Aprovados / Prontos para Envio ({qtd_verdes}):*\n"
    msg += ("\n".join(verdes) + "\n\n") if verdes else "└ _Nenhum item nesta categoria_\n\n"

    msg += f"🟡 *Necessitam de Validação Manual ({qtd_amarelos}):*\n"
    msg += ("\n".join(amarelos) + "\n\n") if amarelos else "└ _Nenhum item nesta categoria_\n\n"

    msg += f"🔴 *Solicitar Documentação / Reprovados ({qtd_vermelhos}):*\n"
    msg += ("\n".join(vermelhos) + "\n\n") if vermelhos else "└ _Nenhum item nesta categoria_\n\n"

    msg += "──────────────────────────────────────────\n"
    msg += "📊 *CÁLCULO E RESUMO CONSOLIDADO:* \n"
    msg += f"• 🟢 *Aprovados / Prontos para Envio:* `{qtd_verdes}` ({pct_v:.1f}%)\n"
    msg += f"• 🟡 *Necessitam de Validação Manual:* `{qtd_amarelos}` ({pct_a:.1f}%)\n"
    msg += f"• 🔴 *Solicitar Documentação / Reprovados:* `{qtd_vermelhos}` ({pct_r:.1f}%)\n"
    msg += f"📌 *TOTAL GERAL AUDITADO HOJE:* `{total_processos} BOBAs`\n"
    msg += "──────────────────────────────────────────\n"
    msg += "✨ _Relatório gerado automaticamente pela Dona Geralda._"

    enviar_para_slack_nativo(msg)
# ==========================================
# PROCESSAMENTO DE DRIVE E RENOMEAÇÃO IA
# ==========================================
def padronizar_arquivos_drive(id_pasta, arquivos_detalhes):
    """Identifica arquivos via IA e renomeia no Google Drive para os nomes padronizados"""
    renomeados = []
    
    for arq in arquivos_detalhes:
        nome_original = arq['name']
        file_id = arq['id']
        mime_type = arq['mimeType']
        
        # Pula se o arquivo já estiver com um nome padronizado
        if nome_original.lower() in MAPA_NOMES_CURTOS.values():
            continue

        # Baixa amostra para análise de classificação
        try:
            req = service_drive.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            prompt = (
                "Identifique qual é o documento presente na imagem/PDF. "
                "Responda EXATAMENTE com um dos seguintes rótulos:\n"
                "- CNH CONDUTOR\n- CNH PROCURADOR\n- DOCUMENTO PROPRIETÁRIO\n"
                "- DOCUMENTO PROCURADOR\n- CNH PROPRIETÁRIO\n- CONTRATO SOCIAL\n"
                "- CONTRATO DE LOCAÇÃO\n- PROCURAÇÃO\n- TERMO DE RESPONSABILIDADE\n"
                "Se não for nenhum desses, responda 'DESCONHECIDO'."
            )
            
            conteudo = [prompt, types.Part.from_bytes(data=fh.getvalue(), mime_type=mime_type)]
            res = client_pago.models.generate_content(model='gemini-2.5-flash', contents=conteudo)
            rotulo = res.text.strip().upper()

            if rotulo in MAPA_NOMES_CURTOS:
                novo_nome = MAPA_NOMES_CURTOS[rotulo]
                if nome_original.lower() != novo_nome:
                    service_drive.files().update(fileId=file_id, body={'name': novo_nome}).execute()
                    renomeados.append(f"`{nome_original}` ➔ `{novo_nome}`")
        except Exception as e:
            print(f"⚠️ Erro ao renomear {nome_original}: {e}")

    return renomeados

def analisar_veredicto_ia_paga(arquivos_baixados):
    if not arquivos_baixados or not client_pago:
        return {
            "condutor_nome": "N/A", "condutor_cnh": "N/A",
            "proprietario_nome": "N/A", "proprietario_cnh": "N/A",
            "orgao": "N/A", "status": "solicitar documentação: Formulário não encontrado",
            "observacao": "Formulário não anexado na pasta."
        }

    prompt = (
        "Você é um auditor sênior de processos de indicação de condutor.\n"
        "Examine os documentos anexados na pasta do cliente e retorne APENAS um JSON puro:\n"
        "{\n"
        '  "condutor_nome": "Nome ou N/A",\n'
        '  "condutor_cnh": "Número ou N/A",\n'
        '  "proprietario_nome": "Nome ou N/A",\n'
        '  "proprietario_cnh": "Número ou N/A",\n'
        '  "orgao": "Órgão Autuador ou N/A",\n'
        '  "status": "podemos enviar para o órgão OU necessita de validação manual OU solicitar documentação: [Motivo]",\n'
        '  "observacao": "Resumo da auditoria"\n'
        "}"
    )
    conteudo = [prompt]
    for arq in arquivos_baixados:
        conteudo.append(types.Part.from_bytes(data=arq['data'], mime_type=arq['mime']))

    try:
        response = client_pago.models.generate_content(
            model='gemini-2.5-flash',
            contents=conteudo
        )
        texto = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(texto)
    except Exception as e:
        print(f"⚠️ Erro na IA Gemini: {e}")
        return {
            "condutor_nome": "N/A", "condutor_cnh": "N/A",
            "proprietario_nome": "N/A", "proprietario_cnh": "N/A",
            "orgao": "N/A", "status": "necessita de validação manual",
            "observacao": "Análise manual recomendada."
        }

def rodar_automacao(origem="Varredura Sob Demanda"):
    global varredura_em_andamento
    if varredura_em_andamento or not service_drive:
        return

    varredura_em_andamento = True
    print(f"\n🚀 [{origem}] Iniciando Varredura no Google Drive...")

    try:
        df_historico = carregar_historico()
        pastas, page_token = [], None

        while True:
            query = f"'{ID_PASTA_RAIZ}' in parents and mimeType = 'application/vnd.google-apps.folder'"
            results = service_drive.files().list(
                q=query, fields="nextPageToken, files(id, name, webViewLink)",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
                pageSize=100, pageToken=page_token
            ).execute()
            pastas.extend(results.get('files', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        novas_pastas = []
        for pasta in pastas:
            nome_p = pasta['name']
            if "BOBA" not in nome_p.upper() and "[IDC]" not in nome_p.upper():
                continue
            boba_id, _, _, _ = extrair_dados_do_nome(nome_p)
            if not df_historico.empty:
                linha_boba = df_historico[df_historico['boba'] == boba_id]
                if not linha_boba.empty and str(linha_boba.iloc[0].get('status', '')).strip() != "":
                    continue
            novas_pastas.append(pasta)

        if not novas_pastas:
            enviar_para_slack_nativo("👍 *Varredura concluída!* Nenhuma pasta nova no Google Drive.")
            return

        enviar_para_slack_nativo(f"🔔 Encontradas *{len(novas_pastas)} nova(s) pasta(s)* no Google Drive! Padronizando arquivos e auditando... 📑⚡")

        for pasta in novas_pastas:
            nome_p, id_pasta, link_drive = pasta['name'], pasta['id'], pasta.get('webViewLink', '')
            boba_id, cliente_limpo, ait_extraido, placa_extraida = extrair_dados_do_nome(nome_p)

            # 1. Busca detalhes dos arquivos da pasta
            res_arqs = service_drive.files().list(
                q=f"'{id_pasta}' in parents", fields="files(id, name, mimeType)",
                supportsAllDrives=True, includeItemsFromAllDrives=True
            ).execute()
            arqs_detalhes = [a for a in res_arqs.get('files', []) if a['name'].lower().endswith('.pdf') or 'image' in a['mimeType']]

            # 2. Renomeia e padroniza arquivos no Drive via IA
            arquivos_renomeados = padronizar_arquivos_drive(id_pasta, arqs_detalhes)

            # 3. Baixa os arquivos atualizados para Auditoria
            arquivos_baixados = []
            try:
                for arq in arqs_detalhes:
                    if 'vnd.google-apps' in arq['mimeType']:
                        continue
                    req = service_drive.files().get_media(fileId=arq['id'])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, req)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()
                    arquivos_baixados.append({'mime': 'application/pdf' if arq['name'].lower().endswith('.pdf') else arq['mimeType'], 'data': fh.getvalue()})
            except Exception as e:
                print(f"⚠️ Erro no download: {e}")

            # 4. Análise de veredicto
            dados_ia = analisar_veredicto_ia_paga(arquivos_baixados)
            status_veredito = dados_ia.get('status', 'necessita de validação manual')

            salvar_no_historico({
                'boba': boba_id, 'cliente': cliente_limpo,
                'status': f"{status_veredito} (IA)" if "podemos enviar" in status_veredito.lower() else status_veredito,
                'data_processamento': datetime.now().strftime("%d/%m/%Y"),
                'placa': placa_extraida, 'condutor': dados_ia.get('condutor_nome', 'N/A'),
                'proprietario': dados_ia.get('proprietario_nome', 'N/A'),
                'cnh_condutor': dados_ia.get('condutor_cnh', 'N/A'),
                'cnh_proprietario': dados_ia.get('proprietario_cnh', 'N/A'),
                'ait': ait_extraido, 'orgao': dados_ia.get('orgao', 'N/A'),
                'link_drive': link_drive
            })

            mencao_resp = buscar_mencao_responsavel(nome_p, dados_ia.get('orgao', ''))
            emoji = "🟢" if "podemos enviar" in status_veredito.lower() else "🟡" if "validação" in status_veredito.lower() else "🔴"
            link_txt = f"<{link_drive}|*BOBA {boba_id}*>" if link_drive else f"*BOBA {boba_id}*"
            
            msg_obs_renomeado = f"\n🔄 *Arquivos Padronizados:* {', '.join(arquivos_renomeados)}" if arquivos_renomeados else ""
            
            enviar_para_slack_nativo(
                f"{emoji} {link_txt} | *Cliente:* {cliente_limpo} | *Placa:* {placa_extraida}\n"
                f"📢 *Veredicto:* `{status_veredito}` | 🎯 *Responsável:* {mencao_resp}{msg_obs_renomeado}"
            )

    except Exception as e:
        print(f"⚠️ Erro na varredura: {e}")
    finally:
        varredura_em_andamento = False

# ==========================================
# ESCUTA DE EVENTOS DO SLACK
# ==========================================
if slack_app:
    @slack_app.event("app_mention")
    def tratar_mencao_dona_geralda(event, say):
        texto_msg = event.get('text', '')
        usuario = event.get('user', 'Usuário')

        # 1. Comando: "Dona Geralda rodar nova rodada"
        if "rodar nova rodada" in texto_msg.lower():
            say(f"🚀 Perfeito <@{usuario}>! Iniciando uma nova verificação de pastas no Google Drive agora...")
            threading.Thread(target=rodar_automacao, kwargs={"origem": f"Iniciada por <@{usuario}>"}).start()
            return

        # 2. Comando: Mapeamento de Órgão (@Dona Geralda orgao PRF = @Tamires)
        match_orgao = re.search(r'orgao\s+(.*?)\s*=\s*<@([A-Z0-9]+)>', texto_msg, re.IGNORECASE)
        if match_orgao:
            orgao_nome = match_orgao.group(1).strip()
            target_user_id = match_orgao.group(2).strip()
            sucesso = atualizar_ou_inserir_responsavel(orgao_nome, target_user_id)
            if sucesso:
                say(f"✅ Órgão *{orgao_nome}* vinculado com sucesso a <@{target_user_id}> no `responsaveis.csv`!")
            else:
                say(f"⚠️ Houve uma falha ao tentar atualizar o arquivo `responsaveis.csv`.")
            return

        # 3. Comando: Atualização de BOBA (@Dona Geralda BOBA 14200 aprovado)
        match_boba = re.search(r'BOBA\s*(\d+)', texto_msg, re.IGNORECASE)
        if match_boba:
            boba_id = match_boba.group(1)
            texto_lower = texto_msg.lower()

            if any(w in texto_lower for w in ["aprovado", "aprovar", "validado", "ok"]):
                novo_status = f"Validado Manualmente (por @{usuario})"
                emoji = "✅"
            elif any(w in texto_lower for w in ["reprovado", "reprovar", "solicitar"]):
                novo_status = f"Solicitar Documentação (por @{usuario})"
                emoji = "🔴"
            else:
                novo_status = f"Atualizado Manualmente (por @{usuario})"
                emoji = "📝"

            sucesso = atualizar_status_boba_no_csv(boba_id, novo_status)
            if sucesso:
                say(f"{emoji} *BOBA {boba_id}* atualizado com sucesso no histórico para: `{novo_status}`!")
            else:
                say(f"⚠️ Não encontrei o *BOBA {boba_id}* no arquivo de histórico para atualizar.")
            return

        # Se não casou com nenhum comando específico, envia ajuda
        enviar_instrucoes_comandos_slack()

# ==========================================
# AGENDADORES E INICIALIZAÇÃO
# ==========================================
def agendador_horarios_relatorio():
    global relatorios_disparados_hoje, Avisos_comandos_disparados_hoje
    data_atual_trava = datetime.now().strftime("%d/%m/%Y")

    while True:
        try:
            agora = datetime.now()
            hora_str = agora.strftime("%H:%M")
            data_str = agora.strftime("%d/%m/%Y")

            if data_str != data_atual_trava:
                relatorios_disparados_hoje.clear()
                Avisos_comandos_disparados_hoje.clear()
                data_atual_trava = data_str

            # Relatórios automáticos
            horarios_alvo = ["10:00", "12:00", "15:00"]
            for h in horarios_alvo:
                chave_trava = f"{data_str}_{h}"
                if hora_str == h and chave_trava not in relatorios_disparados_hoje:
                    gerar_e_enviar_informe_hoje(horario_rotulo=h)
                    relatorios_disparados_hoje.add(chave_trava)

            # Instruções dos Comandos às 12:00 diariamente
            chave_aviso = f"{data_str}_1200"
            if hora_str == "12:00" and chave_aviso not in Avisos_comandos_disparados_hoje:
                enviar_instrucoes_comandos_slack()
                Avisos_comandos_disparados_hoje.add(chave_aviso)

            time.sleep(20)
        except Exception as e:
            print(f"⚠️ Erro no agendador de horários: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("🤖 Iniciando Dona Geralda em Modo Autônomo com Escuta do Slack...")

    # 1. Sincroniza órgãos sem dono ao iniciar
    sincronizar_orgaos_historico_sem_dono()

    # 2. Inicia agendador de relatórios e mensagens em segundo plano
    threading.Thread(target=agendador_horarios_relatorio, daemon=True).start()

    # 3. Manda instruções no Slack na primeira execução
    enviar_instrucoes_comandos_slack()

    # 4. Escuta via Socket Mode
    if SLACK_BOT_TOKEN and SLACK_APP_TOKEN and slack_app:
        try:
            handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
            print("⚡ Escuta de menções (@Dona Geralda) ativada com sucesso!")
            handler.start()
        except Exception as e_slack:
            print(f"⚠️ Erro ao iniciar Socket Mode: {e_slack}")
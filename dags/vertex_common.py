"""
==============================================================================
VERTEX - Funções compartilhadas do pipeline (Arquitetura Lambda)
Challenge Oracle & FIAP 2026 - 1TSCPF/1TSCPV/1TSCPW

Correções aplicadas após feedback da Sprint 3 (nota 96 - Modern Data
Architecture & Engineering):
  1) Speed Layer agora vive em uma DAG própria (pipeline_vertex_speed),
     com schedule_interval diário — independente da DAG mensal do Batch
     Layer. Antes, as duas camadas rodavam na mesma DAG/schedule mensal,
     o que não caracterizava um fluxo de baixa latência de verdade.
  2) A camada Serving agora é de fato carregada no Oracle Autonomous AI
     Database (VERTEX_DB) pelo próprio pipeline, via carregar_no_oracle()
     (python-oracledb). Antes, a "carga analítica" só gravava CSV local.
==============================================================================
"""

import os
import pandas as pd

# ==========================================
# CONFIGURAÇÃO DE CAMINHOS
# ==========================================
RAW_DIR = "/tmp/vertex/raw"
TRUSTED_DIR = "/tmp/vertex/trusted"
SERVING_DIR = "/tmp/vertex/serving"  # cópia local de apoio/depuração — a fonte de verdade passa a ser o Oracle
SOURCE_DIR = "/opt/airflow/data"


# ==========================================
# CARGA REAL NO ORACLE (VERTEX_DB)
# ==========================================
def carregar_no_oracle(df: pd.DataFrame, table_name: str):
    """
    Carrega um DataFrame para uma tabela já existente no Oracle Autonomous
    AI Database VERTEX_DB (schema criado pela disciplina Smart SQL &
    Relational Databases / Data Architecture, Analytics & NoSQL Solutions).

    Credenciais lidas de variáveis de ambiente (nunca hardcoded):
      - ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN (easy connect ou alias do wallet)
      - TNS_ADMIN apontando para a pasta do wallet descompactado, se aplicável

    Estratégia: DELETE + INSERT (recarga completa da tabela a cada execução,
    já que os indicadores são recalculados do zero em cada run). Se as
    variáveis de ambiente não estiverem configuradas, o pipeline não quebra:
    registra um aviso e mantém apenas a cópia local em SERVING_DIR — isso
    permite testar a lógica sem depender do Oracle estar acessível.
    """
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    dsn = os.environ.get("ORACLE_DSN")

    if not all([user, password, dsn]):
        print(
            f"  [Oracle] ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN não configurados — "
            f"carga em {table_name} pulada (dado ficou disponível apenas em {SERVING_DIR})."
        )
        return

    try:
        import oracledb
    except ImportError:
        print("  [Oracle] Pacote 'oracledb' não instalado. Rode: pip install oracledb")
        return

    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table_name}")
                cols = list(df.columns)
                placeholders = ", ".join(f":{i + 1}" for i in range(len(cols)))
                insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
                rows = [tuple(r) for r in df[cols].itertuples(index=False, name=None)]
                cur.executemany(insert_sql, rows)
            conn.commit()
        print(f"  [Oracle] Carga real concluída: {len(df)} linhas em {table_name}.")
    except Exception as e:
        print(f"  [Oracle] ERRO ao carregar {table_name}: {e}")
        raise


# ==========================================
# INGESTÃO (Camada Raw)
# ==========================================
def _ingerir(nome, nome_arquivo, read_kwargs=None):
    read_kwargs = read_kwargs or {}
    origem = os.path.join(SOURCE_DIR, nome_arquivo)
    destino = os.path.join(RAW_DIR, nome_arquivo)
    df = pd.read_csv(origem, **read_kwargs)
    df.to_csv(destino, index=False)
    print(f"  -> {nome}: {len(df)} registros ingeridos ({nome_arquivo})")


def ingestao_sia():
    """
    Ingestão da Batch Layer: produção ambulatorial do SIA/SUS e população
    do IBGE, atualizadas em ciclo mensal/anual. Roda na DAG
    pipeline_vertex_batch (schedule_interval="@monthly").
    """
    print("Iniciando Ingestão SIA/SUS + IBGE (Camada Raw - Batch Layer)...")
    os.makedirs(RAW_DIR, exist_ok=True)
    _ingerir(
        "sia",
        "sia_cnv_qasp113702191_243_242_4.csv",
        dict(sep=";", skiprows=3, encoding="latin1", engine="python"),
    )
    _ingerir("ibge_populacao", "ibge_populacao_sp.csv")
    print("Ingestão Batch Layer concluída com sucesso.")


def ingestao_cnes():
    """
    Ingestão da Speed Layer: capacidade instalada (CNES-ST) e recursos
    humanos (CNES-PF). Roda em DAG própria, pipeline_vertex_speed
    (schedule_interval="@daily") — cadência independente e mais frequente
    que o Batch Layer, refletindo o requisito de baixa latência da
    Arquitetura Lambda.
    """
    print("Iniciando Ingestão CNES-ST/PF (Camada Raw - Speed Layer)...")
    os.makedirs(RAW_DIR, exist_ok=True)
    _ingerir("cnes_estabelecimento", "cnes_estabelecimento_sp.csv")
    _ingerir("cnes_profissional", "cnes_profissional_sp_agg.csv")
    print("Ingestão Speed Layer concluída com sucesso.")


# ==========================================
# TRANSFORMAÇÃO (Camada Trusted) — dividida por camada da Lambda
# ==========================================
def transformar_sia_ibge():
    """Transformação da Batch Layer: SIA/SUS + IBGE, padronização por código IBGE de 6 dígitos."""
    print("Iniciando Transformação SIA/IBGE (Batch Layer - Camada Trusted)...")
    os.makedirs(TRUSTED_DIR, exist_ok=True)

    ibge = pd.read_csv(os.path.join(RAW_DIR, "ibge_populacao_sp.csv"))
    ibge["codigo_6d"] = ibge["id_municipio"] // 10
    nulos_ibge = ibge["populacao"].isnull().sum()
    print(f"  Validação IBGE: {nulos_ibge} valores nulos em população.")
    ibge.to_csv(os.path.join(TRUSTED_DIR, "ibge_trusted.csv"), index=False)

    sia = pd.read_csv(os.path.join(RAW_DIR, "sia_cnv_qasp113702191_243_242_4.csv"))
    linhas_antes = len(sia)
    sia = sia[sia["Município"] != "Total"].dropna(subset=["Qtd.aprovada"])
    print(f"  Validação SIA: removidas {linhas_antes - len(sia)} linhas (rodapé/total/nulos).")

    sia["codigo_6d"] = sia["Município"].str.extract(r"^(\d+)").astype(int)
    sia["nome_municipio"] = sia["Município"].str.extract(r"^\d+\s+(.*)$")
    sia = sia.merge(ibge[["id_municipio", "codigo_6d"]].drop_duplicates(), on="codigo_6d", how="left")
    sem_match = sia["id_municipio"].isnull().sum()
    print(f"  Municípios SIA sem correspondência no IBGE: {sem_match} de {len(sia)}.")

    sia = sia.rename(columns={"Qtd.aprovada": "qtd_atendimentos_periodo"})[
        ["id_municipio", "nome_municipio", "qtd_atendimentos_periodo"]
    ]
    sia.to_csv(os.path.join(TRUSTED_DIR, "sia_trusted.csv"), index=False)
    print(f"  SIA tratado: {len(sia)} municípios padronizados.")
    print("Transformação Batch Layer concluída.")


def transformar_cnes():
    """Transformação da Speed Layer: agregação de leitos e profissionais do CNES por município/ano."""
    print("Iniciando Transformação CNES (Speed Layer - Camada Trusted)...")
    os.makedirs(TRUSTED_DIR, exist_ok=True)

    cnes_est = pd.read_csv(os.path.join(RAW_DIR, "cnes_estabelecimento_sp.csv"))
    cnes_est["total_leitos"] = (
        cnes_est["quantidade_leito_cirurgico"]
        + cnes_est["quantidade_leito_clinico"]
        + cnes_est["quantidade_leito_complementar"]
    )
    agg_estab = cnes_est.groupby(["id_municipio", "ano"]).agg(
        qtd_estabelecimentos=("id_estabelecimento_cnes", "nunique"),
        total_leitos=("total_leitos", "sum"),
    ).reset_index()
    agg_estab.to_csv(os.path.join(TRUSTED_DIR, "cnes_estabelecimento_trusted.csv"), index=False)
    print(f"  CNES-ST agregado: {len(agg_estab)} combinações município/ano.")

    cnes_prof = pd.read_csv(os.path.join(RAW_DIR, "cnes_profissional_sp_agg.csv"))
    agg_prof = cnes_prof.groupby(["id_municipio", "ano"]).agg(
        qtd_profissionais=("quantidade_profissionais", "sum")
    ).reset_index()
    agg_prof.to_csv(os.path.join(TRUSTED_DIR, "cnes_profissional_trusted.csv"), index=False)
    print(f"  CNES-PF agregado: {len(agg_prof)} combinações município/ano.")
    print("Transformação Speed Layer concluída.")


# ==========================================
# CARGA ANALÍTICA (Camada Serving) — agora com carga real no Oracle
# ==========================================
def carga_analitica():
    """
    Junção das fontes tratadas (produzidas pelas duas camadas da Lambda) e
    cálculo dos indicadores per capita (EPC, PPC, APC). Roda no Batch DAG,
    após a Speed Layer ter atualizado o CNES de forma independente.
    Carrega o resultado nas tabelas SERVING_INDICADORES_ANUAIS e
    SERVING_INDICADOR_APC do Oracle Autonomous AI Database (VERTEX_DB) —
    ver DDL em sql/ddl_serving_tables.sql.
    """
    print("Iniciando Carga Analítica (Camada Serving)...")
    os.makedirs(SERVING_DIR, exist_ok=True)

    ibge = pd.read_csv(os.path.join(TRUSTED_DIR, "ibge_trusted.csv"))
    agg_estab = pd.read_csv(os.path.join(TRUSTED_DIR, "cnes_estabelecimento_trusted.csv"))
    agg_prof = pd.read_csv(os.path.join(TRUSTED_DIR, "cnes_profissional_trusted.csv"))
    sia = pd.read_csv(os.path.join(TRUSTED_DIR, "sia_trusted.csv"))

    serving_anual = (
        agg_estab.merge(agg_prof, on=["id_municipio", "ano"], how="outer")
        .merge(ibge[["id_municipio", "ano", "populacao"]], on=["id_municipio", "ano"], how="left")
    )
    serving_anual["EPC"] = (serving_anual["qtd_estabelecimentos"] / serving_anual["populacao"]) * 1000
    serving_anual["PPC"] = (serving_anual["qtd_profissionais"] / serving_anual["populacao"]) * 1000
    serving_anual.to_csv(os.path.join(SERVING_DIR, "indicadores_anuais_epc_ppc.csv"), index=False)
    print(f"  Indicadores anuais (EPC/PPC) calculados: {len(serving_anual)} linhas.")
    carregar_no_oracle(serving_anual, "SERVING_INDICADORES_ANUAIS")

    pop_recente = ibge[ibge["ano"] == ibge["ano"].max()][["id_municipio", "populacao"]]
    serving_sia = sia.merge(pop_recente, on="id_municipio", how="left")
    serving_sia["APC"] = serving_sia["qtd_atendimentos_periodo"] / serving_sia["populacao"]
    serving_sia.to_csv(os.path.join(SERVING_DIR, "indicador_periodo_apc.csv"), index=False)
    print(f"  Indicador de período (APC) calculado: {len(serving_sia)} municípios.")
    carregar_no_oracle(serving_sia, "SERVING_INDICADOR_APC")

    print("Carga concluída (local + Oracle). Dados prontos para o Dashboard VERTEX.")


# ==========================================
# ÍNDICE FINAL DE SUBUTILIZAÇÃO (Camada Serving) — carga real no Oracle
# ==========================================
def calcular_indice_subutilizacao():
    """
    Combina EPC, PPC e APC em um único índice de subutilização/abandono
    indireto por município. Usa normalização min-max — a MESMA fórmula
    já em produção no Dashboard VERTEX (Oracle APEX) e nas consultas
    Select AI da Mariana, carregada na tabela INDICE_SUBUTILIZACAO_VERTEX.

    (Nota: entre 08-09/09 avaliamos migrar para uma fórmula alternativa
    baseada em razão, definida em paralelo por outro membro do grupo —
    decidimos NÃO migrar: o dashboard e o Select AI já estavam públicos
    e funcionando sobre este formato, e trocar o schema a 4 dias da
    entrega era risco desnecessário. A análise alternativa foi
    incorporada como validação complementar de qualidade de dados, não
    como substituição — ver README do repositório.)

    Município com índice ALTO = capacidade instalada (EPC/PPC) alta
    frente a um uso proporcionalmente baixo (APC) -> maior indício de
    abandono/subutilização.
    """
    print("Iniciando cálculo do Índice Final de Subutilização (Camada Serving)...")

    anual = pd.read_csv(os.path.join(SERVING_DIR, "indicadores_anuais_epc_ppc.csv"))
    apc = pd.read_csv(os.path.join(SERVING_DIR, "indicador_periodo_apc.csv"))

    ultimo_ano = anual.groupby("id_municipio")["ano"].transform("max")
    recente = anual[anual["ano"] == ultimo_ano]

    df = apc.merge(recente[["id_municipio", "EPC", "PPC"]], on="id_municipio", how="left")
    df = df.dropna(subset=["EPC", "PPC", "APC"])

    for col in ["EPC", "PPC", "APC"]:
        df[f"{col}_norm"] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())

    df["capacidade_norm"] = (df["EPC_norm"] + df["PPC_norm"]) / 2
    df["indice_subutilizacao"] = df["capacidade_norm"] - df["APC_norm"]
    df = df.sort_values("indice_subutilizacao", ascending=False)

    df.to_csv(os.path.join(SERVING_DIR, "indice_subutilizacao_vertex.csv"), index=False)
    print(f"  Índice final calculado para {len(df)} municípios.")
    print("  Top 5 municípios com maior indício de subutilização:")
    print(df[["nome_municipio", "indice_subutilizacao"]].head(5).to_string(index=False))

    carregar_no_oracle(
        df[["id_municipio", "nome_municipio", "EPC", "PPC", "APC",
            "EPC_norm", "PPC_norm", "APC_norm", "capacidade_norm", "indice_subutilizacao"]],
        "INDICE_SUBUTILIZACAO_VERTEX",
    )
    print("Cálculo do índice final concluído. Pronto para consumo pelo Dashboard VERTEX (APEX).")

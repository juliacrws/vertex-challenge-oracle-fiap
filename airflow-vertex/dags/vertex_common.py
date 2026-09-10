"""
==============================================================================
VERTEX - Funções compartilhadas do pipeline (Arquitetura Lambda)
Challenge Oracle & FIAP 2026 - 1TSCPF/1TSCPV/1TSCPW
 
Pipeline VERTEX:
  - Speed Layer: CNES, executada diariamente
  - Batch Layer: SIA/SUS + IBGE, executada mensalmente
  - Serving Layer: indicadores EPC, PPC, APC e índice de subutilização
  - Persistência real no Oracle Autonomous AI Database (VERTEX_DB)
==============================================================================
"""
 
import os
import pandas as pd
 
 
# ==========================================
# CONFIGURAÇÃO DE CAMINHOS
# ==========================================
RAW_DIR = "/tmp/vertex/raw"
TRUSTED_DIR = "/tmp/vertex/trusted"
SERVING_DIR = "/tmp/vertex/serving"
SOURCE_DIR = "/opt/airflow/data"
 
 
# ==========================================
# CARGA REAL NO ORACLE (VERTEX_DB)
# ==========================================
def carregar_no_oracle(df: pd.DataFrame, table_name: str):
    """
    Carrega um DataFrame em uma tabela já existente no Oracle
    Autonomous AI Database VERTEX_DB.
 
    Variáveis de ambiente utilizadas:
      - ORACLE_USER
      - ORACLE_PASSWORD
      - ORACLE_DSN
      - TNS_ADMIN
      - WALLET_PASSWORD
 
    Estratégia:
      - conexão mTLS usando Oracle Wallet
      - Parallel DML desabilitado para evitar ORA-12860
      - DELETE + INSERT dentro da mesma transação
      - COMMIT somente após a carga terminar com sucesso
      - ROLLBACK automático se ocorrer erro
    """
 
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    dsn = os.environ.get("ORACLE_DSN")
    tns_admin = os.environ.get(
        "TNS_ADMIN",
        "/opt/airflow/wallet"
    )
    wallet_password = os.environ.get(
        "WALLET_PASSWORD"
    )
 
    if not all([user, password, dsn]):
        raise RuntimeError(
            "ORACLE_USER, ORACLE_PASSWORD ou "
            "ORACLE_DSN não configurados."
        )
 
    if not wallet_password:
        raise RuntimeError(
            "WALLET_PASSWORD não configurado "
            "no ambiente do Airflow."
        )
 
    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError(
            "Pacote 'oracledb' não instalado."
        ) from exc
 
    conn = None
 
    try:
        conn = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
            config_dir=tns_admin,
            wallet_location=tns_admin,
            wallet_password=wallet_password,
        )
 
        with conn.cursor() as cur:
 
            # Evita ORA-12860:
            # força operações DML da sessão a serem seriais.
            cur.execute(
                "ALTER SESSION DISABLE PARALLEL DML"
            )
 
            print(
                f"  [Oracle] Iniciando carga em "
                f"{table_name}..."
            )
 
            # Recarga completa da tabela.
            cur.execute(
                f"DELETE FROM {table_name}"
            )
 
            cols = list(df.columns)
 
            placeholders = ", ".join(
                f":{i + 1}"
                for i in range(len(cols))
            )
 
            insert_sql = (
                f"INSERT INTO {table_name} "
                f"({', '.join(cols)}) "
                f"VALUES ({placeholders})"
            )
 
            rows = [
                tuple(row)
                for row in df[cols].itertuples(
                    index=False,
                    name=None
                )
            ]
 
            if rows:
                cur.executemany(
                    insert_sql,
                    rows
                )
 
        # Commit apenas quando DELETE + INSERT
        # terminarem corretamente.
        conn.commit()
 
        print(
            f"  [Oracle] Carga real concluída: "
            f"{len(df)} linhas em {table_name}."
        )
 
    except Exception as e:
 
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
 
        print(
            f"  [Oracle] ERRO ao carregar "
            f"{table_name}: {e}"
        )
 
        raise
 
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
 
 
# ==========================================
# INGESTÃO GENÉRICA
# ==========================================
def _ingerir(
    nome,
    nome_arquivo,
    read_kwargs=None
):
    read_kwargs = read_kwargs or {}
 
    origem = os.path.join(
        SOURCE_DIR,
        nome_arquivo
    )
 
    destino = os.path.join(
        RAW_DIR,
        nome_arquivo
    )
 
    df = pd.read_csv(
        origem,
        **read_kwargs
    )
 
    df.to_csv(
        destino,
        index=False
    )
 
    print(
        f"  -> {nome}: "
        f"{len(df)} registros ingeridos "
        f"({nome_arquivo})"
    )
 
 
# ==========================================
# INGESTÃO BATCH - SIA/SUS + IBGE
# ==========================================
def ingestao_sia():
    """
    Ingestão da Batch Layer:
    produção ambulatorial do SIA/SUS
    e população do IBGE.
    """
 
    print(
        "Iniciando Ingestão SIA/SUS + IBGE "
        "(Camada Raw - Batch Layer)..."
    )
 
    os.makedirs(
        RAW_DIR,
        exist_ok=True
    )
 
    _ingerir(
        "sia",
        "sia_cnv_qasp113702191_243_242_4.csv",
        dict(
            sep=";",
            skiprows=3,
            encoding="latin1",
            engine="python",
        ),
    )
 
    _ingerir(
        "ibge_populacao",
        "ibge_populacao_sp.csv",
    )
 
    print(
        "Ingestão Batch Layer "
        "concluída com sucesso."
    )
 
 
# ==========================================
# INGESTÃO SPEED - CNES
# ==========================================
def ingestao_cnes():
    """
    Ingestão da Speed Layer:
    CNES de estabelecimentos e profissionais.
    """
 
    print(
        "Iniciando Ingestão CNES-ST/PF "
        "(Camada Raw - Speed Layer)..."
    )
 
    os.makedirs(
        RAW_DIR,
        exist_ok=True
    )
 
    _ingerir(
        "cnes_estabelecimento",
        "cnes_estabelecimento_sp.csv",
    )
 
    _ingerir(
        "cnes_profissional",
        "cnes_profissional_sp_agg.csv",
    )
 
    print(
        "Ingestão Speed Layer "
        "concluída com sucesso."
    )
 
 
# ==========================================
# TRANSFORMAÇÃO BATCH
# ==========================================
def transformar_sia_ibge():
    """
    Transformação da Batch Layer:
    padronização dos dados SIA/SUS e IBGE
    por código do município.
    """
 
    print(
        "Iniciando Transformação SIA/IBGE "
        "(Batch Layer - Camada Trusted)..."
    )
 
    os.makedirs(
        TRUSTED_DIR,
        exist_ok=True
    )
 
    # -------------------------------
    # IBGE
    # -------------------------------
    ibge = pd.read_csv(
        os.path.join(
            RAW_DIR,
            "ibge_populacao_sp.csv",
        )
    )
 
    ibge["codigo_6d"] = (
        ibge["id_municipio"] // 10
    )
 
    nulos_ibge = (
        ibge["populacao"]
        .isnull()
        .sum()
    )
 
    print(
        f"  Validação IBGE: "
        f"{nulos_ibge} valores nulos "
        f"em população."
    )
 
    ibge.to_csv(
        os.path.join(
            TRUSTED_DIR,
            "ibge_trusted.csv",
        ),
        index=False,
    )
 
    # -------------------------------
    # SIA/SUS
    # -------------------------------
    sia = pd.read_csv(
        os.path.join(
            RAW_DIR,
            "sia_cnv_qasp113702191_243_242_4.csv",
        )
    )
 
    linhas_antes = len(sia)
 
    sia = (
        sia[
            sia["Município"] != "Total"
        ]
        .dropna(
            subset=[
                "Qtd.aprovada"
            ]
        )
    )
 
    removidas = (
        linhas_antes - len(sia)
    )
 
    print(
        f"  Validação SIA: "
        f"removidas {removidas} linhas "
        f"(total/nulos)."
    )
 
    sia["codigo_6d"] = (
        sia["Município"]
        .str.extract(r"^(\d+)")
        .astype(int)
    )
 
    sia["nome_municipio"] = (
        sia["Município"]
        .str.extract(
            r"^\d+\s+(.*)$"
        )
    )
 
    sia = sia.merge(
        ibge[
            [
                "id_municipio",
                "codigo_6d",
            ]
        ].drop_duplicates(),
        on="codigo_6d",
        how="left",
    )
 
    sem_match = (
        sia["id_municipio"]
        .isnull()
        .sum()
    )
 
    print(
        f"  Municípios SIA sem "
        f"correspondência no IBGE: "
        f"{sem_match} de {len(sia)}."
    )
 
    sia = sia.rename(
        columns={
            "Qtd.aprovada":
            "qtd_atendimentos_periodo"
        }
    )[
        [
            "id_municipio",
            "nome_municipio",
            "qtd_atendimentos_periodo",
        ]
    ]
 
    sia.to_csv(
        os.path.join(
            TRUSTED_DIR,
            "sia_trusted.csv",
        ),
        index=False,
    )
 
    print(
        f"  SIA tratado: "
        f"{len(sia)} municípios."
    )
 
    print(
        "Transformação Batch Layer "
        "concluída."
    )
 
 
# ==========================================
# TRANSFORMAÇÃO SPEED
# ==========================================
def transformar_cnes():
    """
    Transformação da Speed Layer:
    agregação de estabelecimentos,
    leitos e profissionais por município/ano.
    """
 
    print(
        "Iniciando Transformação CNES "
        "(Speed Layer - Camada Trusted)..."
    )
 
    os.makedirs(
        TRUSTED_DIR,
        exist_ok=True
    )
 
    # -------------------------------
    # ESTABELECIMENTOS
    # -------------------------------
    cnes_est = pd.read_csv(
        os.path.join(
            RAW_DIR,
            "cnes_estabelecimento_sp.csv",
        )
    )
 
    cnes_est["total_leitos"] = (
        cnes_est[
            "quantidade_leito_cirurgico"
        ]
        + cnes_est[
            "quantidade_leito_clinico"
        ]
        + cnes_est[
            "quantidade_leito_complementar"
        ]
    )
 
    agg_estab = (
        cnes_est
        .groupby(
            [
                "id_municipio",
                "ano",
            ]
        )
        .agg(
            qtd_estabelecimentos=(
                "id_estabelecimento_cnes",
                "nunique",
            ),
            total_leitos=(
                "total_leitos",
                "sum",
            ),
        )
        .reset_index()
    )
 
    agg_estab.to_csv(
        os.path.join(
            TRUSTED_DIR,
            "cnes_estabelecimento_trusted.csv",
        ),
        index=False,
    )
 
    print(
        f"  CNES-ST agregado: "
        f"{len(agg_estab)} combinações "
        f"município/ano."
    )
 
    # -------------------------------
    # PROFISSIONAIS
    # -------------------------------
    cnes_prof = pd.read_csv(
        os.path.join(
            RAW_DIR,
            "cnes_profissional_sp_agg.csv",
        )
    )
 
    agg_prof = (
        cnes_prof
        .groupby(
            [
                "id_municipio",
                "ano",
            ]
        )
        .agg(
            qtd_profissionais=(
                "quantidade_profissionais",
                "sum",
            )
        )
        .reset_index()
    )
 
    agg_prof.to_csv(
        os.path.join(
            TRUSTED_DIR,
            "cnes_profissional_trusted.csv",
        ),
        index=False,
    )
 
    print(
        f"  CNES-PF agregado: "
        f"{len(agg_prof)} combinações "
        f"município/ano."
    )
 
    print(
        "Transformação Speed Layer "
        "concluída."
    )
 
 
# ==========================================
# CARGA ANALÍTICA - SERVING
# ==========================================
def carga_analitica():
    """
    Consolida CNES, IBGE e SIA/SUS.
 
    Calcula:
      EPC = estabelecimentos por 1.000 habitantes
      PPC = profissionais por 1.000 habitantes
      APC = atendimentos / população
 
    Carrega:
      SERVING_INDICADORES_ANUAIS
      SERVING_INDICADOR_APC
    """
 
    print(
        "Iniciando Carga Analítica "
        "(Camada Serving)..."
    )
 
    os.makedirs(
        SERVING_DIR,
        exist_ok=True
    )
 
    ibge = pd.read_csv(
        os.path.join(
            TRUSTED_DIR,
            "ibge_trusted.csv",
        )
    )
 
    agg_estab = pd.read_csv(
        os.path.join(
            TRUSTED_DIR,
            "cnes_estabelecimento_trusted.csv",
        )
    )
 
    agg_prof = pd.read_csv(
        os.path.join(
            TRUSTED_DIR,
            "cnes_profissional_trusted.csv",
        )
    )
 
    sia = pd.read_csv(
        os.path.join(
            TRUSTED_DIR,
            "sia_trusted.csv",
        )
    )
 
    # -------------------------------
    # EPC + PPC
    # -------------------------------
    serving_anual = (
        agg_estab
        .merge(
            agg_prof,
            on=[
                "id_municipio",
                "ano",
            ],
            how="outer",
        )
        .merge(
            ibge[
                [
                    "id_municipio",
                    "ano",
                    "populacao",
                ]
            ],
            on=[
                "id_municipio",
                "ano",
            ],
            how="left",
        )
    )
 
    serving_anual["EPC"] = (
        serving_anual[
            "qtd_estabelecimentos"
        ]
        / serving_anual[
            "populacao"
        ]
    ) * 1000
 
    serving_anual["PPC"] = (
        serving_anual[
            "qtd_profissionais"
        ]
        / serving_anual[
            "populacao"
        ]
    ) * 1000
 
    serving_anual.to_csv(
        os.path.join(
            SERVING_DIR,
            "indicadores_anuais_epc_ppc.csv",
        ),
        index=False,
    )
 
    print(
        f"  Indicadores anuais "
        f"(EPC/PPC) calculados: "
        f"{len(serving_anual)} linhas."
    )
 
    carregar_no_oracle(
        serving_anual,
        "SERVING_INDICADORES_ANUAIS",
    )
 
    # -------------------------------
    # APC
    # -------------------------------
    ano_mais_recente = (
        ibge["ano"].max()
    )
 
    pop_recente = ibge[
        ibge["ano"]
        == ano_mais_recente
    ][
        [
            "id_municipio",
            "populacao",
        ]
    ]
 
    serving_sia = sia.merge(
        pop_recente,
        on="id_municipio",
        how="left",
    )
 
    serving_sia["APC"] = (
        serving_sia[
            "qtd_atendimentos_periodo"
        ]
        / serving_sia[
            "populacao"
        ]
    )
 
    serving_sia.to_csv(
        os.path.join(
            SERVING_DIR,
            "indicador_periodo_apc.csv",
        ),
        index=False,
    )
 
    print(
        f"  Indicador APC calculado: "
        f"{len(serving_sia)} municípios."
    )
 
    carregar_no_oracle(
        serving_sia,
        "SERVING_INDICADOR_APC",
    )
 
    print(
        "Carga Analítica concluída. "
        "Dados persistidos no Oracle."
    )
 
 
# ==========================================
# ÍNDICE FINAL DE SUBUTILIZAÇÃO
# ==========================================
def calcular_indice_subutilizacao():
    """
    Combina EPC, PPC e APC em um índice
    final de subutilização por município.
 
    Fórmula:
      capacidade_norm =
        (EPC_norm + PPC_norm) / 2
 
      indice_subutilizacao =
        capacidade_norm - APC_norm
 
    Resultado persistido em:
      INDICE_SUBUTILIZACAO
    """
 
    print(
        "Iniciando cálculo do Índice "
        "Final de Subutilização..."
    )
 
    anual = pd.read_csv(
        os.path.join(
            SERVING_DIR,
            "indicadores_anuais_epc_ppc.csv",
        )
    )
 
    apc = pd.read_csv(
        os.path.join(
            SERVING_DIR,
            "indicador_periodo_apc.csv",
        )
    )
 
    # Obtém o registro mais recente
    # de EPC/PPC por município.
    ultimo_ano = (
        anual.groupby(
            "id_municipio"
        )["ano"]
        .transform("max")
    )
 
    recente = anual[
        anual["ano"] == ultimo_ano
    ]
 
    df = apc.merge(
        recente[
            [
                "id_municipio",
                "EPC",
                "PPC",
            ]
        ],
        on="id_municipio",
        how="left",
    )
 
    df = df.dropna(
        subset=[
            "EPC",
            "PPC",
            "APC",
        ]
    )
 
    # -------------------------------
    # NORMALIZAÇÃO MIN-MAX
    # -------------------------------
    for col in [
        "EPC",
        "PPC",
        "APC",
    ]:
 
        valor_min = df[col].min()
        valor_max = df[col].max()
 
        if valor_max == valor_min:
 
            df[
                f"{col}_norm"
            ] = 0.0
 
        else:
 
            df[
                f"{col}_norm"
            ] = (
                df[col] - valor_min
            ) / (
                valor_max - valor_min
            )
 
    # -------------------------------
    # ÍNDICE
    # -------------------------------
    df["capacidade_norm"] = (
        df["EPC_norm"]
        + df["PPC_norm"]
    ) / 2
 
    df[
        "indice_subutilizacao"
    ] = (
        df["capacidade_norm"]
        - df["APC_norm"]
    )
 
    df = df.sort_values(
        "indice_subutilizacao",
        ascending=False,
    )
 
    df.to_csv(
        os.path.join(
            SERVING_DIR,
            "indice_subutilizacao_vertex.csv",
        ),
        index=False,
    )
 
    print(
        f"  Índice final calculado para "
        f"{len(df)} municípios."
    )
 
    print(
        "  Top 5 municípios com maior "
        "indício de subutilização:"
    )
 
    print(
        df[
            [
                "nome_municipio",
                "indice_subutilizacao",
            ]
        ]
        .head(5)
        .to_string(
            index=False
        )
    )
 
    # Oracle possui somente estas
    # 6 colunas na tabela final.
    indice_oracle = df[
        [
            "id_municipio",
            "nome_municipio",
            "EPC",
            "PPC",
            "APC",
            "indice_subutilizacao",
        ]
    ].copy()
 
    carregar_no_oracle(
        indice_oracle,
        "INDICE_SUBUTILIZACAO",
    )
 
    print(
        "Cálculo do índice final "
        "concluído. Dados disponíveis "
        "para o Dashboard VERTEX (APEX)."
    )
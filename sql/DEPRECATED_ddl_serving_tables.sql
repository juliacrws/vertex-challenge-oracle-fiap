-- ==============================================================================
-- VERTEX - DDL das tabelas de Serving no Oracle Autonomous AI Database
-- Alvo da carga real feita pelo pipeline (vertex_common.carregar_no_oracle)
-- Rodar no schema VERTEX_DB já provisionado (Data Architecture, Analytics
-- & NoSQL Solutions), depois de criadas as tabelas dimensionais/fato.
-- ==============================================================================

-- DROP TABLE SERVING_INDICADORES_ANUAIS;
CREATE TABLE SERVING_INDICADORES_ANUAIS (
    ID_MUNICIPIO        NUMBER(9)      NOT NULL,
    ANO                  NUMBER(4)      NOT NULL,
    QTD_ESTABELECIMENTOS NUMBER,
    TOTAL_LEITOS         NUMBER,
    QTD_PROFISSIONAIS    NUMBER,
    POPULACAO            NUMBER,
    EPC                  NUMBER(10,4),
    PPC                  NUMBER(10,4),
    CONSTRAINT PK_SERVING_IND_ANUAL PRIMARY KEY (ID_MUNICIPIO, ANO)
);
COMMENT ON TABLE SERVING_INDICADORES_ANUAIS IS 'Indicadores anuais por município: Estabelecimentos e Profissionais per capita (EPC/PPC), camada Serving do pipeline VERTEX.';
COMMENT ON COLUMN SERVING_INDICADORES_ANUAIS.EPC IS 'Estabelecimentos por 1.000 habitantes.';
COMMENT ON COLUMN SERVING_INDICADORES_ANUAIS.PPC IS 'Profissionais de saúde por 1.000 habitantes.';

-- DROP TABLE SERVING_INDICADOR_APC;
CREATE TABLE SERVING_INDICADOR_APC (
    ID_MUNICIPIO           NUMBER(9)      NOT NULL,
    NOME_MUNICIPIO         VARCHAR2(120),
    QTD_ATENDIMENTOS_PERIODO NUMBER,
    POPULACAO              NUMBER,
    APC                    NUMBER(10,4),
    CONSTRAINT PK_SERVING_APC PRIMARY KEY (ID_MUNICIPIO)
);
COMMENT ON TABLE SERVING_INDICADOR_APC IS 'Atendimentos per capita (APC) por município no período analisado, camada Serving do pipeline VERTEX.';
COMMENT ON COLUMN SERVING_INDICADOR_APC.APC IS 'Atendimentos aprovados no SIA/SUS dividido pela população do município.';

-- DROP TABLE INDICE_SUBUTILIZACAO;
CREATE TABLE INDICE_SUBUTILIZACAO (
    ID_MUNICIPIO         NUMBER(9)      NOT NULL,
    NOME_MUNICIPIO       VARCHAR2(120),
    EPC                  NUMBER(10,4),
    PPC                  NUMBER(10,4),
    APC                  NUMBER(10,4),
    INDICE_SUBUTILIZACAO NUMBER(10,6),
    CONSTRAINT PK_INDICE_SUBUTIL PRIMARY KEY (ID_MUNICIPIO)
);
COMMENT ON TABLE INDICE_SUBUTILIZACAO IS 'Índice final do VERTEX: compara capacidade instalada (EPC+PPC normalizados) x uso real do sistema (APC normalizado) por município. Quanto maior, maior o indício de abandono/subutilização indireta. Consumido pelo Dashboard (heatmap/ranking) e pelo Select AI.';
COMMENT ON COLUMN INDICE_SUBUTILIZACAO.INDICE_SUBUTILIZACAO IS 'capacidade_norm (média EPC_norm, PPC_norm) menos APC_norm; normalização min-max entre municípios do recorte.';

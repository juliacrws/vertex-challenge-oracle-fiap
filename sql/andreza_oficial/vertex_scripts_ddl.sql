--=============================================================================
-- VERTEX -- Scripts de modelagem (Oracle / Oracle Autonomous Database)
-- Escopo: Estado de Sao Paulo, 645 municipios, 2021-2024
-- Fontes: SIASUS (mensal), CNES-ST e CNES-PF (snapshot anual, janeiro), IBGE (anual)
--
-- Este arquivo tem 6 blocos:
--   1) Modelo logico normalizado (3FN)               -> tabelas de staging/OLTP
--   2) Modelo dimensional simplificado (4 tabelas)   -> DIM_POPULACAO, DIM_ESTABELECIMENTO,
--      DIM_PROFISSIONAL, FATO_ATENDIMENTO + view do indice VERTEX
--   3) Carga do 3FN a partir dos CSVs (staging)
--   4) Carga das 4 tabelas a partir do 3FN, resolvendo o descasamento de grao
--      mensal (SIASUS) x anual (CNES/IBGE) via chave composta (id_municipio, ano)
--   5) COMMENT ON tabelas/colunas -- documentacao semantica p/ o Select AI entender o schema
--   6) Criacao do profile do Oracle Select AI, escopado nas 4 tabelas + view
--=============================================================================


--=============================================================================
-- BLOCO 1: MODELO LOGICO NORMALIZADO (3FN)
--=============================================================================

CREATE TABLE municipio (
    id_municipio     NUMBER(7)     NOT NULL,
    sigla_uf         VARCHAR2(2)   NOT NULL,
    nome_municipio   VARCHAR2(100),                 -- enriquecer: nao vem nos CSVs atuais
    CONSTRAINT pk_municipio PRIMARY KEY (id_municipio)
);

CREATE TABLE tipo_unidade (
    tipo_unidade   NUMBER(3)   NOT NULL,
    descricao      VARCHAR2(150),                   -- popular com a tabela de dominio oficial do CNES
    CONSTRAINT pk_tipo_unidade PRIMARY KEY (tipo_unidade)
);

CREATE TABLE natureza_juridica (
    id_natureza_juridica   NUMBER(4)   NOT NULL,
    descricao              VARCHAR2(150),           -- popular com a tabela CONCLA/Receita Federal
    CONSTRAINT pk_natureza_juridica PRIMARY KEY (id_natureza_juridica)
);

CREATE TABLE familia_cbo (
    familia_ocupacional_cbo   NUMBER(6)   NOT NULL,
    descricao                 VARCHAR2(150),
    CONSTRAINT pk_familia_cbo PRIMARY KEY (familia_ocupacional_cbo)
);

-- Linha sentinela para os 775 registros de CNES-PF sem CBO informado
INSERT INTO familia_cbo (familia_ocupacional_cbo, descricao)
VALUES (-1, 'Nao classificado');

CREATE TABLE atendimento_mensal (
    id_municipio               NUMBER(7)     NOT NULL,
    ano                        NUMBER(4)     NOT NULL,
    mes                        NUMBER(2)     NOT NULL,
    quantidade_atendimentos    NUMBER(12)    NOT NULL,
    valor_total_aprovado       NUMBER(16,2)  NOT NULL,
    CONSTRAINT pk_atendimento_mensal PRIMARY KEY (id_municipio, ano, mes),
    CONSTRAINT fk_atend_municipio FOREIGN KEY (id_municipio) REFERENCES municipio(id_municipio),
    CONSTRAINT ck_atend_mes CHECK (mes BETWEEN 1 AND 12)
);

CREATE TABLE estabelecimento_ano (
    id_estabelecimento_cnes          NUMBER(10)  NOT NULL,
    ano                               NUMBER(4)   NOT NULL,
    id_municipio                      NUMBER(7)   NOT NULL,
    tipo_unidade                      NUMBER(3)   NOT NULL,
    id_natureza_juridica              NUMBER(4)   NOT NULL,
    quantidade_leito_cirurgico        NUMBER(6)   DEFAULT 0 NOT NULL,
    quantidade_leito_clinico          NUMBER(6)   DEFAULT 0 NOT NULL,
    quantidade_leito_complementar     NUMBER(6)   DEFAULT 0 NOT NULL,
    indicador_atencao_ambulatorial    NUMBER(1)   NOT NULL,
    CONSTRAINT pk_estabelecimento_ano PRIMARY KEY (id_estabelecimento_cnes, ano),
    CONSTRAINT fk_estab_municipio FOREIGN KEY (id_municipio) REFERENCES municipio(id_municipio),
    CONSTRAINT fk_estab_tipo FOREIGN KEY (tipo_unidade) REFERENCES tipo_unidade(tipo_unidade),
    CONSTRAINT fk_estab_natureza FOREIGN KEY (id_natureza_juridica) REFERENCES natureza_juridica(id_natureza_juridica),
    CONSTRAINT ck_estab_ambulatorial CHECK (indicador_atencao_ambulatorial IN (0,1))
);

CREATE TABLE forca_trabalho_ano (
    id_municipio                      NUMBER(7)   NOT NULL,
    ano                                NUMBER(4)   NOT NULL,
    familia_ocupacional_cbo           NUMBER(6)   NOT NULL,
    quantidade_profissionais          NUMBER(8)   NOT NULL,
    soma_carga_horaria_ambulatorial   NUMBER(10)  NOT NULL,
    CONSTRAINT pk_forca_trabalho_ano PRIMARY KEY (id_municipio, ano, familia_ocupacional_cbo),
    CONSTRAINT fk_ft_municipio FOREIGN KEY (id_municipio) REFERENCES municipio(id_municipio),
    CONSTRAINT fk_ft_cbo FOREIGN KEY (familia_ocupacional_cbo) REFERENCES familia_cbo(familia_ocupacional_cbo)
);

CREATE TABLE populacao_ano (
    id_municipio   NUMBER(7)   NOT NULL,
    ano            NUMBER(4)   NOT NULL,
    populacao      NUMBER(9)   NOT NULL,
    CONSTRAINT pk_populacao_ano PRIMARY KEY (id_municipio, ano),
    CONSTRAINT fk_pop_municipio FOREIGN KEY (id_municipio) REFERENCES municipio(id_municipio)
);


--=============================================================================
-- BLOCO 2: MODELO DIMENSIONAL SIMPLIFICADO (4 TABELAS) -- camada analitica
--
-- DIM_POPULACAO, DIM_ESTABELECIMENTO e DIM_PROFISSIONAL tem grao MUNICIPIO x ANO
-- (nao so municipio: a capacidade muda todo ano -- 74 mil estabelecimentos em
-- 2021 viraram 91 mil em 2024 -- se a chave fosse so municipio, o valor ficaria
-- travado no mesmo numero nos 4 anos). FATO_ATENDIMENTO tem grao municipio x
-- ano x mes e referencia as 3 dimensoes por (id_municipio, ano): os 12 meses de
-- um mesmo ano reaproveitam a mesma linha de dimensao -- isso resolve sozinho o
-- descasamento de grao mensal x anual, sem precisar de uma tabela de fato anual
-- separada nem de forward-fill manual.
--=============================================================================

CREATE TABLE dim_populacao (
    id_municipio     NUMBER(7)      NOT NULL,
    ano              NUMBER(4)      NOT NULL,
    sigla_uf         VARCHAR2(2)    NOT NULL,
    nome_municipio   VARCHAR2(100),                 -- enriquecer via malha municipal IBGE (heatmap)
    latitude         NUMBER(9,6),                   -- enriquecer (heatmap)
    longitude        NUMBER(9,6),                   -- enriquecer (heatmap)
    populacao        NUMBER(9)      NOT NULL,
    CONSTRAINT pk_dim_populacao PRIMARY KEY (id_municipio, ano)
);

CREATE TABLE dim_estabelecimento (
    id_municipio                           NUMBER(7)  NOT NULL,
    ano                                     NUMBER(4)  NOT NULL,
    total_estabelecimentos                 NUMBER(8)  NOT NULL,
    total_estabelecimentos_ambulatoriais   NUMBER(8)  NOT NULL,
    total_leito_cirurgico                  NUMBER(8)  NOT NULL,
    total_leito_clinico                    NUMBER(8)  NOT NULL,
    total_leito_complementar               NUMBER(8)  NOT NULL,
    CONSTRAINT pk_dim_estabelecimento PRIMARY KEY (id_municipio, ano),
    CONSTRAINT fk_dimestab_pop FOREIGN KEY (id_municipio, ano) REFERENCES dim_populacao(id_municipio, ano)
);
-- OBS: agregado a municipio x ano -> perde o detalhe de tipo_unidade/natureza_juridica
-- por estabelecimento individual (mesma limitacao ja registrada no documento de modelagem).

CREATE TABLE dim_profissional (
    id_municipio                      NUMBER(7)   NOT NULL,
    ano                                NUMBER(4)   NOT NULL,
    total_profissionais               NUMBER(9)   NOT NULL,
    soma_carga_horaria_ambulatorial   NUMBER(12)  NOT NULL,
    CONSTRAINT pk_dim_profissional PRIMARY KEY (id_municipio, ano),
    CONSTRAINT fk_dimprof_pop FOREIGN KEY (id_municipio, ano) REFERENCES dim_populacao(id_municipio, ano)
);
-- OBS: agregado a municipio x ano (soma todas as familias CBO) DE PROPOSITO --
-- se mantivesse a quebra por CBO aqui, um relatorio que juntasse FATO_ATENDIMENTO
-- com esta dimensao agrupando por CBO inflaria quantidade_atendimentos (fan-out):
-- o mesmo valor do fato se repetiria uma vez para cada familia CBO daquele
-- municipio/ano. Se um dia precisarem do detalhe por CBO, tratem como uma tabela
-- a parte, nunca somada na mesma query que soma atendimentos.

CREATE TABLE fato_atendimento (
    id_municipio               NUMBER(7)     NOT NULL,
    ano                        NUMBER(4)     NOT NULL,
    mes                        NUMBER(2)     NOT NULL,
    quantidade_atendimentos    NUMBER(12)    NOT NULL,
    valor_total_aprovado       NUMBER(16,2)  NOT NULL,
    flag_dado_incompleto       NUMBER(1)     DEFAULT 0 NOT NULL,  -- marca competencias sem coleta (ex.: 03/2024)
    CONSTRAINT pk_fato_atendimento PRIMARY KEY (id_municipio, ano, mes),
    CONSTRAINT fk_fato_pop   FOREIGN KEY (id_municipio, ano) REFERENCES dim_populacao(id_municipio, ano),
    CONSTRAINT fk_fato_estab FOREIGN KEY (id_municipio, ano) REFERENCES dim_estabelecimento(id_municipio, ano),
    CONSTRAINT fk_fato_prof  FOREIGN KEY (id_municipio, ano) REFERENCES dim_profissional(id_municipio, ano),
    CONSTRAINT ck_fato_mes  CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_fato_flag CHECK (flag_dado_incompleto IN (0,1))
);

-- VIEW: indice VERTEX calculado juntando as 4 tabelas -- nao precisa de uma 5a
-- tabela fisica; materialize (CREATE TABLE AS SELECT) so se a performance exigir.
--
-- IMPORTANTE: quando flag_dado_incompleto = 1, os campos calculados (APC/PPC/EPC
-- e o indice) saem NULL de proposito, em vez de um numero baseado em zero. Sem
-- isso, qualquer competencia sem coleta real (ex.: 03/2024, ou um municipio sem
-- nenhuma linha no SIASUS) apareceria como "abandono total" (indice = 0) no
-- dashboard -- um artefato de dado faltante, nao um resultado real.
CREATE OR REPLACE VIEW vw_indice_vertex AS
SELECT
    fa.id_municipio,
    fa.ano,
    fa.mes,
    fa.quantidade_atendimentos,
    dp.populacao,
    de.total_estabelecimentos_ambulatoriais,
    dpr.total_profissionais,
    CASE WHEN fa.flag_dado_incompleto = 1 THEN NULL
         ELSE fa.quantidade_atendimentos / dp.populacao END AS apc_atendimentos_per_capita,
    CASE WHEN fa.flag_dado_incompleto = 1 THEN NULL
         ELSE dpr.total_profissionais / dp.populacao END AS ppc_profissionais_per_capita,
    CASE WHEN fa.flag_dado_incompleto = 1 THEN NULL
         ELSE de.total_estabelecimentos_ambulatoriais / dp.populacao END AS epc_estabelecimentos_per_capita,
    CASE WHEN fa.flag_dado_incompleto = 1 THEN NULL
         ELSE (fa.quantidade_atendimentos / dp.populacao)
              / NULLIF(0.5 * (dpr.total_profissionais / dp.populacao)
                     + 0.5 * (de.total_estabelecimentos_ambulatoriais / dp.populacao), 0)
    END AS indice_subutilizacao,
    fa.flag_dado_incompleto
FROM fato_atendimento fa
JOIN dim_populacao dp       ON dp.id_municipio = fa.id_municipio AND dp.ano = fa.ano
JOIN dim_estabelecimento de ON de.id_municipio = fa.id_municipio AND de.ano = fa.ano
JOIN dim_profissional dpr   ON dpr.id_municipio = fa.id_municipio AND dpr.ano = fa.ano;


--=============================================================================
-- BLOCO 3: CARGA DO 3FN A PARTIR DOS CSVS (staging externo)
-- Ajuste os nomes das external tables / diretorios OCI Object Storage conforme
-- o pipeline de ETL real (aqui assume-se tabelas de staging ja carregadas
-- com o layout identico aos CSVs recebidos: stg_siasus, stg_ibge, stg_cnes_est,
-- stg_cnes_prof).
--=============================================================================

-- MUNICIPIO: universo vem do IBGE (unica base sem buracos, 645/645)
INSERT INTO municipio (id_municipio, sigla_uf)
SELECT DISTINCT id_municipio, sigla_uf
FROM stg_ibge;

-- TIPO_UNIDADE / NATUREZA_JURIDICA / FAMILIA_CBO: extrair os codigos distintos
-- que aparecem nos dados (descricao fica NULL ate importar as tabelas de dominio oficiais)
INSERT INTO tipo_unidade (tipo_unidade)
SELECT DISTINCT tipo_unidade FROM stg_cnes_est;

INSERT INTO natureza_juridica (id_natureza_juridica)
SELECT DISTINCT id_natureza_juridica FROM stg_cnes_est;

INSERT INTO familia_cbo (familia_ocupacional_cbo)
SELECT DISTINCT familia_ocupacional_cbo
FROM stg_cnes_prof
WHERE familia_ocupacional_cbo IS NOT NULL;

-- ATENDIMENTO_MENSAL: carga direta (grao ja bate 1:1 com o staging)
--
-- ATENCAO: durante a carga real apareceram algumas linhas em stg_siasus com
-- valor_total_aprovado absurdamente alto (~10^16, ou seja, quadrilhoes de
-- reais em um unico municipio-mes -- impossivel). Isso e um bug conhecido de
-- extracao (BigQuery/Colab), nao um valor real, e nao afeta o indice VERTEX
-- (que usa so quantidade_atendimentos, nunca valor_total_aprovado -- ver
-- VW_INDICE_VERTEX no Bloco 2). O CASE abaixo zera qualquer valor acima de
-- 1 trilhao (limite de sanidade, bem acima de qualquer valor real possivel
-- para um municipio-mes) em vez de deixar o INSERT falhar com ORA-01438.
INSERT INTO atendimento_mensal (id_municipio, ano, mes, quantidade_atendimentos, valor_total_aprovado)
SELECT
    id_municipio, ano, mes,
    quantidade_atendimentos,
    CASE WHEN valor_total_aprovado > 1000000000000 THEN 0 ELSE valor_total_aprovado END
FROM stg_siasus;

-- ESTABELECIMENTO_ANO: carga direta
INSERT INTO estabelecimento_ano (
    id_estabelecimento_cnes, ano, id_municipio, tipo_unidade, id_natureza_juridica,
    quantidade_leito_cirurgico, quantidade_leito_clinico, quantidade_leito_complementar,
    indicador_atencao_ambulatorial
)
SELECT
    id_estabelecimento_cnes, ano, id_municipio, tipo_unidade, id_natureza_juridica,
    quantidade_leito_cirurgico, quantidade_leito_clinico, quantidade_leito_complementar,
    indicador_atencao_ambulatorial
FROM stg_cnes_est;

-- FORCA_TRABALHO_ANO: nulos de CBO viram a categoria sentinela -1
INSERT INTO forca_trabalho_ano (
    id_municipio, ano, familia_ocupacional_cbo, quantidade_profissionais, soma_carga_horaria_ambulatorial
)
SELECT
    id_municipio, ano, NVL(familia_ocupacional_cbo, -1), quantidade_profissionais, soma_carga_horaria_ambulatorial
FROM stg_cnes_prof;

-- POPULACAO_ANO: carga direta
INSERT INTO populacao_ano (id_municipio, ano, populacao)
SELECT id_municipio, ano, populacao
FROM stg_ibge;

-- IMPORTANTE: da COMMIT aqui antes de seguir pro Bloco 4 (ou antes de
-- desconectar a sessao por qualquer motivo). O Bloco 3 e so DML, sem nenhum
-- DDL no meio -- se a sessao cair ou for desconectada sem COMMIT, o Oracle
-- desfaz (ROLLBACK) TODO o Bloco 3 automaticamente, e as tabelas voltam a
-- ficar vazias (isso aconteceu na pratica: gerou ORA-02291 no Bloco 4 depois
-- de reconectar sem ter commitado antes).
COMMIT;


--=============================================================================
-- BLOCO 4: CARGA DAS 4 TABELAS A PARTIR DO 3FN
--=============================================================================

-- DIM_POPULACAO
INSERT INTO dim_populacao (id_municipio, ano, sigla_uf, populacao)
SELECT p.id_municipio, p.ano, m.sigla_uf, p.populacao
FROM populacao_ano p
JOIN municipio m ON m.id_municipio = p.id_municipio;

-- DIM_ESTABELECIMENTO: agrega estabelecimento_ano por municipio/ano
INSERT INTO dim_estabelecimento (
    id_municipio, ano, total_estabelecimentos, total_estabelecimentos_ambulatoriais,
    total_leito_cirurgico, total_leito_clinico, total_leito_complementar
)
SELECT
    id_municipio, ano,
    COUNT(*),
    SUM(indicador_atencao_ambulatorial),
    SUM(quantidade_leito_cirurgico),
    SUM(quantidade_leito_clinico),
    SUM(quantidade_leito_complementar)
FROM estabelecimento_ano
GROUP BY id_municipio, ano;

-- DIM_PROFISSIONAL: agrega forca_trabalho_ano por municipio/ano (soma todas as CBO)
INSERT INTO dim_profissional (id_municipio, ano, total_profissionais, soma_carga_horaria_ambulatorial)
SELECT id_municipio, ano, SUM(quantidade_profissionais), SUM(soma_carga_horaria_ambulatorial)
FROM forca_trabalho_ano
GROUP BY id_municipio, ano;

-- FATO_ATENDIMENTO: completa o calendario municipio x competencia (2021-01 a
-- 2024-12) usando o universo de municipios do 3FN (645, sem buracos).
--
-- flag_dado_incompleto = 1 em DOIS casos, detectados automaticamente (nao
-- fixados na mao, para o script continuar valendo se surgirem novos buracos
-- numa proxima extracao). AMBOS OS CASOS FORAM INVESTIGADOS E TEM CAUSA
-- CONFIRMADA (nao sao mais suspeita, sao fato verificado direto na fonte):
--   (a) COMPETENCIA sem NENHUMA linha em todo o estado -- caso de 2024-03:
--       confirmado via BigQuery que SP e TO sao os 2 unicos estados sem
--       essa competencia na tabela basedosdados.br_ms_sia.producao_ambulatorial
--       (os outros 25 estados tem o mes normalmente). O dado EXISTE no
--       DataSUS original (confirmado no TABNET: PASP2403a/b/c.dbc existem) --
--       so nao chegou nesse espelho especifico. Nao e erro do pipeline.
--   (b) MUNICIPIO sem NENHUMA linha em nenhum dos 48 meses -- os 3 casos
--       (3523305, 3545100, 3554656) tem historico normal na mesma tabela
--       ATE 2019, e somem exatamente a partir de 2020 -- coincide com a
--       migracao da atencao basica desses municipios (pequenos, populacao
--       entre 2 mil e 17 mil) para o e-SUS APS/SISAB, sistema que essa
--       tabela do SIA-PA classico nao captura. Nao e falha de coleta: e
--       mudanca de sistema de origem, e representa so 0,05% da populacao
--       do estado (irrelevante para os agregados estaduais).
-- Em ambos os casos o valor fica 0 (nao inventamos numero), mas a flag avisa
-- o consumidor do dado (view/dashboard/Select AI) pra nao tratar esse zero
-- como um indice calculavel de verdade -- ver vw_indice_vertex no Bloco 2.
INSERT INTO fato_atendimento (id_municipio, ano, mes, quantidade_atendimentos, valor_total_aprovado, flag_dado_incompleto)
SELECT
    m.id_municipio,
    cal.ano,
    cal.mes,
    NVL(am.quantidade_atendimentos, 0),
    NVL(am.valor_total_aprovado, 0),
    CASE
        WHEN NVL(cobertura_competencia.linhas, 0) = 0 THEN 1   -- caso (a)
        WHEN NVL(cobertura_municipio.linhas, 0) = 0 THEN 1     -- caso (b)
        ELSE 0
    END AS flag_dado_incompleto
FROM municipio m
CROSS JOIN (
    SELECT 2021 + LEVEL_ANO AS ano, LEVEL_MES AS mes
    FROM (SELECT LEVEL - 1 AS LEVEL_ANO FROM dual CONNECT BY LEVEL <= 4) anos,
         (SELECT LEVEL AS LEVEL_MES FROM dual CONNECT BY LEVEL <= 12) meses
) cal
LEFT JOIN atendimento_mensal am
       ON am.id_municipio = m.id_municipio
      AND am.ano = cal.ano
      AND am.mes = cal.mes
LEFT JOIN (
    SELECT ano, mes, COUNT(*) AS linhas
    FROM atendimento_mensal
    GROUP BY ano, mes
) cobertura_competencia
       ON cobertura_competencia.ano = cal.ano
      AND cobertura_competencia.mes = cal.mes
LEFT JOIN (
    SELECT id_municipio, COUNT(*) AS linhas
    FROM atendimento_mensal
    GROUP BY id_municipio
) cobertura_municipio
       ON cobertura_municipio.id_municipio = m.id_municipio;

COMMIT;

-- A partir daqui, qualquer consulta do dashboard/ranking/heatmap pode usar
-- diretamente a view VW_INDICE_VERTEX (ex.: SELECT * FROM vw_indice_vertex
-- WHERE ano = 2024 ORDER BY indice_subutilizacao ASC).


--=============================================================================
-- BLOCO 5: COMMENT ON -- documentacao semantica das 4 tabelas + view
--
-- O Select AI traduz pergunta em linguagem natural pra SQL usando os nomes
-- de tabela/coluna E os comentarios do dicionario de dados como contexto.
-- Sem comentario, "indice_subutilizacao" e so um nome de coluna; com
-- comentario, vira uma pergunta respondivel tipo "quais municipios tem
-- maior indice de abandono em 2024?". Comentar tambem as flags e as
-- limitacoes conhecidas evita que o Select AI gere uma resposta que ignora
-- os 3 municipios sem dado ou o mes 03/2024, e produza numero errado.
--=============================================================================

COMMENT ON TABLE dim_populacao IS
    'Populacao por municipio de SP e ano (2021-2024), fonte IBGE. Uma linha por municipio-ano. Base para calcular indicadores per capita.';
COMMENT ON COLUMN dim_populacao.id_municipio IS 'Codigo IBGE do municipio (7 digitos).';
COMMENT ON COLUMN dim_populacao.populacao IS 'Populacao estimada do municipio naquele ano.';
COMMENT ON COLUMN dim_populacao.nome_municipio IS 'Nome do municipio (preencher via malha municipal IBGE).';

COMMENT ON TABLE dim_estabelecimento IS
    'Capacidade instalada de saude por municipio e ano (snapshot de janeiro, fonte CNES-ST). Totais agregados, nao por estabelecimento individual.';
COMMENT ON COLUMN dim_estabelecimento.total_estabelecimentos_ambulatoriais IS
    'Quantidade de estabelecimentos de saude com atendimento ambulatorial no municipio naquele ano.';
COMMENT ON COLUMN dim_estabelecimento.total_leito_cirurgico IS 'Soma de leitos cirurgicos de todos os estabelecimentos do municipio naquele ano.';

COMMENT ON TABLE dim_profissional IS
    'Forca de trabalho em saude por municipio e ano (snapshot de janeiro, fonte CNES-PF). Total agregado, sem quebra por ocupacao/CBO.';
COMMENT ON COLUMN dim_profissional.total_profissionais IS 'Quantidade total de profissionais de saude cadastrados no municipio naquele ano.';
COMMENT ON COLUMN dim_profissional.soma_carga_horaria_ambulatorial IS 'Soma das cargas horarias ambulatoriais (em horas) de todos os profissionais do municipio naquele ano.';

COMMENT ON TABLE fato_atendimento IS
    'Producao ambulatorial mensal por municipio de SP (fonte SIASUS, 2021-2024). Uma linha por municipio-ano-mes.';
COMMENT ON COLUMN fato_atendimento.quantidade_atendimentos IS 'Quantidade de procedimentos ambulatoriais aprovados no municipio naquele mes.';
COMMENT ON COLUMN fato_atendimento.valor_total_aprovado IS 'Valor total em reais aprovado para pagamento dos procedimentos daquele municipio-mes.';
COMMENT ON COLUMN fato_atendimento.flag_dado_incompleto IS
    '1 = mes ou municipio com dado ausente/incompleto na fonte (ex.: marco/2024 para todo o estado, ou os 3 municipios que migraram para o e-SUS APS a partir de 2020). Quando 1, NAO tratar quantidade_atendimentos=0 como abandono real -- consultar vw_indice_vertex, que ja retorna NULL nesses casos.';

COMMENT ON TABLE vw_indice_vertex IS
    'Indice VERTEX de subutilizacao/abandono indireto do atendimento ambulatorial, por municipio de SP e mes (2021-2024). Junta atendimento (SIASUS) com capacidade instalada (CNES) e populacao (IBGE). Indice baixo = atende pouco para a capacidade que tem (possivel subutilizacao). Quando flag_dado_incompleto=1, os campos calculados vem NULL (dado insuficiente, nao "zero atendimentos").';
COMMENT ON COLUMN vw_indice_vertex.apc_atendimentos_per_capita IS 'APC: atendimentos ambulatoriais por habitante no mes.';
COMMENT ON COLUMN vw_indice_vertex.ppc_profissionais_per_capita IS 'PPC: profissionais de saude por habitante no municipio naquele ano.';
COMMENT ON COLUMN vw_indice_vertex.epc_estabelecimentos_per_capita IS 'EPC: estabelecimentos ambulatoriais por habitante no municipio naquele ano.';
COMMENT ON COLUMN vw_indice_vertex.indice_subutilizacao IS
    'Indice de subutilizacao do sistema de saude: APC dividido pela capacidade instalada per capita (media ponderada de PPC e EPC). Quanto menor, maior o indicio de subutilizacao/abandono indireto. NULL quando o mes/municipio tem dado incompleto na fonte.';


--=============================================================================
-- BLOCO 6: ORACLE SELECT AI -- profile escopado nas 4 tabelas + view
--
-- Pre-requisito (feito uma vez, fora deste script): uma credencial de
-- provedor de IA generativa configurada no Autonomous Database via
-- DBMS_CLOUD.CREATE_CREDENTIAL (ex.: usando uma OCI GenAI API key ou um
-- OCI resource principal). Troque 'OCI_GENAI_CRED' abaixo pelo nome real
-- da credencial criada no seu tenancy OCI.
--
-- O object_list restringe o Select AI a enxergar SO essas 5 tabelas/view --
-- de proposito: as tabelas do 3FN (Bloco 1) sao staging interno, nao devem
-- ser expostas a perguntas em linguagem natural (nomes tecnicos, sem
-- comentario de negocio, e o usuario final so precisa da camada analitica).
--=============================================================================

BEGIN
    DBMS_CLOUD_AI.CREATE_PROFILE(
        profile_name => 'VERTEX_PROFILE',
        attributes    => '{
            "provider": "oci",
            "credential_name": "OCI_GENAI_CRED",
            "object_list": [
                {"name": "DIM_POPULACAO"},
                {"name": "DIM_ESTABELECIMENTO"},
                {"name": "DIM_PROFISSIONAL"},
                {"name": "FATO_ATENDIMENTO"},
                {"name": "VW_INDICE_VERTEX"}
            ],
            "comments": true
        }'
    );
END;
/

-- Ativa o profile na sessao (ou por usuario, conforme o app do chatbot)
BEGIN
    DBMS_CLOUD_AI.SET_PROFILE(profile_name => 'VERTEX_PROFILE');
END;
/

-- Teste rapido, ja usando as perguntas de exemplo do pitch original:
-- SELECT AI 'Quais municipios de SP tem menor cobertura em 2024?';
-- SELECT AI 'Como evoluiu o indice de subutilizacao em 2023?';
-- SELECT AI CHAT 'Explique o que significa um indice_subutilizacao baixo';

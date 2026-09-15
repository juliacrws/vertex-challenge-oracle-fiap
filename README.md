# VERTEX | Painel Inteligente de Acesso Hospitalar e Perfil de Atendimento

> **Dados que conectam necessidade e capacidade.**

A **VERTEX** é uma solução de apoio à análise de dados de saúde pública desenvolvida para o **Challenge Oracle & FIAP 2026**, na turma **1TSCPF**.

A solução integra dados públicos de **população, profissionais de saúde, estabelecimentos e produção ambulatorial** para permitir uma análise integrada da relação entre **necessidade da população, capacidade assistencial e utilização dos serviços**.

O projeto combina **engenharia de dados, Apache Airflow, Oracle Autonomous Database, SQL, Oracle APEX e Oracle Select AI**, transformando dados públicos dispersos em indicadores comparáveis e acessíveis para análise.

---

## 👥 Equipe

| Integrante                      |       RM |
| ------------------------------- | -------: |
| Andreza do Livramento Silva     | RM570964 |
| Diego Gaspar                    | RM568924 |
| João Guilherme Cavalcante Matos | RM570975 |
| **Julia de Moraes Barbosa**     | RM572997 |
| Mariana Ayumi Dantas Kuramitsu  | RM572788 |

---

# 🏥 Problema

Na saúde pública, a indisponibilidade de atendimento nem sempre representa apenas uma ausência absoluta de recursos.

Um dos desafios está em compreender **como população, profissionais, estabelecimentos e produção ambulatorial estão distribuídos entre os municípios**.

Essas informações estão disponíveis em diferentes bases públicas, mas sua análise isolada dificulta a identificação de situações como:

* baixa disponibilidade relativa de profissionais;
* produção ambulatorial desproporcional ao porte populacional;
* capacidade potencialmente subutilizada;
* possíveis carências estruturais;
* diferenças entre municípios que não aparecem quando são considerados apenas valores absolutos.

A VERTEX foi desenvolvida para **integrar essas informações em uma visão única, comparável e orientada à investigação**.

> **Importante:** os indicadores da VERTEX são ferramentas de apoio à análise. Eles não representam, isoladamente, um diagnóstico definitivo de eficiência, ineficiência ou qualidade da assistência de um município.

---

# 🎯 Objetivo

A VERTEX busca apoiar gestores e analistas na identificação de **possíveis desequilíbrios entre capacidade assistencial e utilização observada**.

A solução permite:

* integrar diferentes fontes de dados públicos;
* comparar municípios de diferentes portes;
* utilizar indicadores relativos à população;
* analisar capacidade e produção ambulatorial;
* identificar padrões que merecem investigação;
* explorar os dados por meio de dashboards;
* realizar consultas em linguagem natural utilizando inteligência artificial.

O fluxo analítico da solução pode ser resumido em:

```text
DADOS
  ↓
INTEGRAÇÃO
  ↓
COMPARAÇÃO
  ↓
INSIGHT
  ↓
INVESTIGAÇÃO / DECISÃO
```

---

# 🏗️ Arquitetura

A arquitetura da VERTEX foi estruturada com uma abordagem inspirada em **Lambda Architecture**, permitindo trabalhar com fontes que possuem diferentes frequências de atualização.

```text
                FONTES PÚBLICAS
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
       BATCH LAYER          SPEED LAYER
       SIA/SUS + IBGE           CNES
             │                   │
             └─────────┬─────────┘
                       ↓
              PROCESSAMENTO
              E CONSOLIDAÇÃO
                       ↓
          ORACLE AUTONOMOUS DATABASE
                       │
              ┌────────┴────────┐
              ↓                 ↓
          SQL / VIEWS       SELECT AI
              │                 │
              └────────┬────────┘
                       ↓
                 ORACLE APEX
                       │
                       ↓
             DASHBOARD VERTEX
                       │
                       ↓
             COMPARAÇÃO → INSIGHT
```

---

# ⚙️ Engenharia de Dados

## Apache Airflow

O **Apache Airflow** é utilizado como camada de orquestração dos pipelines de dados.

O ambiente está organizado em:

```text
airflow-vertex/
```

As principais DAGs são:

```text
airflow-vertex/dags/
├── dag_vertex_batch.py
├── dag_vertex_speed.py
└── vertex_common.py
```

O diretório também contém arquivos relacionados ao ambiente Docker, dados de execução, logs, evidências e configuração da conexão com o Oracle.

---

## 📦 Batch Layer

A DAG:

```text
airflow-vertex/dags/dag_vertex_batch.py
```

representa o fluxo de processamento dos dados provenientes principalmente do **SIA/SUS e IBGE**.

Seu fluxo conceitual é:

```text
Ingestão SIA
     ↓
Transformação SIA + IBGE
     ↓
Sincronização com Speed Layer
     ↓
Carga analítica
     ↓
Cálculo do índice
```

A Batch Layer foi projetada para acompanhar a periodicidade de atualização dos dados de produção ambulatorial.

### Status da automação

O pipeline `pipeline_vertex_batch` está funcional e validado como **prova de conceito da arquitetura proposta**, contemplando:

* ingestão;
* transformação;
* sincronização entre camadas;
* carga no Oracle;
* cálculo de indicadores.

Na implementação atual do Airflow, o pipeline automatizado opera em **granularidade anual** e grava dados nas tabelas:

```text
SERVING_INDICADORES_ANUAIS
SERVING_INDICADOR_APC
INDICE_SUBUTILIZACAO
```

Esse conjunto representa uma versão inicial da solução.

O modelo dimensional utilizado na versão final do Dashboard e do Select AI possui granularidade **mensal**, estruturado a partir do modelo oficial localizado em:

```text
sql/andreza_oficial/
```

O modelo final contempla:

```text
DIM_POPULACAO
DIM_ESTABELECIMENTO
DIM_PROFISSIONAL
FATO_ATENDIMENTO
```

com:

```text
30.960 registros
= 645 municípios × 4 anos × 12 meses
```

Como a carga automatizada existente no Airflow e o modelo dimensional final possuem granularidades diferentes, a migração da automação para o modelo mensal exigiria uma adaptação estrutural do pipeline.

Por esse motivo, essa etapa não foi incorporada à entrega atual.

A carga final utilizada pelo Dashboard VERTEX e pelo Select AI foi realizada diretamente no Oracle a partir dos datasets de **SIASUS, IBGE e CNES**, com validação de volumetria durante as etapas de processamento.

> **Próxima evolução:** automatizar integralmente a carga do modelo dimensional mensal por meio do Airflow.

---

# ⚡ Speed Layer

A DAG:

```text
airflow-vertex/dags/dag_vertex_speed.py
```

representa a camada de atualização mais frequente da arquitetura.

Ela trabalha principalmente com dados do **CNES**, relacionados à capacidade instalada e aos recursos humanos.

Fluxo:

```text
Ingestão CNES
     ↓
Transformação CNES
```

A Speed Layer possui execução diária, permitindo representar uma cadência diferente daquela utilizada pelos dados de produção ambulatorial.

Funções compartilhadas entre os pipelines estão centralizadas em:

```text
airflow-vertex/dags/vertex_common.py
```

---

# 📊 Dados e Indicadores

A VERTEX integra informações relacionadas a:

* municípios;
* população;
* profissionais de saúde;
* estabelecimentos;
* produção ambulatorial;
* procedimentos realizados.

Um dos indicadores utilizados é:

```text
Profissionais por 10 mil habitantes
```

A utilização de indicadores relativos permite comparar municípios de diferentes portes populacionais de maneira mais adequada do que uma análise baseada exclusivamente em valores absolutos.

---

# 📐 Índice de Subutilização

O indicador utilizado na versão final da solução está implementado na view:

```text
VW_INDICE_VERTEX
```

A view utiliza o modelo dimensional:

```text
FATO_ATENDIMENTO
        +
DIM_POPULACAO
DIM_ESTABELECIMENTO
DIM_PROFISSIONAL
```

A fórmula utilizada é:

```text
Índice = APC / (0,5 × PPC + 0,5 × EPC)
```

Onde os componentes representam indicadores relacionados à produção, população e capacidade assistencial utilizados pela metodologia da VERTEX.

### Interpretação

Na versão final:

```text
Índice menor
      ↓
Maior indício de subutilização
```

O indicador deve ser utilizado como **sinal para investigação**, e não como uma conclusão isolada sobre determinado município.

### Qualidade dos dados

Quando um período apresenta dados incompletos, identificado por:

```text
FLAG_DADO_INCOMPLETO = 1
```

o índice é definido como:

```text
NULL
```

em vez de tratar automaticamente a ausência de dados como zero.

Essa abordagem evita que períodos com informação ausente sejam interpretados como baixa utilização.

Um exemplo identificado durante a análise foi a ausência de dados para todo o estado em determinado período de **março de 2024**.

---

# 🗄️ Oracle Autonomous Database

O **Oracle Autonomous Database** funciona como principal camada de persistência e consulta da VERTEX.

O banco armazena os dados estruturados utilizados pelo:

* Dashboard VERTEX;
* Oracle APEX;
* Oracle Select AI;
* consultas SQL;
* views analíticas.

As estruturas principais da solução final incluem:

```text
ADMIN.FATO_ATENDIMENTO
ADMIN.DIM_*
ADMIN.VW_INDICE_VERTEX
ADMIN.V_VERTEX_DASHBOARD
```

Para o APEX, é utilizada uma view-ponte:

```text
WKSP_VERTEX.V_VERTEX_DASHBOARD
```

Os materiais relacionados ao banco estão organizados em:

```text
mariana_oracle_apex/01_Banco_Oracle/
```

---

# 🧠 Oracle Select AI

A VERTEX utiliza o **Oracle Select AI** para permitir consultas aos dados utilizando linguagem natural.

Por exemplo:

```text
Quais municípios possuem menor quantidade de profissionais
por 10 mil habitantes?
```

A partir do:

```sql
DBMS_CLOUD_AI.GENERATE
```

o Select AI pode interpretar a pergunta e gerar uma consulta SQL baseada nos dados disponíveis no Oracle.

Durante a implementação foram utilizados recursos como:

```text
showsql
```

para visualizar o SQL gerado pela IA, e:

```text
runsql
```

para executar a consulta e retornar seus resultados.

Os scripts e evidências dessa etapa estão em:

```text
mariana_oracle_apex/02_Select_AI/
```

A utilização de linguagem natural reduz a barreira técnica entre o usuário e os dados, permitindo explorar a base sem que todas as consultas precisem ser construídas manualmente.

---

# 📈 Dashboard VERTEX

A solução possui duas interfaces principais de exploração dos dados.

## Oracle APEX

O Dashboard desenvolvido no **Oracle APEX** apresenta uma visão consolidada dos principais indicadores da VERTEX.

Entre os dados disponíveis estão:

* município;
* população;
* profissionais de saúde;
* profissionais por 10 mil habitantes;
* produção ambulatorial;
* procedimentos realizados;
* indicadores derivados;
* informações relacionadas ao índice de subutilização.

Os materiais do dashboard estão disponíveis em:

```text
mariana_oracle_apex/03_Dashboard_APEX/
```

---

## 🌐 Dashboard Standalone

Também foi desenvolvido um **dashboard HTML standalone**, permitindo explorar os dados de maneira independente do ambiente APEX.

O painel apresenta:

* ranking de municípios por indício de subutilização;
* relação entre capacidade e procedimentos realizados;
* evolução temporal entre 2021 e 2024;
* seleção de diferentes indicadores;
* análise da qualidade dos dados;
* comparação entre municípios.

O dashboard utiliza a mesma fonte analítica:

```text
ADMIN.V_VERTEX_DASHBOARD
```

e segue a mesma metodologia utilizada no painel APEX.

### Acesso

**Repositório:**

```text
dashboard/index.html
```

**Deploy:**

https://vertex-challenge-oracle-fiap.netlify.app/

---

# 🔎 Fluxo de Análise

A VERTEX transforma os dados em uma sequência analítica:

```text
┌──────────────┐
│    DADOS     │
└──────┬───────┘
       ↓
┌──────────────┐
│  INTEGRAÇÃO  │
└──────┬───────┘
       ↓
┌──────────────┐
│ COMPARAÇÃO   │
└──────┬───────┘
       ↓
┌──────────────┐
│   INSIGHT    │
└──────┬───────┘
       ↓
┌──────────────┐
│ INVESTIGAÇÃO │
└──────────────┘
```

O objetivo não é produzir uma conclusão automática sobre cada município, mas **evidenciar padrões que possam orientar análises posteriores**.

---

# 📁 Estrutura do Repositório

```text
vertex-challenge-oracle-fiap/
│
├── airflow-vertex/
│   ├── dags/
│   │   ├── dag_vertex_batch.py
│   │   ├── dag_vertex_speed.py
│   │   └── vertex_common.py
│   ├── data/
│   ├── evidencias/
│   ├── logs/
│   ├── wallet/
│   ├── .env
│   └── docker-compose.yaml
│
├── dashboard/
│   └── index.html
│
├── docs/
│
├── graficos/
│
├── mariana_oracle_apex/
│   ├── 01_Banco_Oracle/
│   ├── 02_Select_AI/
│   ├── 03_Dashboard_APEX/
│   └── 04_Scripts_SQL/
│
├── notebooks/
│
├── sql/
│   ├── andreza_oficial/
│   └── arquivo/
│       └── ddl_serving_tables_deprecated.sql
│
├── modelo_preditivo/
│   └── dados/
│
└── README.md
```

---

# 🗂️ Organização dos Diretórios

| Diretório                    | Conteúdo                                              |
| ---------------------------- | ----------------------------------------------------- |
| `airflow-vertex/`            | Ambiente local e pipelines Apache Airflow             |
| `airflow-vertex/dags/`       | DAGs e funções compartilhadas dos pipelines           |
| `airflow-vertex/evidencias/` | Evidências das execuções do Airflow                   |
| `mariana_oracle_apex/`       | Componentes Oracle da solução                         |
| `01_Banco_Oracle/`           | Evidências e materiais do banco                       |
| `02_Select_AI/`              | Scripts e evidências do Select AI                     |
| `03_Dashboard_APEX/`         | Dashboard desenvolvido no Oracle APEX                 |
| `04_Scripts_SQL/`            | Scripts SQL utilizados na implementação               |
| `notebooks/`                 | Análises exploratórias                                |
| `graficos/`                  | Visualizações e análises produzidas durante o projeto |
| `dashboard/`                 | Dashboard HTML standalone                             |
| `docs/`                      | Documentação e materiais complementares               |
| `sql/andreza_oficial/`       | Modelo 3FN + dimensional da solução final             |
| `sql/arquivo/`               | DDLs históricos/depreciados                           |
| `modelo_preditivo/dados/`    | Dados utilizados pelo modelo preditivo                |

---

# 🛠️ Tecnologias

### Dados & Engenharia

* Python
* Pandas
* SQL
* Apache Airflow
* Docker
* Git
* GitHub

### Oracle

* Oracle Autonomous Database
* Oracle Database Actions
* Oracle SQL
* Oracle APEX
* Oracle Select AI
* DBMS_CLOUD_AI

---

# 📸 Evidências

As evidências da implementação estão organizadas por componente:

### Oracle Database

```text
mariana_oracle_apex/01_Banco_Oracle/
```

### Oracle Select AI

```text
mariana_oracle_apex/02_Select_AI/
```

### Oracle APEX

```text
mariana_oracle_apex/03_Dashboard_APEX/
```

### SQL

```text
mariana_oracle_apex/04_Scripts_SQL/
```

### Apache Airflow

```text
airflow-vertex/evidencias/
```

As evidências do Airflow incluem a disponibilização das DAGs, fluxos, estados de execução e logs relevantes.

---

# ⚠️ Limitações

A análise da VERTEX depende de bases públicas que possuem diferentes periodicidades, coberturas e características de registro.

Por isso, diferenças observadas entre municípios podem estar relacionadas, entre outros fatores, a:

* períodos com dados ausentes ou incompletos;
* diferenças na forma de registro dos atendimentos;
* alterações na cobertura dos sistemas;
* migração de municípios entre sistemas de informação;
* fluxo de pacientes entre municípios;
* características demográficas locais;
* características assistenciais não representadas diretamente no modelo.

A análise de qualidade dos dados identificou períodos com informações incompletas. Por esse motivo, os indicadores devem ser interpretados como **sinais para investigação**, considerando o contexto de cada município.

---

# 🚀 Próximos Passos

Entre as possibilidades de evolução da VERTEX estão:

* automatizar a carga mensal do modelo dimensional por meio do Airflow;
* ampliar a cobertura de municípios;
* ampliar a série histórica;
* incorporar novos indicadores de saúde;
* adicionar análises temporais mais avançadas;
* criar alertas automáticos;
* desenvolver modelos preditivos;
* ampliar as consultas em linguagem natural;
* incorporar novos mecanismos de análise e priorização de regiões.

---

# 🎓 Contexto Acadêmico

**Challenge Oracle & FIAP 2026**

**Turma:** 1TSCPF

**Projeto:** VERTEX

### Dados que conectam necessidade e capacidade.

A VERTEX busca transformar dados públicos de saúde em informação acessível, integrando diferentes fontes e indicadores para apoiar análises orientadas por evidências.

---

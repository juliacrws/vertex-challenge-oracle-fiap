# VERTEX — Challenge Oracle & FIAP 2026 (1TSCPF)

**Painel Inteligente de Acesso Hospitalar e Perfil de Atendimento**

A **VERTEX** é uma solução de apoio à análise de dados de saúde pública que integra informações de população, profissionais, estabelecimentos e produção ambulatorial para evidenciar possíveis desequilíbrios entre **necessidade da população** e **capacidade assistencial disponível**.

O projeto foi desenvolvido para o **Challenge Oracle & FIAP 2026**, combinando engenharia de dados, Apache Airflow, Oracle Autonomous Database, SQL, Oracle APEX e Oracle Select AI.

---

## 👥 Equipe

* **Andreza do Livramento Silva** — RM570964
* **Diego Gaspar** — RM568924
* **João Guilherme Cavalcante Matos** — RM570975
* **Julia de Moraes Barbosa** — RM572997
* **Mariana Ayumi Dantas Kuramitsu** — RM572788

---

## 🏥 Problema de negócio

No contexto da saúde pública, a indisponibilidade de atendimento nem sempre significa apenas falta absoluta de recursos.

Em muitos casos, o desafio está em entender **como população, profissionais, estabelecimentos e produção estão distribuídos entre os municípios**.

Essas informações existem em bases públicas, mas, quando analisadas separadamente, dificultam a identificação de situações como:

* baixa disponibilidade relativa de profissionais;
* produção ambulatorial incompatível com o porte populacional;
* capacidade potencialmente subutilizada;
* regiões com carência estrutural;
* diferenças relevantes entre municípios que não aparecem em valores absolutos.

A VERTEX foi criada para transformar esses dados dispersos em uma visão integrada, comparável e acessível.

---

## 🎯 Objetivo da solução

A VERTEX busca apoiar gestores e analistas na identificação de desigualdades e possíveis desequilíbrios na utilização dos recursos de saúde.

A solução permite relacionar indicadores e observar os municípios sob diferentes perspectivas, transformando dados públicos em informações que apoiam investigação e tomada de decisão.

Os resultados devem ser interpretados como **indicadores de apoio à análise**, e não como diagnóstico definitivo de eficiência ou ineficiência de um município.

---

## 🏗️ Arquitetura da solução

```text
Fontes públicas de dados
        ↓
Apache Airflow
Batch Layer + Speed Layer
        ↓
Processamento e consolidação
        ↓
Oracle Autonomous Database
        ↓
SQL + Views analíticas
        ↓
Oracle Select AI
        ↓
Oracle APEX / Dashboard VERTEX
        ↓
Comparação → Insight → Decisão
```

A arquitetura foi organizada segundo uma abordagem inspirada em **Lambda Architecture**, com fluxos independentes para dados de diferentes cadências.

---

## ⚙️ Batch Layer

A DAG `pipeline_vertex_batch`, definida em:

```text
airflow-vertex/dags/dag_vertex_batch.py
```

é executada mensalmente.

Ela processa dados relacionados ao **SIA/SUS e IBGE**, aguarda uma execução válida da Speed Layer e então realiza a carga analítica e o cálculo do índice final de subutilização.

Fluxo principal:

```text
Ingestão SIA
    ↓
Transformação SIA + IBGE
    ↓
Sincronização com Speed Layer
    ↓
Carga analítica
    ↓
Índice final de subutilização
```

A Batch Layer acompanha a periodicidade de atualização dos dados de produção ambulatorial.

---

## ⚡ Speed Layer

A DAG `pipeline_vertex_speed`, definida em:

```text
airflow-vertex/dags/dag_vertex_speed.py
```

possui execução diária.

Ela trabalha com informações do **CNES**, representando uma camada de atualização mais frequente para dados relacionados à capacidade instalada e recursos humanos.

Fluxo principal:

```text
Ingestão CNES
    ↓
Transformação CNES
```

As funções compartilhadas pelos pipelines estão centralizadas em:

```text
airflow-vertex/dags/vertex_common.py
```

A separação entre Batch Layer e Speed Layer permite tratar fontes com diferentes frequências de atualização.

---

## 📊 Fontes e dimensões analisadas

A solução trabalha com dados públicos relacionados a:

* municípios;
* população;
* profissionais de saúde;
* estabelecimentos;
* produção ambulatorial.

Esses dados são integrados para permitir análises relativas, evitando depender apenas de números absolutos.

Um dos indicadores utilizados é:

```text
Profissionais por 10 mil habitantes
```

Esse indicador permite comparar municípios de diferentes portes populacionais de forma mais adequada.

---

## 📐 Índice de subutilização

A versão utilizada na solução final é baseada na normalização **Min-Max** dos componentes analíticos.

De forma conceitual, o índice compara:

```text
capacidade normalizada
-
produção ambulatorial normalizada
```

A finalidade do índice é destacar municípios que merecem investigação adicional por apresentarem possível diferença entre capacidade disponível e utilização observada.

A tabela utilizada no ambiente Oracle é:

```text
INDICE_SUBUTILIZACAO_VERTEX
```

Os scripts SQL relacionados à implementação utilizada no ambiente Oracle estão disponíveis em:

```text
mariana_oracle_apex/04_Scripts_SQL/
```

O diretório:

```text
sql/andreza_oficial/
```

permanece no repositório como uma abordagem analítica complementar, com modelagem mais granular e tratamento adicional de qualidade dos dados.

Essa modelagem não corresponde ao schema utilizado pelo dashboard final em produção.

---

## 🗄️ Oracle Autonomous Database

O **Oracle Autonomous Database** é a principal camada de persistência e consulta da solução.

Nele são mantidos os dados estruturados utilizados pelo dashboard e pelas consultas com inteligência artificial.

Os materiais e evidências referentes ao banco estão organizados em:

```text
mariana_oracle_apex/01_Banco_Oracle/
```

O Oracle é responsável por armazenar e disponibilizar os dados consolidados consumidos pelas demais camadas da solução.

---

## 🧠 Oracle Select AI

Além da análise visual, a VERTEX utiliza o **Oracle Select AI** para permitir que perguntas sobre a base sejam realizadas em linguagem natural.

Exemplo:

```text
Quais municípios possuem menor quantidade de profissionais por 10 mil habitantes?
```

Por meio do:

```sql
DBMS_CLOUD_AI.GENERATE
```

o Select AI interpreta a pergunta e pode gerar automaticamente uma consulta SQL sobre os dados estruturados no Oracle.

Durante a implementação foram utilizados modos como:

```text
showsql
```

para visualizar o SQL produzido pela inteligência artificial, e:

```text
runsql
```

para executar a consulta e retornar o resultado.

Os scripts e evidências dessa etapa estão disponíveis em:

```text
mariana_oracle_apex/02_Select_AI/
```

Essa funcionalidade reduz a barreira técnica entre o dado e o usuário que precisa realizar uma análise.

---

## 📈 Dashboard VERTEX

O dashboard desenvolvido no **Oracle APEX** apresenta uma visão consolidada dos principais indicadores utilizados pela solução.

Entre as informações analisadas estão:

* município;
* população;
* quantidade de profissionais;
* profissionais por 10 mil habitantes;
* produção e procedimentos ambulatoriais;
* indicadores derivados utilizados pela VERTEX.

A proposta é permitir que os indicadores sejam observados de forma integrada e comparável, facilitando a identificação de padrões e possíveis desequilíbrios.

Os materiais e o link da aplicação estão disponíveis em:

```text
mariana_oracle_apex/03_Dashboard_APEX/
```

---

## 🌬️ Apache Airflow

O **Apache Airflow** é utilizado para orquestrar o pipeline de dados da VERTEX.

O ambiente local está organizado em:

```text
airflow-vertex/
```

Esse diretório contém os arquivos necessários para execução do ambiente, incluindo:

* configuração Docker;
* DAGs;
* dados utilizados no ambiente;
* logs;
* arquivos de conexão com o Oracle;
* arquivos auxiliares de execução.

As evidências visuais das execuções estão organizadas em:

```text
airflow-vertex/evidencias/
```

As DAGs principais mantidas no projeto são:

```text
airflow-vertex/dags/dag_vertex_batch.py
airflow-vertex/dags/dag_vertex_speed.py
airflow-vertex/dags/vertex_common.py
```

---

## 🔎 Fluxo de análise da VERTEX

A proposta analítica pode ser resumida em quatro etapas:

```text
DADOS
  ↓
COMPARAÇÃO
  ↓
INSIGHT
  ↓
DECISÃO
```

Primeiro, os dados provenientes de diferentes fontes são integrados e tratados.

Depois, indicadores relativos permitem comparar municípios de diferentes portes.

Essas comparações ajudam a destacar possíveis desigualdades ou desequilíbrios.

Por fim, os resultados servem como ponto de partida para investigação e apoio à tomada de decisão.

---

## 📂 Estrutura do repositório

```text
vertex-challenge-oracle-fiap/
│
├── airflow-vertex/
│   ├── dags/
│   ├── data/
│   ├── evidencias/
│   ├── logs/
│   ├── wallet/
│   ├── .env
│   └── docker-compose.yaml
│
├── dashboard/
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
│   └── DEPRECATED_ddl_serving_tables.sql
│
└── README.md
```

---

## 🗂️ Conteúdo por área

| Diretório                               | Conteúdo principal                                                     |
| --------------------------------------- | ---------------------------------------------------------------------- |
| `airflow-vertex/`                       | Ambiente local de execução do Apache Airflow                           |
| `mariana_oracle_apex/`                  | Banco Oracle, Select AI, Dashboard APEX e scripts SQL da solução final |
| `notebooks/`                            | Análise exploratória dos dados                                         |
| `graficos/`                             | Gráficos e rankings produzidos durante a análise                       |
| `dashboard/`                            | Scripts analíticos desenvolvidos durante o projeto                     |
| `docs/`                                 | Documentação de governança, ética e materiais complementares           |
| `sql/andreza_oficial/`                  | Modelagem complementar e análise de qualidade de dados                 |
| `sql/DEPRECATED_ddl_serving_tables.sql` | Implementação antiga mantida apenas como histórico                     |

---

## 🛠️ Tecnologias utilizadas

* Oracle Autonomous Database
* Oracle Database Actions
* Oracle SQL
* Oracle APEX
* Oracle Select AI
* DBMS_CLOUD_AI
* Apache Airflow
* Docker
* Python
* Pandas
* Git
* GitHub

---

## 📸 Evidências

As principais evidências de implementação do projeto estão distribuídas entre os diretórios da solução.

### Oracle Database

```text
mariana_oracle_apex/01_Banco_Oracle/
```

### Oracle Select AI

```text
mariana_oracle_apex/02_Select_AI/
```

### Dashboard Oracle APEX

```text
mariana_oracle_apex/03_Dashboard_APEX/
```

### Scripts SQL

```text
mariana_oracle_apex/04_Scripts_SQL/
```

### Apache Airflow

```text
airflow-vertex/evidencias/
```

As evidências do Airflow demonstram a disponibilização das DAGs, seus fluxos, estados de execução e logs relevantes.

---

## ⚠️ Limitações conhecidas

A VERTEX utiliza dados públicos provenientes de sistemas com diferentes periodicidades e características de registro.

Por isso, diferenças entre municípios podem estar relacionadas também a fatores como:

* períodos com dados ausentes ou incompletos;
* alterações na forma de registro dos atendimentos;
* diferenças de cobertura entre sistemas;
* migração de municípios para outros sistemas de informação;
* fluxo de pacientes entre municípios;
* características demográficas e assistenciais locais não representadas diretamente no modelo.

Durante a análise de qualidade foram identificadas situações de ausência de dados que reforçam a necessidade de interpretar os resultados como **sinais para investigação**, e não como conclusões isoladas.

---

## 🚀 Próximos passos

Como evolução, a VERTEX pode incorporar:

* ampliação da cobertura de municípios;
* ampliação da série histórica;
* novos indicadores de saúde;
* análises temporais;
* alertas automáticos;
* modelos preditivos;
* novas consultas utilizando inteligência artificial;
* mecanismos adicionais de priorização de regiões.

---

## 🎓 Contexto acadêmico

Projeto desenvolvido para o:

**Challenge Oracle & FIAP 2026**

Turma:

**1TSCPF**

Projeto:

**VERTEX**

### Dados que conectam necessidade e capacidade.

A VERTEX busca transformar dados públicos de saúde em informação acessível, integrando diferentes indicadores para apoiar análises e decisões orientadas por evidências.

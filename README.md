# VERTEX — Challenge Oracle & FIAP 2026 (1TSCPF)

Análise de Abandono Indireto de Atendimentos Ambulatoriais no SUS — Painel
Inteligente de Acesso Hospitalar e Perfil de Atendimento.

## Equipe
Andreza do Livramento Silva (RM570964) · Diego Gaspar (RM568924) ·
João Guilherme Cavalcante Matos (RM570975) · Julia de Moraes Barbosa (RM572997) ·
Mariana Ayumi Dantas Kuramitsu (RM572788)

## ✅ Decisão final sobre o schema/índice (atualizada em 09/09/2026)

Duas versões do banco/índice foram desenvolvidas em paralelo (esperado, dado
o trabalho distribuído):

1. **Versão original** (Julia + João): schema agregado por ano, índice por
   normalização min-max (`capacidade_norm − APC_norm`).
2. **Versão alternativa** (Andreza): schema 3FN + dimensional com
   granularidade mensal, índice por razão (`APC / (peso_p·PPC + peso_e·EPC)`),
   com tratamento explícito de dados incompletos.

**Em 08/09 recomendamos migrar para a versão da Andreza** por ser mais
rigorosa. **Em 09/09 revertemos essa decisão**: a Mariana já tinha construído,
sobre a versão original, um **Dashboard público no Oracle APEX**
(`mariana_oracle_apex/03_Dashboard_APEX/`, link confirmado funcionando em aba
anônima) e **3 consultas Select AI reais** (`mariana_oracle_apex/02_Select_AI/`),
com o Oracle Autonomous Database já carregado (`mariana_oracle_apex/01_Banco_Oracle/`).
Migrar de schema a 4 dias da entrega, com essas duas peças já públicas e
funcionando, era um risco desnecessário — então a **versão original
(min-max) é a oficial**, e o pipeline (`dags/vertex_common.py`) foi
revertido para ela.

- **Link público do dashboard**: ver `mariana_oracle_apex/03_Dashboard_APEX/link publico pros dashs.txt`
- **Schema oficial em produção**: tabela `INDICE_SUBUTILIZACAO_VERTEX` (ver `mariana_oracle_apex/04_Scripts_SQL/`)
- O trabalho da Andreza (`sql/andreza_oficial/`) continua no repositório como
  **validação complementar de qualidade de dados** — ela identificou de
  verdade um mês inteiro (03/2024) ausente no SIA/SUS de SP e 3 municípios
  migrados para o e-SUS APS, o que vale citar como limitação conhecida no
  PPT/vídeo, sem exigir migração do sistema já no ar.
- O documento do João (Data Ethics) **não precisa mudar** — a fórmula que ele
  documentou é a que está realmente em produção.

## Estrutura do repositório

| Pasta | Conteúdo | Responsável |
|---|---|---|
| `dags/` | Pipeline Airflow (Arquitetura Lambda): `vertex_common.py`, `dag_vertex_batch.py` (mensal), `dag_vertex_speed.py` (diário) | Julia |
| `mariana_oracle_apex/` | **Sistema em produção**: banco Oracle, Select AI (3 consultas reais), Dashboard APEX público, scripts SQL da view oficial | Mariana |
| `sql/andreza_oficial/` | Modelagem alternativa mais rigorosa (3FN + dimensional + tratamento de dados incompletos) — validação complementar, não está em produção | Andreza |
| `sql/DEPRECATED_ddl_serving_tables.sql` | Primeira tentativa minha de schema — não usar | Julia |
| `notebooks/` | AED completa: distribuições, outliers, correlação, evolução temporal 2021-2024 | Diego |
| `graficos/` | 3 gráficos de destaque + rankings (menor cobertura, queda estrutural, dupla carência) | Diego |
| `dashboard/` | Script standalone do índice de abandono indireto (`indice_abandono_indireto.py`, já corrigido) | Julia |
| `docs/` | Documentação de governança/ética (COBIT, Oracle Ethics Shield) — fórmula já bate com a produção | João Guilherme |

## Ainda faltando pra Sprint 4 (checklist)

- [x] Link da aplicação funcionando (Dashboard APEX da Mariana, confirmado público)
- [x] Select AI com 3 consultas reais (Mariana)
- [x] Fontes técnicas de todo mundo reunidas neste repositório
- [ ] Vídeo pitch (até 5 min, YouTube) — usar o dashboard da Mariana na demonstração
- [ ] Planilha `Informacoes_Finais_Projeto_Integrantes.xlsx`
- [ ] Atualizar o PPT com o link real do dashboard e os prints do Select AI
- [ ] Zip final: `EC_Sprint_4_1TSCPF_solucaofinal_VERTEX_<nome_grupo>.zip`

## Duas lentes analíticas complementares (mantido — ainda válido)

- **Índice de subutilização** (schema oficial Andreza): municípios com
  capacidade instalada alta mas uso real baixo relativo — indício de
  abandono/barreira de acesso apesar de ter estrutura.
- **AED (Diego)**: municípios com carência estrutural real — poucos
  profissionais/estabelecimentos per capita, inclusive em queda 2021→2024.

Nenhum município aparece nos dois rankings ao mesmo tempo — esperado, já que
capturam fenômenos diferentes (excesso ocioso vs. escassez real).


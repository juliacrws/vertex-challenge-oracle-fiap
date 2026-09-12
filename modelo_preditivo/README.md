# Modelo Preditivo — VERTEX (v2)

## Objetivo
Ir além do índice por normalização (min-max) e testar, com rigor
estatístico, se a subutilização pode ser explicada a partir da
capacidade instalada.

## Metodologia
- **Alvo**: log(APC) — log-transformado por causa da cauda longa da
  distribuição (poucos municípios com valores muito altos distorciam o
  ajuste em escala real).
- **Features**: EPC, PPC, log(população), leitos por 1.000 habitantes,
  interação EPC×PPC, variação % de EPC e de PPC entre 2021 e 2024
  (tendência estrutural, mesma lógica da análise do Diego, calculada
  aqui a partir da série completa do pipeline).
- **Modelos comparados**: Regressão Linear, Ridge, Lasso, Random Forest,
  Gradient Boosting — todos com validação cruzada (5 folds).
- **Tuning**: GridSearchCV em Random Forest e Gradient Boosting
  (profundidade, nº de árvores, taxa de aprendizado, mínimo de amostras
  por folha).
- **Importância de variáveis**: por permutação (mais confiável que a
  importância bruta de árvores, que tende a inflar variáveis com mais
  granularidade).

## Resultado
Melhor modelo: **Random Forest tunado**, R² = **0,223** (log-APC),
contra 0,176 da primeira versão (regressão linear simples, sem tuning).

## Achado principal
**PPC (profissionais por habitante) é de longe a variável mais
importante (0,38 de importância por permutação) — mais que 10x o peso
de EPC (estabelecimentos por habitante, ~0,002).** Isso sugere um
achado relevante para a gestão pública: **ter prédio/posto de saúde
por si só quase não move a utilização real — o gargalo está em
profissionais disponíveis, não em infraestrutura física.**

Ainda assim, mesmo com as variáveis mais fortes, o modelo explica só
~22% da variação real — reforçando que a maior parte do fenômeno de
subutilização não é explicada pela oferta de estrutura/pessoal, e sim
por fatores de demanda (acesso, barreiras, comportamento) que estão
fora do escopo dos dados públicos disponíveis. Isso valida a proposta
central do VERTEX: o índice existe justamente para sinalizar esse gap
não-explicado, não para substituí-lo por uma previsão perfeita.

Municípios como **Guaratinguetá**, **São Carlos** e **Lorena** aparecem
tanto nesta versão quanto na v1, e também no índice original (min-max)
— convergência entre três abordagens analíticas independentes.

## Arquivos
- `modelo.py` — código completo (reprodutível)
- `resultado_modelo_preditivo.csv` — ranking completo (496 municípios, pop. ≥ 5.000)
- `real_vs_previsto.png`, `importancia_variaveis.png`, `top10_subutilizacao_ml.png`

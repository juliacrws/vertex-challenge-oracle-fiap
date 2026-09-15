import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import cross_val_predict, cross_validate, KFold, GridSearchCV
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.inspection import permutation_importance

SERVING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")

anual = pd.read_csv(f"{SERVING}/indicadores_anuais_epc_ppc.csv")
apc = pd.read_csv(f"{SERVING}/indicador_periodo_apc.csv")

# ---------------------------------------------------------------
# Feature nova 1: variação da estrutura entre 2021 e 2024 (tendência)
# ---------------------------------------------------------------
primeiro_ano = anual[anual["ano"] == anual["ano"].min()].set_index("id_municipio")
ultimo_ano_df = anual[anual["ano"] == anual["ano"].max()].set_index("id_municipio")
variacao_epc = ((ultimo_ano_df["EPC"] - primeiro_ano["EPC"]) / primeiro_ano["EPC"].replace(0, np.nan)) * 100
variacao_ppc = ((ultimo_ano_df["PPC"] - primeiro_ano["PPC"]) / primeiro_ano["PPC"].replace(0, np.nan)) * 100

recente = ultimo_ano_df.reset_index()
recente["variacao_epc_pct"] = recente["id_municipio"].map(variacao_epc)
recente["variacao_ppc_pct"] = recente["id_municipio"].map(variacao_ppc)

# ---------------------------------------------------------------
# Feature nova 2: leitos per capita + interação EPC x PPC
# ---------------------------------------------------------------
recente["leitos_per_1000"] = (recente["total_leitos"] / recente["populacao"]) * 1000
recente["epc_x_ppc"] = recente["EPC"] * recente["PPC"]

df = apc.merge(
    recente[["id_municipio", "EPC", "PPC", "leitos_per_1000", "epc_x_ppc",
             "variacao_epc_pct", "variacao_ppc_pct"]],
    on="id_municipio", how="left",
)
df = df.dropna(subset=["EPC", "PPC", "APC", "populacao", "leitos_per_1000",
                        "variacao_epc_pct", "variacao_ppc_pct"])
df = df[df["populacao"] >= 5000]
# clip de outliers extremos de variação (erro de base pequena) pra não explodir o modelo
df["variacao_epc_pct"] = df["variacao_epc_pct"].clip(-100, 200)
df["variacao_ppc_pct"] = df["variacao_ppc_pct"].clip(-100, 200)
print(f"Dataset final: {len(df)} municípios, {df.shape[1]} colunas")

df["log_populacao"] = np.log1p(df["populacao"])
# ALVO em log — a distribuição de APC tem cauda longa (poucos municípios com valores muito altos)
df["log_APC"] = np.log1p(df["APC"])

features = ["EPC", "PPC", "log_populacao", "leitos_per_1000", "epc_x_ppc",
            "variacao_epc_pct", "variacao_ppc_pct"]
X = df[features].values
y_log = df["log_APC"].values
y_real = df["APC"].values

kf = KFold(n_splits=5, shuffle=True, random_state=42)

modelos = {
    "Regressão Linear": LinearRegression(),
    "Ridge (regularizado)": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "Lasso (regularizado)": make_pipeline(StandardScaler(), Lasso(alpha=0.01)),
    "Random Forest": RandomForestRegressor(random_state=42),
    "Gradient Boosting": GradientBoostingRegressor(random_state=42),
}

print("\n=== ETAPA 1: comparação com alvo em log(APC), hiperparâmetros padrão ===")
for nome, modelo in modelos.items():
    scores = cross_validate(modelo, X, y_log, cv=kf, scoring="r2")
    print(f"{nome:24s} R² médio = {scores['test_score'].mean():.3f}  (+/- {scores['test_score'].std():.3f})")

# ---------------------------------------------------------------
# ETAPA 2: GridSearch nos dois modelos de árvore (os que mais se beneficiam de tuning)
# ---------------------------------------------------------------
print("\n=== ETAPA 2: GridSearchCV (Random Forest e Gradient Boosting) ===")

grid_rf = GridSearchCV(
    RandomForestRegressor(random_state=42),
    param_grid={"n_estimators": [200, 500], "max_depth": [3, 5, 8], "min_samples_leaf": [2, 5, 10]},
    cv=kf, scoring="r2", n_jobs=-1,
)
grid_rf.fit(X, y_log)
print(f"Random Forest — melhores params: {grid_rf.best_params_} | R² = {grid_rf.best_score_:.3f}")

grid_gb = GridSearchCV(
    GradientBoostingRegressor(random_state=42),
    param_grid={"n_estimators": [100, 300], "max_depth": [2, 3], "learning_rate": [0.03, 0.05, 0.1]},
    cv=kf, scoring="r2", n_jobs=-1,
)
grid_gb.fit(X, y_log)
print(f"Gradient Boosting — melhores params: {grid_gb.best_params_} | R² = {grid_gb.best_score_:.3f}")

candidatos = {
    "Regressão Linear": (LinearRegression(), scores),
    "Random Forest (tunado)": (grid_rf.best_estimator_, grid_rf.best_score_),
    "Gradient Boosting (tunado)": (grid_gb.best_estimator_, grid_gb.best_score_),
}
melhor_nome = max(
    ["Random Forest (tunado)", "Gradient Boosting (tunado)"],
    key=lambda k: candidatos[k][1],
)
melhor_modelo = candidatos[melhor_nome][0]
melhor_r2 = candidatos[melhor_nome][1]
print(f"\nMelhor modelo após tuning: {melhor_nome} (R² = {melhor_r2:.3f})")

# Predições honestas fora da amostra, já no espaço real (des-log)
y_pred_log = cross_val_predict(melhor_modelo, X, y_log, cv=kf)
df["APC_previsto"] = np.expm1(y_pred_log)
df["residuo"] = df["APC"] - df["APC_previsto"]

melhor_modelo.fit(X, y_log)

# Importância por permutação (mais confiável que feature_importances_ bruto)
perm = permutation_importance(melhor_modelo, X, y_log, n_repeats=20, random_state=42, scoring="r2")
importancias = dict(zip(features, perm.importances_mean))
print("\nImportância por permutação:")
for feat, imp in sorted(importancias.items(), key=lambda x: -x[1]):
    print(f"  {feat:20s} {imp:.4f}")

df_rank = df.sort_values("residuo").reset_index(drop=True)
print("\n=== TOP 10 municípios — maior subutilização (modelo aprimorado) ===")
print(df_rank[["nome_municipio", "EPC", "PPC", "APC", "APC_previsto", "residuo"]].head(10).round(2).to_string(index=False))

df_rank.to_csv("resultado_modelo_preditivo_v2.csv", index=False)

# ---- Gráficos ----
fig, ax = plt.subplots(figsize=(6, 5))
ax.scatter(df["APC_previsto"], df["APC"], alpha=0.4, color="#1E2761")
lims = [0, max(df["APC"].max(), df["APC_previsto"].max())]
ax.plot(lims, lims, "r--", label="Previsão perfeita")
ax.set_xlabel("APC previsto pelo modelo")
ax.set_ylabel("APC real")
ax.set_title(f"Real vs. Previsto — {melhor_nome}\nR² (em log-APC) = {melhor_r2:.3f}")
ax.legend()
plt.tight_layout()
plt.savefig("real_vs_previsto_v2.png", dpi=150)
plt.close()

fig, ax = plt.subplots(figsize=(6, 4))
nomes_feat = [f for f, _ in sorted(importancias.items(), key=lambda x: x[1])]
valores_feat = [importancias[f] for f in nomes_feat]
ax.barh(nomes_feat, valores_feat, color="#1E2761")
ax.set_title("Importância das variáveis (permutação)")
plt.tight_layout()
plt.savefig("importancia_variaveis_v2.png", dpi=150)
plt.close()

top10 = df_rank.head(10)
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(top10["nome_municipio"][::-1], -top10["residuo"][::-1], color="#B33B3B")
ax.set_xlabel("Gap: quanto o município atendeu A MENOS do que o modelo previa")
ax.set_title("Top 10 municípios — Índice Preditivo de Subutilização (v2)")
plt.tight_layout()
plt.savefig("top10_subutilizacao_ml_v2.png", dpi=150)
plt.close()

print("\nArquivos gerados: resultado_modelo_preditivo_v2.csv, real_vs_previsto_v2.png, importancia_variaveis_v2.png, top10_subutilizacao_ml_v2.png")

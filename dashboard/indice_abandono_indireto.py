"""
==============================================================================
VERTEX - Índice de Abandono Indireto de Atendimentos Ambulatoriais no SUS
Challenge Oracle & FIAP 2026 - 1TSCPF/1TSCPV/1TSCPW
Disciplina: Building Data-Driven Applications for Data Science
==============================================================================

O QUE ESTE SCRIPT FAZ:
Lê dois arquivos de indicadores de saúde municipal já calculados:
  - indicadores_anuais_epc_ppc.csv  (EPC e PPC, por município e ano)
  - indicador_periodo_apc.csv       (APC, por município, período total)

E resolve o problema de negócio central do VERTEX: responder "quais
municípios têm capacidade instalada (estabelecimentos e profissionais)
desproporcional ao volume de atendimentos realizados?", construindo um
índice composto (IAI) e um ranking dos municípios mais críticos.

LÓGICA DO ÍNDICE:
Um município com capacidade alta (EPC/PPC altos) e utilização baixa (APC
baixo) é o padrão que caracteriza abandono/subutilização indireta: a
estrutura de saúde existe, mas a população não está sendo atendida na
proporção esperada. Para comparar essas três grandezas, que têm escalas
muito diferentes, cada indicador é normalizado (min-max, 0 a 1) antes de
compor o índice:

    IAI = média(EPC_norm, PPC_norm) - APC_norm

Quanto maior o IAI, maior o sinal de abandono indireto (capacidade ociosa).
Quanto menor (mais negativo), maior a utilização em relação à capacidade
disponível.
==============================================================================
"""

import argparse
import os
import sys
import pandas as pd


ARQUIVO_EPC_PPC = "indicadores_anuais_epc_ppc.csv"
ARQUIVO_APC = "indicador_periodo_apc.csv"
ARQUIVO_SAIDA = "indice_abandono_indireto.csv"


def carregar_dados(diretorio):
    """
    Carrega os dois arquivos de indicadores gerados pelo pipeline VERTEX
    e valida se as colunas essenciais estão presentes. Lança erro claro
    se algum arquivo estiver ausente ou corrompido, em vez de falhar com
    uma exceção genérica do pandas.
    """
    caminho_epc_ppc = os.path.join(diretorio, ARQUIVO_EPC_PPC)
    caminho_apc = os.path.join(diretorio, ARQUIVO_APC)

    for caminho in (caminho_epc_ppc, caminho_apc):
        if not os.path.isfile(caminho):
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho}. "
                f"Execute o pipeline VERTEX (Airflow) antes de rodar esta aplicação."
            )

    # Antes, um arquivo corrompido (encoding errado, separador trocado,
    # arquivo vazio) fazia o pandas estourar uma exceção que não era
    # capturada aqui embaixo, mesmo o docstring prometendo cobrir esse
    # caso. Agora qualquer erro de leitura vira um ValueError com uma
    # mensagem clara, que o `except` do main() já sabe tratar.
    try:
        epc_ppc = pd.read_csv(caminho_epc_ppc)
        apc = pd.read_csv(caminho_apc)
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as erro:
        raise ValueError(
            f"Não foi possível ler um dos arquivos de indicadores — verifique se o "
            f"encoding e o separador estão corretos (detalhe: {erro})"
        ) from erro

    # "populacao" foi removida da validação: o índice usa apenas EPC, PPC e
    # APC (já são taxas per capita, a população não entra em nenhum cálculo
    # deste script) — exigi-la aqui só criaria uma falha falsa se o pipeline
    # um dia parar de exportar essa coluna sem motivo real para quebrar.
    colunas_esperadas_epc_ppc = {"id_municipio", "ano", "EPC", "PPC"}
    colunas_esperadas_apc = {"id_municipio", "nome_municipio", "APC"}
    faltando_1 = colunas_esperadas_epc_ppc - set(epc_ppc.columns)
    faltando_2 = colunas_esperadas_apc - set(apc.columns)
    if faltando_1:
        raise ValueError(f"Colunas ausentes em {ARQUIVO_EPC_PPC}: {faltando_1}")
    if faltando_2:
        raise ValueError(f"Colunas ausentes em {ARQUIVO_APC}: {faltando_2}")

    print(f"[OK] {ARQUIVO_EPC_PPC}: {len(epc_ppc)} linhas carregadas.")
    print(f"[OK] {ARQUIVO_APC}: {len(apc)} linhas carregadas.")
    return epc_ppc, apc


def preparar_base_mais_recente(epc_ppc):
    """
    EPC e PPC têm quebra anual; para compor o índice com o APC (que é um
    valor de período único), utiliza-se o ano mais recente disponível de
    cada município como retrato mais atual da capacidade instalada.
    """
    ano_mais_recente = epc_ppc["ano"].max()
    base = epc_ppc[epc_ppc["ano"] == ano_mais_recente].copy()
    print(f"[INFO] Usando o ano {ano_mais_recente} como referência de capacidade instalada "
          f"({len(base)} municípios).")
    return base


def normalizar_min_max(serie):
    """Normaliza uma série numérica para o intervalo [0, 1]. Protege contra
    divisão por zero quando todos os valores da série são iguais."""
    minimo, maximo = serie.min(), serie.max()
    amplitude = maximo - minimo
    if amplitude == 0:
        return serie * 0
    return (serie - minimo) / amplitude


def calcular_indice_abandono(epc_ppc, apc):
    """
    Junta as duas fontes, normaliza os três indicadores e calcula o
    Índice de Abandono Indireto (IAI) por município. Retorna o DataFrame
    ordenado do maior (mais crítico) para o menor IAI.
    """
    base_capacidade = preparar_base_mais_recente(epc_ppc)

    dados = base_capacidade.merge(
        apc[["id_municipio", "nome_municipio", "APC"]],
        on="id_municipio",
        how="inner",
    )

    sem_correspondencia = len(base_capacidade) - len(dados)
    if sem_correspondencia:
        print(f"[AVISO] {sem_correspondencia} municípios sem correspondência entre as duas bases.")

    dados["EPC_norm"] = normalizar_min_max(dados["EPC"])
    dados["PPC_norm"] = normalizar_min_max(dados["PPC"])
    dados["APC_norm"] = normalizar_min_max(dados["APC"])

    dados["IAI"] = ((dados["EPC_norm"] + dados["PPC_norm"]) / 2) - dados["APC_norm"]

    dados = dados.sort_values("IAI", ascending=False).reset_index(drop=True)
    dados.insert(0, "ranking", dados.index + 1)

    return dados[
        ["ranking", "id_municipio", "nome_municipio", "ano", "EPC", "PPC", "APC", "IAI"]
    ]


def exibir_resumo(resultado, top_n):
    """Imprime no console os N municípios com maior sinal de abandono
    indireto (mais críticos) e os N com menor sinal (mais equilibrados)."""
    print(f"\n=== TOP {top_n} municípios com MAIOR sinal de abandono indireto ===")
    print(resultado.head(top_n).to_string(index=False))

    print(f"\n=== TOP {top_n} municípios com MENOR sinal de abandono indireto ===")
    print(resultado.tail(top_n).sort_values("IAI").to_string(index=False))

    print(f"\n[RESUMO] IAI médio: {resultado['IAI'].mean():.4f} | "
          f"IAI máximo: {resultado['IAI'].max():.4f} | "
          f"IAI mínimo: {resultado['IAI'].min():.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Calcula o Índice de Abandono Indireto (IAI) do projeto VERTEX "
                    "a partir dos indicadores EPC, PPC e APC gerados pelo pipeline."
    )
    parser.add_argument(
        "--diretorio", default=".",
        help="Diretório onde estão os CSVs de indicadores (padrão: diretório atual)."
    )
    parser.add_argument(
        "--top", type=int, default=10,
        help="Quantidade de municípios a exibir no ranking (padrão: 10)."
    )
    parser.add_argument(
        "--saida", default=ARQUIVO_SAIDA,
        help=f"Nome do arquivo CSV de saída (padrão: {ARQUIVO_SAIDA})."
    )
    args = parser.parse_args()

    try:
        epc_ppc, apc = carregar_dados(args.diretorio)
        resultado = calcular_indice_abandono(epc_ppc, apc)
        exibir_resumo(resultado, args.top)

        caminho_saida = os.path.join(args.diretorio, args.saida)
        resultado.to_csv(caminho_saida, index=False)
        print(f"\n[OK] Ranking completo salvo em: {caminho_saida} ({len(resultado)} municípios).")

    except (FileNotFoundError, ValueError) as erro:
        print(f"[ERRO] {erro}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

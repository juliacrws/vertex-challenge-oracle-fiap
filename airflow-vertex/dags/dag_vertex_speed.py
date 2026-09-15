"""
==============================================================================
VERTEX - Speed Layer (Arquitetura Lambda)
Challenge Oracle & FIAP 2026 - 1TSCPF/1TSCPV/1TSCPW

Roda diariamente, refletindo a natureza mais volátil da capacidade
instalada (CNES-ST) e dos recursos humanos (CNES-PF) frente ao ciclo
mensal do SIA/SUS. É essa cadência independente e mais frequente que
caracteriza a Speed Layer na Arquitetura Lambda — corrige o ponto do
feedback da Sprint 3 em que Batch e Speed rodavam na mesma DAG mensal.
==============================================================================
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

from vertex_common import ingestao_cnes, transformar_cnes

default_args = {
    "owner": "equipe_vertex",
    "start_date": datetime(2026, 8, 20),
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "pipeline_vertex_speed",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
    description="VERTEX - Speed Layer: CNES-ST/PF em cadência diária, independente do Batch",
) as dag:

    task_ingestao_cnes = PythonOperator(
        task_id="ingestao_cnes_speed_layer",
        python_callable=ingestao_cnes,
    )

    task_transformacao_cnes = PythonOperator(
        task_id="transformacao_cnes_speed_layer",
        python_callable=transformar_cnes,
    )

    task_ingestao_cnes >> task_transformacao_cnes

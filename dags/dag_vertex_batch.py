"""
==============================================================================
VERTEX - Batch Layer (Arquitetura Lambda)
Challenge Oracle & FIAP 2026 - 1TSCPF/1TSCPV/1TSCPW

Roda mensalmente (cadência alinhada à publicação de novas competências do
DATASUS/SIA-SUS). Processa SIA/SUS + IBGE, aguarda a execução mais recente
da Speed Layer (CNES, DAG separada e diária) e então consolida os
indicadores e o índice final de subutilização — carregando tudo no Oracle
Autonomous AI Database (VERTEX_DB).
==============================================================================
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor
from airflow.models import TaskInstance
from airflow.utils.state import TaskInstanceState
from airflow.utils.session import provide_session
from datetime import datetime

from vertex_common import (
    ingestao_sia,
    transformar_sia_ibge,
    carga_analitica,
    calcular_indice_subutilizacao,
)

default_args = {
    "owner": "equipe_vertex",
    "start_date": datetime(2026, 8, 20),
}

@provide_session
def speed_layer_concluida(session=None):
    """
    Retorna True quando já existe pelo menos uma execução bem-sucedida
    da transformação da Speed Layer.
    """
    ultima_execucao = (
        session.query(TaskInstance)
        .filter(
            TaskInstance.dag_id == "pipeline_vertex_speed",
            TaskInstance.task_id == "transformacao_cnes_speed_layer",
            TaskInstance.state == TaskInstanceState.SUCCESS,
        )
        .first()
    )

    return ultima_execucao is not None

with DAG(
    "pipeline_vertex_batch",
    default_args=default_args,
    schedule_interval="@monthly",
    catchup=False,
    description="VERTEX - Batch Layer: SIA/SUS + IBGE -> indicadores + índice final (Oracle)",
) as dag:

    task_ingestao_sia = PythonOperator(
        task_id="ingestao_sia_batch_layer",
        python_callable=ingestao_sia,
    )

    task_transformacao = PythonOperator(
        task_id="transformacao_sia_ibge",
        python_callable=transformar_sia_ibge,
    )

    # aguarda uma execução bem-sucedida da Speed Layer
    # pipeline_vertex_speed). É essa dependência entre DAGs com schedules
    # diferentes que caracteriza a Lambda de verdade: o CNES é atualizado
    # de forma independente e mais frequente que o ciclo mensal do SIA/IBGE.
    aguardar_speed_layer = PythonSensor(
        task_id="aguardar_speed_layer",
        python_callable=speed_layer_concluida,
        mode="reschedule",
        timeout=60 * 30,
        poke_interval=30,
)

    task_carga = PythonOperator(
        task_id="carga_analitica",
        python_callable=carga_analitica,
    )

    task_indice_final = PythonOperator(
        task_id="indice_final_subutilizacao",
        python_callable=calcular_indice_subutilizacao,
    )

    task_ingestao_sia >> task_transformacao
    [task_transformacao, aguardar_speed_layer] >> task_carga >> task_indice_final

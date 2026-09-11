# Evidências — Apache Airflow e integração Oracle

Esta pasta reúne evidências da execução da arquitetura de dados da VERTEX, incluindo as camadas Speed e Batch no Apache Airflow e a validação da carga no Oracle.

## Arquivos

1. `01_speed_layer_sucesso.png` — DAG `pipeline_vertex_speed` executada com sucesso, com as tarefas de ingestão e transformação do CNES concluídas.
2. `02_conexao_oracle_docker.png` — ambiente Airflow iniciado via Docker Compose e teste de conexão com o Oracle concluído com `ORACLE OK`.
3. `03_batch_layer_sucesso.png` — DAG `pipeline_vertex_batch` executada com sucesso, incluindo ingestão SIA, transformação SIA/IBGE, sincronização com a Speed Layer, carga analítica e cálculo do índice.
4. `04_log_carga_analitica_oracle.png` — log da tarefa `carga_analitica`, evidenciando persistência dos indicadores analíticos no Oracle.
5. `05_log_indice_subutilizacao.png` — log da tarefa `indice_final_subutilizacao`, mostrando o cálculo do índice para 643 municípios e a carga concluída no Oracle.
6. `06_validacao_total_registros_oracle.png` — validação no Oracle com `COUNT(*)`, confirmando 643 registros na tabela `INDICE_SUBUTILIZACAO`.
7. `07_validacao_indice_subutilizacao_oracle.png` — consulta dos registros da tabela `INDICE_SUBUTILIZACAO`, exibindo município, EPC, PPC, APC e índice calculado.

## Fluxo evidenciado

`CNES / SIA-SUS / IBGE → Apache Airflow → Processamento → Oracle → Indicadores e índice de subutilização`

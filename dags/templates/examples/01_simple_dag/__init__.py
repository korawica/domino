from domino.generator import DagFactory

factory = DagFactory(path=__file__)
factory.build_airflow_dag_to_globals(globals())

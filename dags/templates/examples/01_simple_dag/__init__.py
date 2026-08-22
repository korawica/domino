from domino.generator import SingleDagGenerator

gen = SingleDagGenerator(
    path=__file__,
)
gen.build_airflow_dag_to_globals(globals())

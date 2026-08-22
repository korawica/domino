from domino.providers import Group


def test_group_model():
    group = Group(
        id="group1",
        tasks=[],
    )
    assert group.id == "group1"
    assert group.type == "group"
    assert isinstance(group.tasks, list)


def test_group_model_validate():
    group = Group.model_validate(
        obj={
            "id": "group1",
            "type": "group",
            "tasks": [
                {
                    "id": "task1",
                    "type": "task",
                },
                {
                    "id": "nested_group1",
                    "type": "group",
                    "tasks": [
                        {
                            "id": "task2",
                            "type": "task",
                        }
                    ],
                },
            ],
        }
    )
    assert group.id == "group1"
    assert group.type == "group"
    assert len(group.tasks) == 2
    assert group.tasks[0].id == "task1"
    assert group.tasks[0].type == "task"
    assert group.tasks[1].id == "nested_group1"
    assert group.tasks[1].type == "group"
    assert len(group.tasks[1].tasks) == 1
    assert group.tasks[1].tasks[0].id == "task2"
    assert group.tasks[1].tasks[0].type == "task"

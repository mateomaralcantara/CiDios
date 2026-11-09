from cdd.harness.states import can_transition


def test_main_chain_forward_only():
    assert can_transition("CREATED", "AUTHORIZED")
    assert can_transition("PLANNED", "ACQUIRING")
    assert can_transition("ACQUIRING", "VERIFYING")  # fases sin tareas pueden omitirse
    assert not can_transition("VERIFYING", "ACQUIRING")
    assert not can_transition("ACQUIRING", "ACQUIRING")


def test_interruptions_and_resume():
    assert can_transition("ACQUIRING", "PAUSED")
    assert can_transition("PAUSED", "ACQUIRING", previous="ACQUIRING")
    assert not can_transition("PAUSED", "PLANNED", previous="ACQUIRING")
    assert can_transition("PLANNED", "AWAITING_APPROVAL")
    assert can_transition("ACQUIRING", "BUDGET_EXHAUSTED")


def test_terminal_and_publish():
    assert can_transition("READY", "PUBLISHED")
    assert not can_transition("QA", "PUBLISHED")
    assert not can_transition("PUBLISHED", "FAILED")
    assert not can_transition("CANCELLED", "AUTHORIZED")
    assert can_transition("ANALYZING", "CANCELLED")

import pytest

from cne_agent.appointments.request import AppointmentRequestPatch
from cne_agent.graph.routing import route_after_normalization
from cne_agent.interpretation.models import TurnIntent, TurnInterpretation
from cne_agent.interpretation.normalizer import (
    NormalizationIssue,
    NormalizationIssueCode,
    NormalizationIssueKind,
    NormalizationResult,
    NormalizationStatus,
)


def state(result, interpretation=None):
    return {
        "messages": [],
        "normalization_result": result,
        "turn_interpretation": interpretation or TurnInterpretation(),
    }


def issue(kind):
    return NormalizationIssue(
        NormalizationIssueCode.CONFLICTING_CHANGES,
        kind,
        None,
        "detalle interno",
    )


@pytest.mark.parametrize(
    ("status", "kind", "expected"),
    [
        (NormalizationStatus.INVALID, NormalizationIssueKind.CONFLICT, "invalid"),
        (
            NormalizationStatus.NEEDS_CLARIFICATION,
            NormalizationIssueKind.CLARIFICATION,
            "clarification",
        ),
    ],
)
def test_routes_blocking_results(status, kind, expected):
    result = NormalizationResult(status, None, (issue(kind),))
    assert route_after_normalization(state(result)) == expected


def test_routes_success_with_information_without_discarding_other_intents():
    result = NormalizationResult(
        NormalizationStatus.SUCCESS,
        AppointmentRequestPatch(),
    )
    interpretation = TurnInterpretation(
        intents=[TurnIntent.INFORMATION_QUERY, TurnIntent.BOOK_APPOINTMENT],
        information_queries=["¿Cuánto cuesta?"],
    )
    assert (
        route_after_normalization(state(result, interpretation))
        == "success"
    )


def test_routes_other_success_to_conversation():
    result = NormalizationResult(
        NormalizationStatus.SUCCESS,
        AppointmentRequestPatch(),
    )
    assert route_after_normalization(state(result)) == "success"


def test_configuration_issue_is_a_technical_error():
    result = NormalizationResult(
        NormalizationStatus.INVALID,
        None,
        (issue(NormalizationIssueKind.CONFIGURATION),),
    )
    with pytest.raises(RuntimeError, match="configuracion"):
        route_after_normalization(state(result))

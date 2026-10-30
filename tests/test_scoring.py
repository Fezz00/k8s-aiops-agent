"""Tests for the keyword scoring of the eval."""

from eval.scoring import score

GROUPS = [["ImagePullBackOff", "ErrImagePull", "pull"], ["1.277", "not found"]]


def test_passes_when_every_group_matches():
    assert score("The pod is in ImagePullBackOff: tag 1.277 does not exist.", GROUPS) == {
        "passed": True,
        "missing": [],
    }


def test_matching_ignores_case():
    assert score("image PULL failed, manifest NOT FOUND", GROUPS)["passed"]


def test_fails_and_names_the_missing_group():
    result = score("The pod is in ImagePullBackOff.", GROUPS)
    assert not result["passed"]
    assert result["missing"] == [["1.277", "not found"]]


def test_empty_answer_misses_everything():
    assert score("", GROUPS)["missing"] == GROUPS

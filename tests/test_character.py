import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from autopilot.character.animator import Cue, MouthKey, Timeline
from autopilot.character.rig import EXPRESSIONS, MOUTHS, POSES, State, render_svg, state_for


def _parses(svg: str) -> None:
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")


@pytest.mark.parametrize("pose", list(POSES))
def test_every_pose_renders(pose):
    _parses(render_svg(state_for("neutral", pose)))


@pytest.mark.parametrize("expr", list(EXPRESSIONS))
def test_every_expression_renders(expr):
    _parses(render_svg(state_for(expr)))


@pytest.mark.parametrize("mouth", MOUTHS)
def test_every_mouth_renders(mouth):
    _parses(render_svg(replace(State(), mouth=mouth)))


def test_unknown_values_raise():
    with pytest.raises(ValueError):
        render_svg(State(pose="moonwalk"))
    with pytest.raises(ValueError):
        render_svg(State(mouth="Z"))


def test_timeline_blinks_close_the_eyes():
    tl = Timeline(10, [Cue(0, "neutral", "idle")])
    b = tl.blinks[0]
    assert tl.state_at(b + 0.08).eye_open < 0.1
    assert tl.state_at(b - 0.05).eye_open == 1.0


def test_timeline_follows_mouth_track_and_pose_blend():
    tl = Timeline(3, [Cue(0, "neutral", "idle"), Cue(1.0, "happy", "wave")], mouth=[MouthKey(0.5, "D"), MouthKey(0.9, "X")])
    assert tl.state_at(0.6).mouth == "D"
    mid = tl.state_at(1.1).arms[1]
    assert POSES["idle"][1].upper < mid.upper < POSES["wave"][1].upper
    assert tl.state_at(2.0).arms[1].upper == pytest.approx(POSES["wave"][1].upper)

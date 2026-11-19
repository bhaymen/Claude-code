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


# --- wardrobe, IK, actions, scenes, sfx ---------------------------------------
import math

from autopilot.audio import sfx
from autopilot.character import scenes, wardrobe
from autopilot.character.animator import ACTIONS, Action
from autopilot.character.rig import SHOULDERS, UPPER_LEN, FORE_LEN, PAW_OFFSET, reach
from autopilot.character.style import direction


@pytest.mark.parametrize("outfit", list(wardrobe.OUTFITS))
@pytest.mark.parametrize("hat", [None, *wardrobe.HATS])
def test_outfit_and_hat_combinations_render(outfit, hat):
    _parses(render_svg(State(outfit=outfit, hat=hat)))


@pytest.mark.parametrize("prop", wardrobe.PROPS)
def test_props_render_and_paws_reach_them(prop):
    s = State(prop=prop, pose="hold")
    _parses(render_svg(s))
    (lx, ly), (rx, ry) = wardrobe.PAW_TARGETS[prop]
    for side, (dx, dy) in ((-1, (lx, ly)), (1, (rx, ry))):
        target = (500 + dx, 720 + dy)
        arm = reach(side, target)
        sx, sy = SHOULDERS[side]
        ux, uy = direction(side, arm.upper)
        fx, fy = direction(side, arm.upper + arm.elbow)
        px = sx + ux * UPPER_LEN + fx * (FORE_LEN + PAW_OFFSET)
        py = sy + uy * UPPER_LEN + fy * (FORE_LEN + PAW_OFFSET)
        assert math.hypot(px - target[0], py - target[1]) < 1.0


def test_unknown_wardrobe_items_raise():
    for bad in (dict(outfit="tuxedo"), dict(hat="crown"), dict(prop="pizza")):
        with pytest.raises(ValueError):
            render_svg(State(**bad))


@pytest.mark.parametrize("name", ACTIONS)
def test_every_action_renders_mid_way(name):
    tl = Timeline(2, [Cue(0, "neutral", "hold")], actions=[Action(0.2, name, 1.0)], base=State(prop="coffee", pose="hold"))
    _parses(render_svg(tl.state_at(0.7)))


def test_unknown_action_raises():
    with pytest.raises(ValueError):
        Timeline(1, [], actions=[Action(0, "moonwalk")])


@pytest.mark.parametrize("name", list(sfx.LIBRARY))
def test_sfx_are_audible_and_not_clipping(name):
    x = sfx.LIBRARY[name]()
    assert len(x) > 0 and 0.2 < float(abs(x).max()) <= 1.0


def test_scene_frames_and_titles_fit():
    for fn in (scenes.intro, scenes.outro):
        duration, frame, events = fn()
        assert duration > 1 and events
        ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{frame(duration / 2)}</svg>')
    long_title = scenes.sticker_text("A VERY VERY LONG CHANNEL TITLE HERE", 540, 300, 120, 5.0)
    xs = [float(g.split("translate(")[1].split(" ")[0]) for g in long_title.split("<g ")[1:]]
    assert min(xs) > 40 and max(xs) < scenes.W - 40

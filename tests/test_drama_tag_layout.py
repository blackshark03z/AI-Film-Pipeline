from film_pipeline.drama.tag_layout import (Box, assign_by_identity,
                                            place_tag)

SIZE = (240.0, 68.0)


def slot_box(anchor, size=SIZE):
    x, y = anchor
    return Box(x=x * 1280 - size[0] / 2, y=y * 720, w=size[0], h=size[1])


def test_tag_goes_toward_frame_centre():
    left_face = Box(x=200, y=200, w=80, h=100)
    a = place_tag(left_face, [left_face], SIZE)
    assert slot_box(a).x > left_face.x + left_face.w
    right_face = Box(x=1000, y=200, w=80, h=100)
    b = place_tag(right_face, [right_face], SIZE)
    assert slot_box(b).x + SIZE[0] < right_face.x


def test_tag_never_covers_another_face():
    target = Box(x=200, y=200, w=80, h=100)
    neighbour = Box(x=300, y=190, w=80, h=110)      # right where it would go
    box = slot_box(place_tag(target, [target, neighbour], SIZE))
    assert not box.hits(neighbour) and not box.hits(target)


def test_glare_moves_the_tag_and_no_slot_returns_none():
    target = Box(x=200, y=200, w=80, h=100)
    first = slot_box(place_tag(target, [target], SIZE))
    glare = lambda b: 1.0 if b.hits(first) else 0.0     # noqa: E731
    moved = slot_box(place_tag(target, [target], SIZE, glare))
    assert not moved.hits(first)
    wall = [Box(x=0, y=0, w=1280, h=720)]
    assert place_tag(target, wall, SIZE) is None


def test_identity_assignment_is_one_to_one_and_thresholded():
    refs = {"ROSA": [1.0, 0.0], "ELENA": [0.0, 1.0]}
    faces = [[0.1, 0.9], [0.95, 0.1], [-1.0, 0.0]]
    assert assign_by_identity(faces, refs) == {"ROSA": 1, "ELENA": 0}
    assert assign_by_identity([[-1.0, 0.0]], refs) == {}

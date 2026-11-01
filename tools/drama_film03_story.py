"""film03 "The Front Desk": what the viewer must know (drama.comprehension).

Shared by the plan (tools/drama_film03.py) and the post
(tools/drama_film03_post.py). Dramatic irony: the opening card tells the
viewer who NORA is before the sergeant learns it.
"""
from film_pipeline.drama.comprehension import (Carrier, CharacterIntro,
                                               ContextCard, IdentityTag,
                                               StoryFact)

TAKES_ORDER = [f"SC0{s}_g{g}" for s in range(1, 9) for g in (1, 2)]
ALL = ["NORA", "KESSLER", "ORTIZ"]
IN_FRAME = {
    "SC01_g1": ALL, "SC01_g2": ["KESSLER", "NORA"],
    "SC02_g1": ["NORA", "KESSLER"], "SC02_g2": ALL,
    "SC03_g1": ["ORTIZ"], "SC03_g2": ALL,
    "SC04_g1": ["NORA"], "SC04_g2": ALL,
    "SC05_g1": ["KESSLER"], "SC05_g2": ["ORTIZ"],
    "SC06_g1": ["NORA"], "SC06_g2": ["KESSLER"],
    "SC07_g1": ALL, "SC07_g2": ["NORA"],
    "SC08_g1": ["ORTIZ"], "SC08_g2": ALL,
}
INTROS = [
    CharacterIntro(character="NORA", label="NORA BELL",
                   relation="the precinct's new captain",
                   needed_by="SC01_g2"),
    CharacterIntro(character="KESSLER", label="SGT. KESSLER",
                   relation="the desk sergeant", needed_by="SC02_g1"),
    CharacterIntro(character="ORTIZ", label="OFFICER ORTIZ",
                   relation="a rookie", needed_by="SC03_g1"),
]
# the opening master is too wide to recognise KESSLER and ORTIZ (face
# detection fails at that size): each is named on his first close shot,
# before his line; NORA on her first close shot too
TAGS = [
    IdentityTag(character="NORA", generation_id="SC01_g2", start_s=0.2,
                end_s=3.3),
    IdentityTag(character="KESSLER", generation_id="SC02_g1", start_s=0.2,
                end_s=3.2),
    IdentityTag(character="ORTIZ", generation_id="SC03_g1", start_s=0.1,
                end_s=2.4),
]
CARDS = [ContextCard(card_id="OPEN_card", before="SC01_g1",
                     lines=["The new captain arrives early"]),
         ContextCard(card_id="ROLLCALL_card", before="SC07_g1",
                     lines=["Roll call, 8 a.m."])]
FACTS = [
    StoryFact(fact_id="nora_is_captain",
              text="NORA is the new captain; the desk has never met her",
              needed_by="SC01_g1",
              carriers=[Carrier(kind="CARD", generation_id="SC01_g1")]),
    StoryFact(fact_id="letter_is_appointment",
              text="the letter names her captain",
              needed_by="SC02_g2",
              carriers=[Carrier(kind="DIALOGUE", generation_id="SC02_g1",
                                detail="Captain? Captains here don't look "
                                       "like you.")]),
    StoryFact(fact_id="lieutenant_confirms",
              text="the call from upstairs is about the new captain",
              needed_by="SC06_g1",
              carriers=[Carrier(kind="DIALOGUE", generation_id="SC05_g1",
                                detail="Desk. Yes, Lieutenant. The new "
                                       "captain?"),
                        Carrier(kind="DIALOGUE", generation_id="SC05_g2",
                                detail="Captain Nora Bell.")]),
    StoryFact(fact_id="time_jump", text="roll call, later that morning",
              needed_by="SC07_g1",
              carriers=[Carrier(kind="CARD", generation_id="SC07_g1"),
                        Carrier(kind="VISUAL", generation_id="SC07_g1",
                                detail="briefing room, officers seated")]),
]

# Vietnamese sidecar: every on-screen and spoken English text of the cut
VI = {
    "THE FRONT DESK": "QUẦY TRỰC BAN",
    "The new captain arrives early": "Tân đại úy đến sớm",
    "Roll call, 8 a.m.": "Điểm danh, 8 giờ sáng",
    "the precinct's new captain": "tân chỉ huy của đồn",
    "the desk sergeant": "trung sĩ trực ban",
    "a rookie": "cảnh sát mới vào nghề",
    "Complaints window opens at nine.":
        "Quầy tiếp nhận khiếu nại mở lúc chín giờ.",
    "I'm not here to complain.": "Tôi không đến để khiếu nại.",
    "Captain? Captains here don't look like you.":
        "Đại úy à? Đại úy ở đây đâu có trông như bà.",
    "Nice try. Next.": "Diễn hay đấy. Người tiếp theo.",
    "Sarge, maybe we call upstairs?":
        "Trung sĩ, hay ta gọi lên tầng trên hỏi thử?",
    "Maybe you go file something.": "Hay cậu đi mà xếp hồ sơ.",
    "What's your name, officer?": "Cậu tên gì, anh cảnh sát?",
    "Ortiz, ma'am.": "Ortiz, thưa bà.",
    "Desk. Yes, Lieutenant. The new captain?":
        "Trực ban nghe. Vâng, thưa trung úy. Tân đại úy ạ?",
    "Captain Nora Bell.": "Đại úy Nora Bell.",
    "Roll call is at eight, Sergeant.": "Tám giờ điểm danh, trung sĩ.",
    "Yes... Captain.": "Vâng... thưa đại úy.",
    "We check before we judge. Every time.":
        "Ta kiểm tra trước khi phán xét. Lần nào cũng vậy.",
    "Officer Ortiz rides with me today.":
        "Hôm nay cảnh sát Ortiz đi tuần cùng tôi.",
    "Yes, ma'am.": "Vâng, thưa bà.",
    "Sergeant Kessler keeps the desk.":
        "Trung sĩ Kessler tiếp tục ngồi quầy trực.",
    "A short drama. All characters are fictional.":
        "Phim ngắn. Mọi nhân vật đều là hư cấu.",
    "Video, images and voices generated with AI.":
        "Video, hình ảnh và giọng nói được tạo bằng AI.",
}

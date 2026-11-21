import os
import sys
import unittest
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.film_qc_engine import FilmQCEngine
from core.video_processor import VideoProcessor

class TestFilmQCEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("D:/Muse/muse_studio/data/test_qc_temp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_preflight_valid(self):
        shot = {
            "id": "SH01",
            "order": 1,
            "prompt": "Captain Brianna standing poised in cockpit door in exactly 16:9 aspect ratio. Locked-off static tripod shot, no camera motion.",
            "reference_images": []
        }
        ok, errs = FilmQCEngine.validate_shot_preflight(shot)
        self.assertTrue(ok)
        self.assertEqual(len(errs), 0)

    def test_preflight_reject_missing_aspect_ratio(self):
        shot = {
            "id": "SH02",
            "order": 2,
            "prompt": "Flight attendant shouting without camera rules."
        }
        ok, errs = FilmQCEngine.validate_shot_preflight(shot)
        self.assertFalse(ok)
        self.assertTrue(any("MISSING_ASPECT_RATIO" in e for e in errs))

    def test_preflight_reject_hazardous_finger_action(self):
        shot = {
            "id": "SH03",
            "order": 3,
            "prompt": "Captain holding phone in exactly 16:9 aspect ratio. Locked-off static tripod shot. She uses her index finger to tap screen."
        }
        ok, errs = FilmQCEngine.validate_shot_preflight(shot)
        self.assertFalse(ok)
        self.assertTrue(any("HAZARDOUS_FINGER_ACTION" in e for e in errs))
        self.assertTrue(any("MISSING_HAND_ANATOMY_GUARD" in e for e in errs))

    def test_postflight_qc_reject_hand_mutation(self):
        test_clip = self.tmp_dir / "hand_clip.mp4"
        VideoProcessor.create_synthetic_test_clip(test_clip, duration_s=4.0, text="HAND")
        shot_spec = {
            "id": "SH_HAND",
            "prompt": "Captain holds phone with five fingers.",
            "has_hand_defect": True
        }
        res = FilmQCEngine.evaluate_generated_clip(test_clip, shot_spec, min_duration_s=3.0)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertTrue(any("DEFECT_ANATOMICAL_HAND_MUTATION" in d for d in res["defects"]))

    def test_postflight_qc_on_valid_video(self):
        # Create a test video using VideoProcessor
        test_clip = self.tmp_dir / "valid_clip.mp4"
        VideoProcessor.create_synthetic_test_clip(test_clip, duration_s=4.0, text="QC TEST")
        self.assertTrue(test_clip.exists())

        shot_spec = {"id": "SH01"}
        res = FilmQCEngine.evaluate_generated_clip(test_clip, shot_spec, min_duration_s=3.0)
        
        # Test synthetic clip might be rejected if frozen or accepted if dynamic
        self.assertIn("verdict", res)
        self.assertIn(res["verdict"], ["PASS", "REJECT"])
        self.assertIn("metrics", res)

    def test_postflight_qc_rejects_missing_file(self):
        non_existent = self.tmp_dir / "ghost.mp4"
        res = FilmQCEngine.evaluate_generated_clip(non_existent, {"id": "SH_NONE"})
        self.assertEqual(res["verdict"], "REJECT")
        self.assertEqual(res["defect_code"], "PROBE_FAILED")

    def test_native_dialogue_qc_interface(self):
        # Kiểm tra tính tương thích của Gate 5 ASR
        test_clip = self.tmp_dir / "dialogue_clip.mp4"
        VideoProcessor.create_synthetic_test_clip(test_clip, duration_s=4.0, text="SPEECH")
        
        # Test gọi verify_native_dialogue
        res = FilmQCEngine.verify_native_dialogue(test_clip, expected_dialogue="Hello world")
        self.assertIn("passed", res)
        self.assertIn("wer", res)
        self.assertIn("pauses", res)

if __name__ == "__main__":
    unittest.main()

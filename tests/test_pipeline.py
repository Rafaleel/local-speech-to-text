import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from src.audio.recorder import AudioRecorder
from src.engine.stt_engine import ModelManager, TranscribeWorker


class PipelineTests(unittest.TestCase):
    def test_failed_microphone_can_be_retried(self):
        bad_stream = Mock()
        bad_stream.start.side_effect = RuntimeError("dispositivo ocupado")
        good_stream = Mock()
        recorder = AudioRecorder()
        with patch("src.audio.recorder.sd.InputStream", side_effect=[bad_stream, good_stream]):
            with self.assertRaises(RuntimeError):
                recorder.start_recording()
            self.assertFalse(recorder.is_recording)
            bad_stream.close.assert_called_once()
            recorder.start_recording()
            self.assertTrue(recorder.is_recording)
            recorder.stop_recording()

    def test_cpu_fallback_is_reused_and_legacy_model_is_normalized(self):
        model = object()
        factory = Mock(side_effect=[RuntimeError("CUDA indisponível"), model])
        with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=factory)}):
            with patch.multiple(ModelManager, _loaded_model=None, _current_key=None, _active_device="cpu"):
                self.assertEqual(ModelManager.get_model("openai/whisper-large-v3"), (model, "cpu"))
                self.assertEqual(ModelManager.get_model("large-v3"), (model, "cpu"))
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(factory.call_args.args, ("large-v3",))

    def test_spoken_closing_is_preserved_and_not_logged(self):
        phrase = "Pode me mandar amanhã, obrigado."
        model = Mock()
        model.transcribe.return_value = (
            iter([SimpleNamespace(text=phrase)]),
            SimpleNamespace(language="pt", language_probability=0.99),
        )
        worker = TranscribeWorker(np.zeros(16000), language="pt")
        result = Mock()
        worker.finished_signal.connect(result)
        with patch.object(ModelManager, "get_model", return_value=(model, "cpu")), patch("builtins.print") as log:
            worker.run()
        result.assert_called_once_with(phrase, "pt", 1.0)
        self.assertNotIn(phrase, str(log.call_args_list))

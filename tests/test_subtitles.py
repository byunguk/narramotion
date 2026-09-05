from narramotion.subtitles import offset_cues, words_to_cues


def test_cue_grouping_and_offset():
    words = [
        {"word": "In", "start": 0.1, "end": 0.2},
        {"word": "the", "start": 0.21, "end": 0.3},
        {"word": "beginning.", "start": 0.31, "end": 0.8},
        {"word": "Next", "start": 1.0, "end": 1.2},
    ]
    cues = words_to_cues(words, max_words=9, max_sec=4)
    assert len(cues) == 2
    shifted = offset_cues(cues, 10.0)
    assert shifted[0]["start"] == 10.1
    assert shifted[1]["start"] == 11.0

from src.utils.sentiment import blend_sentiment_scores, compute_lexical_sentiment


def test_blend_sentiment_scores_weighting():
    blended = blend_sentiment_scores(0.8, -0.2, weight=0.75)
    expected = round((0.8 * 0.75) + (-0.2 * 0.25), 4)
    assert blended == expected


def test_blend_sentiment_scores_clamps_weight():
    assert blend_sentiment_scores(0.5, -0.5, weight=1.5) == 0.5
    assert blend_sentiment_scores(0.5, -0.5, weight=-1.0) == -0.5


def test_compute_lexical_sentiment_direction():
    assert compute_lexical_sentiment("This is absolutely wonderful!") > 0
    assert compute_lexical_sentiment("This is terrible and disastrous") < 0
    assert compute_lexical_sentiment("") == 0.0

from src.coaching.mental_toughness_coach import MentalToughnessCoach


def test_mental_toughness_coach_initialization():
    coach = MentalToughnessCoach()
    assert coach is not None
    assert coach.state_manager is not None


def test_mental_toughness_coach_session_lifecycle():
    coach = MentalToughnessCoach()
    start_msg = coach.start_session()
    assert start_msg is not None

    ready, intervention = coach.is_ready_to_trade()
    assert isinstance(ready, bool)

    end_msg = coach.end_session()
    assert end_msg is not None

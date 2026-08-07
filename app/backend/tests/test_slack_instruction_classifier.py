from app.backend.services.slack_instruction_classifier import SlackInstructionClassifier


def test_requested_conversational_comic_examples_normalize_to_story_briefs() -> None:
    classifier = SlackInstructionClassifier()
    examples = {
        "create me a comic of eating wings and eating wings with you": ("EATING WINGS.", "EATING WINGS WITH YOU."),
        "make laundry / laundry with you": ("LAUNDRY.", "LAUNDRY WITH YOU."),
        "create the farmers market one": ("FARMERS MARKET.", "FARMERS MARKET WITH YOU."),
        "party / party with you": ("PARTY.", "PARTY WITH YOU."),
    }

    for instruction, expected in examples.items():
        plan = classifier.classify(instruction)
        assert plan["task_type"] == "generate_comic"
        assert (plan["context"]["left_title"], plan["context"]["right_title"]) == expected
        assert plan["context"]["story_brief"]["title_left"] == expected[0]
        assert plan["context"]["story_brief"]["left_emotion"].endswith("never happy.")


def test_ambiguous_comic_request_asks_one_question_without_guessing() -> None:
    plan = SlackInstructionClassifier().classify("create me a comic")
    assert plan["task_type"] == "unknown"
    assert plan["clarification"]

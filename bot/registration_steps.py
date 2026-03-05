from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationStep:
    key: str
    label: str
    prompt: str
    required: bool = True


REGISTRATION_STEPS = [
    RegistrationStep(
        key="full_name",
        label="ФИО",
        prompt="Введите ваше ФИО:",
        required=True,
    ),
]

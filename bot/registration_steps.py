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
        label="Имя",
        prompt="Напишите Ваше имя:",
        required=True,
    ),
    RegistrationStep(
        key="phone",
        label="Номер телефона",
        prompt="Отправьте свой номер телефона кнопкой 'Отправить контакт':",
        required=True,
    ),
]

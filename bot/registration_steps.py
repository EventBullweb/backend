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
        prompt="""Начинаем регистрацию.
Напишите Ваше имя:""",
        required=True,
    ),
    RegistrationStep(
        key="phone",
        label="Номер телефона",
        prompt="""Финальное действие в регистрации и вы получаете билет 👇нажмите кнопку 'Отправить контакт'""",
        required=True,
    ),
]

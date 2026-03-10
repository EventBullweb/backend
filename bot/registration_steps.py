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
        label="Фамилия и имя",
        prompt="""Начинаем регистрацию.
Напишите фамилию и имя:""",
        required=True,
    ),
    RegistrationStep(
        key="organization",
        label="Название организации",
        prompt="""Укажите название организации:""",
        required=True,
    ),
    RegistrationStep(
        key="position",
        label="Должность или занимаемый пост",
        prompt="""Укажите должность или занимаемый пост:""",
        required=True,
    ),
    RegistrationStep(
        key="phone",
        label="Контакт",
        prompt="""Финальное действие в регистрации: нажмите кнопку 'Отправить контакт'.""",
        required=True,
    ),
]

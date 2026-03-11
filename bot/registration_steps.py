from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationStep:
    key: str
    label: str
    prompt: str
    required: bool = True


REGISTRATION_STEPS = [
    RegistrationStep(
        key="phone",
        label="Контакт",
        prompt=(
            "{username}, для получения билета подтвердите, что вы не робот — "
            'оставьте свой номер телефона нажав кнопку "ОТПРАВИТЬ КОНТАКТ"👇'
        ),
        required=True,
    ),
    RegistrationStep(
        key="full_name",
        label="Фамилия и имя",
        prompt="""<b>Последний шаг регистрации.</b>

Напишите пожалуйста Ваши:

1. Имя и Фамилию
2. Название организации  
3. Должность/занимаемый пост

*просто текстом ниже👇""",
        required=True,
    ),
]

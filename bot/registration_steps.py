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
        prompt="""Для регистрации

Напишите Ваше:
1. фамилию и имя 
2. название организации  
3. должность или занимаемый пост 

просто текстом ниже 👇""",
        required=True,
    ),
    RegistrationStep(
        key="phone",
        label="Контакт",
        prompt="""Финальное действие в регистрации: нажмите кнопку 'Отправить контакт'.""",
        required=True,
    ),
]

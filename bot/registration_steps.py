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
        prompt="""Для регистрации нажмите кнопку 'Отправить контакт'.""",
        required=True,
    ),
    RegistrationStep(
        key="full_name",
        label="Фамилия и имя",
        prompt="""Финальное действие в регистрации: 

Напишите Ваше:
1. фамилию и имя 
2. название организации  
3. должность или занимаемый пост 

просто текстом ниже 👇""",
        required=True,
    ),
]

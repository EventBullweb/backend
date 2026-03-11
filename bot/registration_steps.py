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
        prompt="""Финальное действие в регистрации: 

Напишите Ваше:
1. фамилию и имя 
2. название организации  
3. должность или занимаемый пост 

просто текстом ниже 👇""",
        required=True,
    ),
]

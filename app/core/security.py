# app/core/security.py
import re

def sanitize_input(text: str) -> str:
    """
    Substitui dados pessoais sensíveis (CPF, e-mail, telefone, cartão) por placeholders seguros.
    Essa higienização é efetuada antes do envio das dúvidas para os LLMs externos.
    """
    # CPF: XXX.XXX.XXX-XX ou XXXXXXXXXXX
    cpf_pattern = r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
    # E-mail: teste@teste.com
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    # Telefone: (XX) 9XXXX-XXXX ou XXXXXXXXX
    phone_pattern = r'\b(?:\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}\b'
    # Cartão de Crédito
    card_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    
    sanitized = re.sub(cpf_pattern, "[CPF_REDUZIDO]", text)
    sanitized = re.sub(email_pattern, "[EMAIL_REDUZIDO]", sanitized)
    sanitized = re.sub(phone_pattern, "[TELEFONE_REDUZIDO]", sanitized)
    sanitized = re.sub(card_pattern, "[CARTÃO_CREDITO_REDUZIDO]", sanitized)
    return sanitized

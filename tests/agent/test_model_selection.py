#!/usr/bin/env python3
"""
Test script for dynamic model selection

Run this to see which model would be selected for different messages.
"""

import logging

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Copy of should_use_haiku function for testing (to avoid import issues)
def should_use_haiku(message: str) -> bool:
    """
    STRATEGY: "Haiku First, Sonnet for Polish"
    - Use Haiku for ALL operations (default)
    - Use Sonnet ONLY for final polish/review
    """
    message_lower = message.lower()

    # CRITICAL: Only use Sonnet for polish/review requests
    polish_keywords = [
        'revisar', 'revise', 'revisada', 'revisar proposta',
        'polir', 'polish', 'polida',
        'bem pensada',
        'finalizar', 'finalize', 'finalizada',
        'versão final',
        'review',
        'revisar tudo', 'revisar completa',
        'melhorar a qualidade', 'melhorar redação',
        'aprimorar',
    ]

    for keyword in polish_keywords:
        if keyword in message_lower:
            logger.info(f"💎 Keyword '{keyword}' requires polish/review - using Sonnet for quality")
            return False

    # EVERYTHING ELSE uses Haiku (including creating proposals!)
    logger.info(f"⚡ Using Haiku for fast operation (Sonnet only for polish/review)")
    return True

# Test cases - NEW STRATEGY: Haiku for everything, Sonnet only for polish
test_messages = [
    # Should use Haiku (ALL normal operations - new strategy!)
    ("Olá! Liste as 10 propostas mais recentes", "Haiku"),
    ("edite a data do sesc friburgo pra 11/01", "Haiku"),
    ("Altere o título para 'Novo Projeto'", "Haiku"),
    ("Liste as propostas", "Haiku"),
    ("Mostre a estrutura da proposta", "Haiku"),
    ("Gere o PDF", "Haiku"),
    ("Delete a proposta antiga", "Haiku"),
    ("Qual é a data da proposta?", "Haiku"),
    ("Criar uma nova proposta para o cliente SESC", "Haiku"),  # NEW: Haiku can create drafts!
    ("Gerar proposta completa", "Haiku"),  # NEW: Haiku creates, Sonnet polishes
    ("Mostre tudo", "Haiku"),
    ("Reestruturar a proposta", "Haiku"),
    ("Preciso melhorar a proposta", "Haiku"),  # Generic "improve" uses Haiku
    ("Ajuda com a proposta do cliente", "Haiku"),

    # Should use Sonnet (ONLY polish/review operations!)
    ("Revisar a proposta completa", "Sonnet"),
    ("Revise a proposta antes de enviar", "Sonnet"),
    ("Polir a redação da proposta", "Sonnet"),
    ("Finalizar a proposta", "Sonnet"),
    ("Versão final da proposta", "Sonnet"),
    ("Melhorar a qualidade da redação", "Sonnet"),
    ("Aprimorar a proposta", "Sonnet"),
    ("A proposta está bem pensada?", "Sonnet"),
]

def test_model_selection():
    """Test model selection for various messages"""
    print("=" * 80)
    print("Dynamic Model Selection Test")
    print("=" * 80)
    print()

    correct = 0
    total = len(test_messages)

    for message, expected in test_messages:
        use_haiku = should_use_haiku(message)
        selected = "Haiku" if use_haiku else "Sonnet"
        status = "✅" if selected == expected else "❌"

        print(f"{status} Message: {message[:60]}...")
        print(f"   Expected: {expected} | Selected: {selected}")
        print()

        if selected == expected:
            correct += 1

    print("=" * 80)
    print(f"Results: {correct}/{total} correct ({correct/total*100:.1f}%)")
    print("=" * 80)

if __name__ == "__main__":
    test_model_selection()

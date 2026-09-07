#!/usr/bin/env python3
"""Utility script to list all Gemini models available to the current GEMINI_API_KEY."""

import os
import sys
from google import genai

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("[ERRO] Defina GEMINI_API_KEY no terminal antes de executar:")
    print("    export GEMINI_API_KEY=\"sua-chave\"")
    sys.exit(1)

client = genai.Client(api_key=api_key.strip())

print("Consultando modelos disponíveis para a chave na API do Google Gemini...")
print("=" * 80)
print(f"{'Nome do Modelo':<35} | {'Display Name':<30} | {'Ações'}")
print("-" * 80)

count = 0
try:
    for model in client.models.list():
        name = model.name or ""
        display = model.display_name or ""
        actions = ", ".join(model.supported_actions or [])
        clean_name = name.removeprefix("models/")
        if not model.supported_actions or "generateContent" in model.supported_actions:
            print(f"{clean_name:<35} | {display[:30]:<30} | {actions}")
            count += 1
except Exception as exc:
    print(f"[ERRO] Falha ao listar modelos: {exc}")
    sys.exit(2)

print("=" * 80)
print(f"Total de modelos compatíveis com generateContent: {count}")

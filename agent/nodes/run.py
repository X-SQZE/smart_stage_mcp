import asyncio
import sys

from agent.nodes.graph import app
from agent.nodes.mcp_client import get_mcp_tools


async def main():
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        print("Erreur: Veuillez fournir une requête utilisateur en argument.")
        print('Exemple: python -m agent.nodes.run "Ajouter une fonctionnalité X"')
        sys.exit(1)

    result = await app.ainvoke({"user_request": user_request})

    if not result.get("scope_ok", True) and result.get("clarifying_questions"):
        print("\n--- L'agent manque d'informations pour procéder de façon autonome ---")
        for q in result.get("clarifying_questions", []):
            print(f"- {q}")
        print("\nVeuillez relancer la commande avec plus de précisions ou mettre à jour le repository avec plus de contexte.")
    else:
        print("\n--- Pull Request créée avec succès ---")
        print(result.get("pull_request_url", "Aucune PR créée."))


if __name__ == "__main__":
    asyncio.run(main())
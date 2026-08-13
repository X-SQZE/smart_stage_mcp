import asyncio
import sys

from agent.nodes.graph import app
from agent.nodes.mcp_client import get_mcp_tools


async def main():
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        user_request = input("Que veux-tu que l'agent fasse ? ")

    result = await app.ainvoke({"user_request": user_request})

    if not result.get("scope_ok", False):
        print("\n--- L'agent a besoin de précisions ---")
        for q in result.get("clarifying_questions", []):
            print(f"- {q}")

        reponse_utilisateur = input(
            "\nRéponds à ces questions (ta réponse sera mémorisée pour la suite) : "
        )

        tools = await get_mcp_tools()
        await tools["save_project_conventions"].ainvoke({"new_conventions": reponse_utilisateur})

        print("\nConventions enregistrées. Relance ta demande, elle ne redemandera plus ces infos.")
    else:
        print("\n--- Pull Request créée ---")
        print(result.get("pull_request_url"))


if __name__ == "__main__":
    asyncio.run(main())
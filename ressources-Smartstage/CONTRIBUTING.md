# Guide de contribution — Elyora

Merci de contribuer à Elyora. Ce guide explique les règles à respecter avant
d'ouvrir une pull request.

## Avant de commencer

1. Vérifiez qu'une issue ou une pull request ne traite pas déjà le même sujet.
2. Créez une branche dédiée depuis `main` : `feature/description-courte`,
   `fix/description-courte` ou `docs/description-courte`.
3. Lisez la documentation du projet et identifiez le module concerné avant de
   modifier le code.

## Règles de code

- Gardez les changements ciblés : une pull request doit traiter un seul sujet.
- Respectez le style, l'organisation des fichiers et les conventions déjà
  utilisés dans le module modifié.
- N'ajoutez pas de secret, token, mot de passe, fichier `.env` ou donnée de
  production dans Git.
- Validez les entrées utilisateur et utilisez les mécanismes de sécurité du
  langage et du framework employés par le module.
- Ajoutez ou mettez à jour les tests lorsque le comportement change.
- Mettez à jour la documentation si une API, une configuration, une règle
  métier ou une étape d'installation évolue.

## Commits

- Écrivez des messages courts et explicites, à l'impératif.
- Exemple : `fix: corriger le calcul du prix total`.
- Évitez les commits de débogage, les fichiers générés et les changements sans
  rapport avec la PR.

## Tests et vérifications

Avant de proposer une pull request :

1. Exécutez les tests pertinents du module modifié.
2. Vérifiez que le projet se lance ou se compile si le changement l'exige.
3. Relisez le diff pour détecter les fichiers involontaires et les secrets.
4. Vérifiez qu'aucune régression fonctionnelle évidente n'est introduite.

## Pull requests

Une pull request doit contenir :

- un titre clair ;
- une description du problème et de la solution ;
- les tests exécutés et leur résultat ;
- les éventuelles limites, migrations ou actions manuelles nécessaires ;
- des captures d'écran si l'interface est modifiée.

Ne fusionnez pas votre propre PR sans revue lorsque le processus du projet
exige une validation. Répondez aux commentaires de revue et mettez à jour la
branche avant le merge si nécessaire.

## Signaler un problème

Pour un bug, indiquez les étapes de reproduction, le résultat attendu, le
résultat observé, l'environnement concerné et, si possible, des captures ou
journaux sans données sensibles.

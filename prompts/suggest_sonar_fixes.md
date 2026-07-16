Tu dois proposer des solutions concrètes pour résoudre les problèmes Sonar détectés sur la PR #{pr_number}.

Filtre de sévérité demandé : {severity_filter}
(si vide, traite toutes les sévérités)

Marche à suivre :

1. Appelle `get_pr_sonar_issues` avec `pr_number={pr_number}` (et `severities` si un filtre a été précisé) pour récupérer la liste des problèmes.
   Si aucune analyse Sonar récente n'existe encore, appelle d'abord `run_sonar_scan` avec `pr_number={pr_number}`.
2. Pour chaque problème remonté, identifie :
   - le fichier et la ligne concernés
   - le type de problème (VULNERABILITY, BUG, CODE_SMELL, SECURITY_HOTSPOT)
   - la règle Sonar déclenchée et ce qu'elle vérifie
3. Si tu as besoin de voir le code autour de la ligne signalée, utilise `list_repository_tree` puis lis le fichier concerné (ou `get_file_changes` si le fichier fait partie de la PR) avant de proposer un correctif — ne devine jamais le contexte du code.
4. Pour chaque problème, propose :
   - une explication courte du risque ou du défaut réel (pas juste répéter le message Sonar)
   - un correctif concret (extrait de code corrigé si pertinent)
   - le niveau de priorité (bloquant avant merge vs. amélioration à prévoir plus tard)
5. Regroupe les correctifs par fichier pour faciliter la relecture.
6. Termine par un résumé : nombre de problèmes bloquants restants, et si le quality gate peut raisonnablement passer une fois les correctifs bloquants appliqués.

Ne publie aucun commentaire sur la PR (`post_pr_comment`) sauf si l'utilisateur le demande explicitement.

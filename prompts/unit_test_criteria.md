# Critères pour des tests unitaires pertinents

- Un test = un seul comportement vérifié (principe AAA : Arrange, Act, Assert)
- Prioriser les cas limites : valeurs nulles, vides, négatives, hors bornes
- Couvrir les branches conditionnelles (if/else, exceptions)
- Nommer le test selon ce qu'il vérifie, pas comment (ex: `test_rejette_email_invalide`)
- Ne pas tester l'implémentation interne, tester le comportement observable
- Isoler les dépendances externes (mock/stub) plutôt que d'appeler de vrais services

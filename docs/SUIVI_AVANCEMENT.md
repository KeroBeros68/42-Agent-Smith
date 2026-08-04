# Suivi d'Avancement — Agent Smith

> Ce document est un **template réutilisable**. À chaque point d'équipe, dupliquez la section "Relevé" ci-dessous (ou ajoutez une nouvelle entrée datée) plutôt que d'écraser l'historique — cela permet de visualiser la progression réelle dans le temps.
>
> Statuts possibles : `Non démarré` · `En cours` · `Bloqué` · `Terminé (non testé)` · `Terminé (validé exam)`
>
> La liste des composants ci-dessous reprend exactement la structure du [Cahier des Charges](./CAHIER_DES_CHARGES.md), pour que chaque ligne soit traçable à une section précise du sujet.

---

## Relevé du 2026-08-04

**État constaté du dépôt** : uniquement `README.md` (squelette) et les fichiers sujet (`en.subject_1-1.pdf`, `subject-1-1.txt`). **Aucun code source n'a encore été écrit.** Ce relevé sert de point de départ (baseline) à zéro — il ne s'agit pas d'une évaluation de qualité, mais d'un état des lieux honnête pour amorcer le suivi.

### Tableau de suivi par composant

| Composant | Réf. sujet | Statut | Responsable | Blocages / Notes |
|---|---|---|---|---|
| Architecture générale du dépôt (student/moulinette/cache) | §V.3, §V.4 | Non démarré | *à assigner* | — |
| Boucle agent Thought→Code→Observation | §V.1 | Non démarré | *à assigner* | — |
| Extraction de code (formats Python/XML/JSON/ReAct) | §V.1 pt.2 | Non démarré | *à assigner* | — |
| System prompt (doc outils + exemples) | §V.1 pt.6 | Non démarré | *à assigner* | — |
| Sandbox — CLI + REPL interactif | §V.2.1 | Non démarré | *à assigner* | — |
| Sandbox — `final_answer` | §V.2.2 | Non démarré | *à assigner* | — |
| Sandbox — sécurité (imports/fs/réseau/timeout/mémoire/builtins) | §V.2.3 | Non démarré | *à assigner* | — |
| Sandbox — `SandboxConfig` (Pydantic) | §V.2.4 | Non démarré | *à assigner* | — |
| Intégration MCP (stdio + HTTP) | §V.2.5 | Non démarré | *à assigner* | — |
| Manuel du sandbox (généré dynamiquement) | §V.2.6 | Non démarré | *à assigner* | — |
| Agent MBPP + CLI (`agent_mbpp`) | §V.3 | Non démarré | *à assigner* | — |
| Outil MCP `run_tests` (MBPP) | §V.3.2 | Non démarré | *à assigner* | — |
| Modèles Pydantic MBPP (Task/Step/SolutionOutput) | §V.3.3 | Non démarré | *à assigner* | — |
| Agent SWE-bench + CLI (`agent_swebench`) | §V.4 | Non démarré | *à assigner* | — |
| Intégration Docker (testbed) | §V.4 | Non démarré | *à assigner* | — |
| Génération de patch (`get_patch`) | §V.4, §V.5.3 | Non démarré | *à assigner* | — |
| Modèles Pydantic SWE-bench | §V.4.3 | Non démarré | *à assigner* | — |
| Outils fichiers (`read_file`/`edit_file`/`list_files`) | §V.5.1 | Non démarré | *à assigner* | — |
| Outils recherche (`search_code`/def/refs) | §V.5.2 | Non démarré | *à assigner* | — |
| Outils exécution (`run_tests`/`get_patch`/`run_command`) | §V.5.3 | Non démarré | *à assigner* | — |
| Multi-provider LLM + rotation de clés | §V.6 | Non démarré | *à assigner* | — |
| `BENCHMARK_REPORT.md` (≥5 modèles × ≥3 tâches) | §V.7 | Non démarré | *à assigner* | — |
| `README.md` conforme (sections imposées, en anglais) | §VII | Non démarré | *à assigner* | Squelette vide actuellement |

### Synthèse
- **Avancement global estimé** : 0 %
- **Risque principal identifié** : aucun code n'existe encore alors que le projet comporte deux sous-systèmes majeurs (sandbox sécurisé + double agent) qui dépendent l'un de l'autre — le sandbox doit exister avant que le moindre agent ne soit testable.
- **Prochaine étape recommandée** : voir le [Plan d'Action](./PLAN_ACTION.md), Phase 0.

---

## Relevé du [DATE]

*(dupliquer cette section à chaque point d'avancement)*

### Tableau de suivi par composant
*(copier le tableau ci-dessus et mettre à jour les statuts)*

### Points positifs de la période
-

### Difficultés rencontrées
-

### Décisions techniques prises et justification
-

### Écarts par rapport au plan d'action
-

### Prochaine étape
-

---

## Grille de questions d'auto-évaluation (issue du sujet, §V.1.1)

À utiliser en équipe à chaque relevé pour objectiver le feedback, plutôt que de se fier à une impression :

**Démarrage**
- [ ] Avons-nous identifié quel benchmark est le plus simple à attaquer en premier ?
- [ ] Testons-nous avec le modèle le plus capable disponible, avant d'ajouter des contraintes ?
- [ ] L'agent résout-il la tâche la plus simple sans limite de tokens/itérations ?

**Debug**
- [ ] Avons-nous observé les 3 à 5 premières itérations de l'agent en détail ?
- [ ] Avons-nous résolu la tâche cible manuellement avant d'écrire le prompt ?
- [ ] Avons-nous des signaux de progression partielle même quand les tests échouent encore ?

**Scaling**
- [ ] L'agent généralise-t-il à plusieurs tâches ou est-il en surapprentissage sur une seule ?
- [ ] Avons-nous prouvé que l'approche fonctionne avant d'optimiser tokens/modèle ?
- [ ] Travaillons-nous avec les tendances naturelles du modèle ou contre elles ?

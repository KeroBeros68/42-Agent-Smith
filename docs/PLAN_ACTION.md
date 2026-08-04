# Plan d'Action — Agent Smith

> Ce plan traduit les recommandations explicites du sujet (§V.1.1 « Development Approach ») en phases concrètes. L'ordre proposé suit deux principes directement issus du sujet :
> 1. **Le sandbox est un prérequis** aux deux agents — aucun agent n'est testable sans lui (§III.1 pt.3, §V.2).
> 2. **MBPP avant SWE-bench** — le sujet présente MBPP comme le benchmark le plus simple (problèmes algorithmiques isolés vs. bugs réels en conteneurs Docker), et le sujet lui-même traite MBPP (§V.3) avant SWE-bench (§V.4).
>
> Chaque phase liste : objectif, tâches, critère de sortie (« Definition of Done »), et référence au sujet.
>
> **À compléter par l'équipe** : dates, répartition nominative des tâches. Aucune date n'est fixée ici car le sujet ne mentionne pas d'échéance — ne pas inventer de deadline.

---

## Phase 0 — Socle du projet

**Objectif** : poser une base saine avant d'écrire la moindre logique agentique.

- [ ] Initialiser la structure de dépôt (`student/`, `moulinette/`, `cache/`, config racine) — structure interne libre (§VIII)
- [ ] Configurer `uv` + Python 3.10 (§IV.1)
- [ ] Mettre en place le chargement de clés API via `.env` / variables d'environnement (§VI, §VI.3) — **aucune clé en dur**
- [ ] Définir les premiers modèles Pydantic communs (`SandboxConfig`, squelettes de `StepMetrics`/`SolutionOutput`)
- [ ] Décider de l'architecture cible (découpage modules, gestion des erreurs gracieuse) — documenter les choix pour pouvoir les défendre en soutenance (§II)

**Definition of Done** : `uv run` fonctionne, structure de dossiers créée, `.env.example` versionné (sans vraies clés).

---

## Phase 1 — Sandbox (sans MCP)

**Objectif** : avoir un sandbox qui exécute du code Python arbitraire de façon sûre, avant même de parler d'agent ou de LLM.

Réf. §V.2.

- [ ] Choisir l'approche d'isolation (process séparé vs. namespace restreint dans le process courant) — peser sécurité / gestion du timeout / communication (question posée explicitement par le sujet, §V.2 fin)
- [ ] Implémenter les restrictions : imports (allowlist), filesystem (`allowed_directories`), réseau (aucun), timeout, mémoire, builtins restreints — stdlib uniquement, pas de `RestrictedPython`
- [ ] Implémenter `final_answer` comme construct sandbox (pas un outil MCP)
- [ ] Vérifier explicitement que `KeyboardInterrupt`/`SystemExit` remontent sans être capturés
- [ ] Implémenter la CLI `uv run sandbox` (avec/sans fichier de config JSON)
- [ ] Implémenter le mode REPL interactif (boucle lecture/exécution, sortie sur `exit`/EOF)

**Definition of Done** : `uv run sandbox sandbox_template.json` ouvre un REPL, refuse un import hors allowlist, refuse un accès disque hors `allowed_directories`, coupe une boucle infinie au timeout, appelle `final_answer(...)` correctement.

---

## Phase 2 — Intégration MCP générique + premier outil (MBPP)

**Objectif** : connecter le sandbox à un serveur MCP et exposer ses outils comme fonctions Python, sans coder en dur les outils d'un seul serveur.

Réf. §V.2.5, §V.2.6.

- [ ] Client MCP dans le sandbox, support **stdio** et **HTTP streamable**
- [ ] Découverte dynamique des outils/ressources/prompts exposés par le serveur connecté
- [ ] Génération dynamique du **manuel du sandbox** à partir des schémas d'outils découverts
- [ ] Implémenter `mcp_tools_mbpp.py` (racine du dépôt) avec au minimum `run_tests`
- [ ] Test croisé : brancher un serveur MCP factice/minimal différent et vérifier que le manuel et les wrappers s'adaptent automatiquement (anticipe le test avec « serveur MCP inconnu », §V.2.5)

**Definition of Done** : `uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json` expose `run_tests()` comme fonction Python appelable, et le manuel généré liste bien cet outil.

---

## Phase 3 — Boucle agent minimale (sur le modèle le plus capable, sans contraintes)

**Objectif** : valider que la boucle Thought→Code→Observation fonctionne de bout en bout, **avant** d'ajouter les limites d'itérations/tokens qui compliqueraient le debug (conseil explicite du sujet, §V.1.1).

Réf. §V.1.

- [ ] Implémenter la boucle agent (appel LLM → extraction code → exécution sandbox → réinjection observation → itération)
- [ ] Extraction du format principal (blocs ```` ```python ``` ````) en premier ; ajouter XML/JSON/ReAct ensuite une fois le flux principal validé
- [ ] Rédiger un premier system prompt : doc des outils, exemples Thought/Code/Observation
- [ ] Implémenter les 5 cas de feedback explicite obligatoires (pas de code trouvé, code malformé, timeout, sortie tronquée, erreur de syntaxe après edit)
- [ ] Tester manuellement sur 1 tâche MBPP simple, avec le modèle LLM le plus capable disponible et **sans** limite d'itérations/tokens
- [ ] Observer et documenter les 3-5 premières itérations (comportement réel vs. attendu) — sert de matière pour le futur `SUIVI_AVANCEMENT.md`

**Definition of Done** : l'agent résout au moins une tâche MBPP simple de bout en bout, sans limites artificielles.

---

## Phase 4 — Agent MBPP complet

**Objectif** : conformité complète à la CLI, aux modèles de données, et aux limites d'examen MBPP.

Réf. §V.3, §VI.1.1, §VI.2.

- [ ] CLI `agent_mbpp` conforme (`--task-file`, `--output`, `--model-name`, `--provider-url`)
- [ ] Modèles Pydantic `MBPPTaskInput`, `StepMetrics`, `SolutionOutput` remplis avec de vraies données d'exécution (pas de valeurs fabriquées — vérifié en soutenance, §VI.4)
- [ ] `max_iterations` configurable
- [ ] Appliquer progressivement les limites réelles (10 itérations / 6k in / 1.5k out / 120s) et vérifier que l'agent reste fonctionnel sous contrainte
- [ ] Tester sur plusieurs tâches MBPP (pas une seule) pour détecter un éventuel surapprentissage sur le cas de test initial

**Definition of Done** : `moulinette_eval validate mbpp ...` passe sur au moins 4/5 tâches tirées aléatoirement, dans les limites imposées.

---

## Phase 5 — Sandbox étendu + outils SWE-bench

**Objectif** : ajouter le support Docker/testbed et les outils fichiers/recherche/exécution restants.

Réf. §V.4, §V.5.

- [ ] Décider de l'architecture Docker : sandbox déployé dans le conteneur, ou sandbox hôte + pont MCP vers Docker
- [ ] Implémenter `read_file`, `edit_file`, `list_files` (format `cat -n` pour `read_file`)
- [ ] Implémenter `search_code`, `search_function_or_class_definition_in_code`, `find_references` (format type grep)
- [ ] Implémenter `run_command` (stdout/stderr/exit code)
- [ ] Implémenter `get_patch` (`git -c core.fileMode=false diff`)
- [ ] Mettre en place le nettoyage systématique des conteneurs après exécution
- [ ] `mcp_tools_swebench.py` à la racine du dépôt

**Definition of Done** : chaque outil testé indépendamment (hors boucle agent), conforme aux formats de sortie imposés.

---

## Phase 6 — Agent SWE-bench

**Objectif** : agent complet capable de résoudre des tâches SWE-bench réelles.

Réf. §V.4, §VI.1.2, §VI.2.

- [ ] CLI `agent_swebench` conforme
- [ ] Tester d'abord sur les tâches suggérées par le sujet comme point de départ simple : `sympy__sympy-14711`, `sympy__sympy-13480`, `pydata__xarray-4629`
- [ ] Résoudre la tâche cible manuellement (à la main, avec les mêmes outils que l'agent) avant d'affiner le prompt — le sujet insiste sur cette méthode (§V.4, « Think about it »)
- [ ] Découper le script d'éval en sous-objectifs, suivre les tests individuels plutôt que d'attendre le script complet
- [ ] Remplir `SolutionOutput` avec `system_prompt` et tous les champs de traçabilité (`llm_output`, `sandbox_input`, `sandbox_output`, `retries`)
- [ ] Appliquer les limites réelles (30 itérations / 300k in / 10k out / 900s)
- [ ] Vérifier l'absence de triche : aucune solution récupérée depuis PR/issues/sources externes (§VI.4.1 — violation = note 0)

**Definition of Done** : `moulinette_eval validate swebench ...` passe sur au moins 2/3 tâches tirées aléatoirement.

---

## Phase 7 — Multi-provider et gestion des clés

**Objectif** : abstraction propre permettant de changer de provider sans réécrire l'agent.

Réf. §V.6.

- [ ] Interface commune pour appeler plusieurs providers (uniquement gratuits — aucun compte facturable)
- [ ] Support multi-clé par provider + rotation automatique en cas de rate limit/quota épuisé
- [ ] Implémentation des `stop_sequences` pour éviter que le modèle n'hallucine une sortie d'outil
- [ ] Vérifier que changer de provider ne nécessite pas de refactoring majeur (test concret : brancher un 2e provider et mesurer l'effort réel)

**Definition of Done** : au moins deux providers gratuits différents fonctionnent avec la même base de code agent, sans clé en dur.

---

## Phase 8 — Benchmark de modèles

**Objectif** : produire `BENCHMARK_REPORT.md` conforme.

Réf. §V.7.

- [ ] Sélectionner ≥5 modèles et ≥3 tâches SWE-bench communes, justifier le choix des tâches
- [ ] Construire le tableau de résultats (Pass/Fail, itérations, tokens in/out, temps) pour chaque couple modèle × tâche
- [ ] Mesurer la fiabilité provider (temps de réponse moyen, retries, disponibilité)
- [ ] Choisir et mesurer au moins 2 métriques intermédiaires (mesure manuelle acceptée, l'important est l'analyse pas l'outillage)
- [ ] Réaliser au moins une étude d'ablation (avant/après un changement de prompt, d'outils, ou de paramètres, à modèle et tâches fixés)
- [ ] Rédiger la conclusion : modèle(s) retenu(s) et pourquoi, modèle(s) écarté(s) et pourquoi, en s'appuyant sur les données produites
- [ ] Conserver tous les `solution.json` correspondants dans le dépôt

**Definition of Done** : `BENCHMARK_REPORT.md` présent à la racine avec les 6 sous-sections exigées, données réelles et traçables.

---

## Phase 9 — Durcissement, README, et répétition de soutenance

**Objectif** : passer les tests de sécurité, finaliser la documentation, se préparer aux modifications live.

Réf. §VI, §VII.

- [ ] Faire tourner un jeu de tests de sécurité sandbox : import bloqué, builtin bloqué, réseau bloqué, path hors allowlist, timeout, limite mémoire, protocole MCP
- [ ] Rédiger `README.md` en anglais avec toutes les sections imposées (Description, Instructions, Resources incluant l'usage de l'IA, + Architecture système, boucle agent, design du sandbox, détails des outils, résultats de benchmark), 1ère ligne en italique avec les logins
- [ ] Vérifier qu'aucune clé API n'est présente dans le code source (grep systématique avant rendu)
- [ ] S'entraîner en équipe à faire une petite modification live sur l'agent et la relancer sur une tâche MBPP en 2-5 minutes (simulation de la soutenance, §VI.4)
- [ ] Vérifier que le dépôt ne contient ni images Docker, ni poids de modèles, ni sorties générées volumineuses (§VIII)
- [ ] Relire `CAHIER_DES_CHARGES.md` section par section comme checklist finale de conformité

**Definition of Done** : `exam_sandbox.sh` passe à 100 %, README conforme, dépôt propre, équipe capable d'expliquer chaque décision d'architecture.

---

## Vue d'ensemble (ordre recommandé)

```
Phase 0 (socle)
   → Phase 1 (sandbox seul)
      → Phase 2 (MCP + 1er outil)
         → Phase 3 (boucle agent minimale, sans limites)
            → Phase 4 (agent MBPP complet + limites réelles)
               → Phase 5 (sandbox Docker + outils SWE-bench)
                  → Phase 6 (agent SWE-bench complet)
                     → Phase 7 (multi-provider) ─┐
                     → Phase 8 (benchmark report) ┘ (peuvent être menées en parallèle par deux sous-groupes)
                        → Phase 9 (durcissement + README + répétition)
```

Les phases 7 et 8 peuvent être menées en parallèle par deux membres différents une fois la Phase 6 stabilisée, puisqu'elles sollicitent des compétences différentes (abstraction provider vs. analyse de données).

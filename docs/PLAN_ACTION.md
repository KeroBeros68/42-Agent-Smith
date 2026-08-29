# Plan d'Action — Agent Smith

> Ce plan traduit les recommandations explicites du sujet (§V.1.1 « Development Approach ») en phases concrètes. L'ordre proposé suit deux principes directement issus du sujet :
> 1. **Le sandbox est un prérequis** aux deux agents — aucun agent n'est testable sans lui (§III.1 pt.3, §V.2).
> 2. **MBPP avant SWE-bench** — le sujet présente MBPP comme le benchmark le plus simple (problèmes algorithmiques isolés vs. bugs réels en conteneurs Docker), et le sujet lui-même traite MBPP (§V.3) avant SWE-bench (§V.4).
>
> Chaque phase liste : objectif, tâches, critère de sortie (« Definition of Done »), et référence au sujet.
>
> **Mise à jour du 2026-08-29** : l'état des cases reflète la **progression réelle vérifiée** du dépôt, documentée dans les audits (`docs/AUDIT_*.md`) et confirmée par des validations **moulinette réelles** (MBPP tâche 282 et SWE-bench `django__django-15851` passent en conditions d'examen). Légende : `[✅]` = fait · `[🟡]` = en cours (partiel) · `[❌]` = non démarré.
>
> **Reste à compléter par l'équipe** : dates et répartition nominative des tâches pour les phases en cours. Aucune échéance n'est fixée ici — le sujet ne mentionne pas de deadline, ne pas en inventer.

---

## Vue d'ensemble de la progression (2026-08-29)

| Phase | Objet | Statut |
|---|---|---|
| 0 | Socle du projet | ✅ Terminée |
| 1 | Sandbox (sans MCP) | ✅ Terminée — vérifiée en conditions réelles Docker |
| 2 | Intégration MCP + 1er outil (MBPP) | ✅ Terminée — stdio **et** HTTP testés en réel |
| 3 | Boucle agent minimale | 🟡 En cours — DoD atteint ; 1 point de conformité (§ feedbacks) ouvert |
| 4 | Agent MBPP complet | 🟡 En cours — validé sur 1 tâche ; pas encore 4/5 aléatoires |
| 5 | Sandbox étendu + outils SWE-bench | ✅ Terminée — 9/9 outils testés contre une vraie tâche Django |
| 6 | Agent SWE-bench | 🟡 En cours — validé sur 1 tâche ; pas encore 2/3 aléatoires |
| 7 | Multi-provider et gestion des clés | 🟡 En cours — abstraction + rotation OK ; stop_sequences à implémenter |
| 8 | Benchmark de modèles | ❌ Non démarrée — pas de `BENCHMARK_REPORT.md` |
| 9 | Durcissement, README, répétition | 🟡 En cours — README encore squelette, pas d'examen blanc |

**Avancement global estimé** : ≈ 60 % (6 des 8 blocs fonctionnels livrés et vérifiés ; il reste la généralisation multi-tâches, le benchmark, et le durcissement final).

---

## Phase 0 — Socle du projet

**Objectif** : poser une base saine avant d'écrire la moindre logique agentique.

- [✅] Initialiser la structure de dépôt (`student/`, `moulinette/`, `cache/`, config racine) — structure interne libre (§VIII)
- [✅] Configurer `uv` + Python 3.10 (`requires-python == "3.10.*"` dans `pyproject.toml`, `uv.lock` versionné, cibles `install`/`lint` dans le `Makefile`) (§IV.1)
- [✅] Mettre en place le chargement de clés API via `.env` / variables d'environnement (§VI, §VI.3) — **aucune clé en dur** (`.env` gitignoré, `.env.example` versionné ; `provider/base.py` lit `{PROVIDER}_API_KEY(S)`)
- [✅] Définir les premiers modèles Pydantic communs (`SandboxConfig` dans `sandbox/config.py` ; `StepMetrics`/`SolutionOutput` dans `agent_core/schemas.py` ; squelettes MBPP/SWE-bench)
- [✅] Décider de l'architecture cible — sandbox = process Docker isolé + pont MCP côté hôte (`sandbox/session.py`, `mcp_bridge.py`) ; boucle agent benchmark-agnostique (`agent_core/loop.py`) ; choix documentés et défendables (§II)

**Definition of Done** : `uv run` fonctionne, structure de dossiers créée, `.env.example` versionné (sans vraies clés). ✅ **Atteinte.**

---

## Phase 1 — Sandbox (sans MCP)

**Objectif** : avoir un sandbox qui exécute du code Python arbitraire de façon sûre, avant même de parler d'agent ou de LLM.

Réf. §V.2.

- [✅] Choisir l'approche d'isolation — **process séparé** (conteneur Docker `network:none`, `read_only`, `mem_limit`, `pids_limit`), décision motivée (sécurité / timeout / communication) et documentée dans `student/sandbox/README.md` (question posée explicitement par le sujet, §V.2 fin)
- [✅] Implémenter les restrictions : imports (allowlist via hook `sys.meta_path`, `executor/restrictions.py`), filesystem (`allowed_directories`, `open` remplacé par une version restreinte), réseau (aucun), timeout (`watchdog.py`, `signal.alarm`), mémoire (`mem_limit` Docker), builtins restreints (allowlist `SAFE_BUILTINS`) — stdlib uniquement, pas de `RestrictedPython`
- [✅] Implémenter `final_answer` comme construct sandbox (exception `_FinalAnswerSignal` dans `runner.py`, pas un outil MCP)
- [✅] Vérifier explicitement que `KeyboardInterrupt`/`SystemExit` remontent sans être capturés (`except Exception` uniquement dans `runner.py`/`cli.py`)
- [✅] Implémenter la CLI `uv run sandbox` (avec/sans fichier de config JSON — les 4 formes du §V.2.1)
- [✅] Implémenter le mode REPL interactif (boucle lecture/exécution multi-lignes via `codeop.compile_command()`, sortie sur `exit`/Ctrl+D/EOF, Ctrl+C réinitialise le buffer)

**Definition of Done** : `uv run sandbox sandbox_template.json` ouvre un REPL, refuse un import hors allowlist, refuse un accès disque hors `allowed_directories`, coupe une boucle infinie au timeout, appelle `final_answer(...)` correctement. ✅ **Atteinte** — chaque point vérifié en conditions réelles Docker (voir « Corrigés » de `AUDIT_SANDBOX.md`).

---

## Phase 2 — Intégration MCP générique + premier outil (MBPP)

**Objectif** : connecter le sandbox à un serveur MCP et exposer ses outils comme fonctions Python, sans coder en dur les outils d'un seul serveur.

Réf. §V.2.5, §V.2.6.

- [✅] Client MCP dans le sandbox, support **stdio** et **HTTP streamable** — `mcp_bridge.py` (facade synchrone sur `fastmcp.Client`, pont via thread + boucle asyncio dédiée) ; les deux transports testés de bout en bout contre le vrai serveur (§V.2.5)
- [✅] Découverte dynamique des outils/ressources/prompts exposés par le serveur connecté (`MCPBridge.list_tools()`, stubs générés depuis `inputSchema` dans `runner.py`)
- [✅] Génération dynamique du **manuel du sandbox** à partir des schémas d'outils découverts (`manual.build_manual(tools)`) — y compris l'exemple d'appel synthétisé
- [✅] Implémenter `mcp_tools_mbpp.py` (racine du dépôt) avec au minimum `run_tests` — conforme §V.3.2, audité (`AUDIT_MCP_SERVERS/AUDIT_MCP_TOOLS_MBPP.md`)
- [✅] Test croisé : le manuel et les wrappers s'adaptent automatiquement au serveur connecté — vérifié en pratique avec deux serveurs réels différents (MBPP et SWE-bench) dont les 9+1 outils diffèrent, sans aucun codage en dur des schémas (anticipe le test avec « serveur MCP inconnu », §V.2.5)

**Definition of Done** : `uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json` expose `run_tests()` comme fonction Python appelable, et le manuel généré liste bien cet outil. ✅ **Atteinte.**

---

## Phase 3 — Boucle agent minimale (sur le modèle le plus capable, sans contraintes)

**Objectif** : valider que la boucle Thought→Code→Observation fonctionne de bout en bout, **avant** d'ajouter les limites d'itérations/tokens qui compliqueraient le debug (conseil explicite du sujet, §V.1.1).

Réf. §V.1.

- [✅] Implémenter la boucle agent (`agent_core/loop.py`, benchmark-agnostique) — appel LLM → extraction code → exécution sandbox → réinjection observation → itération ; arrêt sur `final_answer`
- [✅] Extraction du format principal (blocs ```` ```python ``` ````) **et** des formats XML (`<invoke>`), JSON/Hermes (`<tool_call>`), ReAct (`Action:`/`Action Input:`) — `agent_core/parsing.py` couvre les formats (a) à (d) du §V.1.2, convertis en appels de fonctions Python avant exécution
- [✅] Rédiger un premier system prompt : doc des outils (générée par `manual.py`), exemples Thought/Code/Observation (assemblés par `build_system_prompt` dans les deux points d'entrée)
- [🟡] Implémenter les 5 cas de feedback explicite obligatoires — 2 sur 5 confirmés : « No valid code block was found » et avertissement de bloc non fermé (`parsing.py`/`loop.py`). **Reste à vérifier/fermer** : timeout avec sortie partielle, troncature de sortie outil signalée au LLM, erreur de syntaxe/lint après `edit_file` (§V.1 — le LLM ne doit jamais deviner)
- [✅] Tester manuellement sur 1 tâche MBPP simple, avec le modèle LLM le plus capable disponible et **sans** limite d'itérations/tokens — runs réels des 2026-08-21/26/27 (modèle `deepseek/deepseek-v4-flash`, conteneur Docker, clé API réelle)
- [✅] Observer et documenter les 3-5 premières itérations (comportement réel vs. attendu) — diagnostic détaillé et itérations du prompt consignés dans `AUDIT_AGENT_CORE.md` (fait matière pour `SUIVI_AVANCEMENT.md`)

**Definition of Done** : l'agent résout au moins une tâche MBPP simple de bout en bout, sans limites artificielles. ✅ **Atteinte** — dépassée : la solution est désormais aussi validée par la moulinette (voir Phase 4).

---

## Phase 4 — Agent MBPP complet

**Objectif** : conformité complète à la CLI, aux modèles de données, et aux limites d'examen MBPP.

Réf. §V.3, §VI.1.1, §VI.2.

- [✅] CLI `agent_mbpp` conforme (`--task-file`, `--output`, `--model-name`, `--provider-url`) — `student/agent_mbpp/__main__.py`, `python -m agent_mbpp`
- [✅] Modèles Pydantic `MBPPTaskInput`, `StepMetrics`, `SolutionOutput` remplis avec de vraies données d'exécution (`cache/mbpp_solution.json` — tâche 305, 3 itérations, tokens réels ; pas de valeurs fabriquées — vérifié en soutenance, §VI.4)
- [✅] `max_iterations` configurable (`--max-iterations`, défaut 10)
- [🟡] Appliquer progressivement les limites réelles (10 itérations / 6k in / 1.5k out / 120s) — **validé par la moulinette** sur la tâche 282 (2/10 it., 899/6000 tokens in, 360/1500 out, 56.6 s/120 s → `Metrics: VALID`, `Overall: PASSED`). **Manque** : le garde-fou *proactif* côté agent sur les budgets cumulés tokens/temps (le `max_iterations` borne les itérations, pas les tokens) — priorité listée dans `AUDIT_MBPP.md`
- [🟡] Tester sur plusieurs tâches MBPP (pas une seule) pour détecter un éventuel surapprentissage sur le cas de test initial — 2 tâches réelles produites (282, 305) ; **pas encore** de campagne de ≥5 tâches aléatoires

**Definition of Done** : `moulinette_eval validate mbpp ...` passe sur au moins 4/5 tâches tirées aléatoirement, dans les limites imposées. 🟡 **En cours** — 1/1 tâche validée en conditions réelles ; reste la campagne 4/5.

---

## Phase 5 — Sandbox étendu + outils SWE-bench

**Objectif** : ajouter le support Docker/testbed et les outils fichiers/recherche/exécution restants.

Réf. §V.4, §V.5.

- [✅] Décider de l'architecture Docker — **option (b)** : sandbox sur l'hôte, outils MCP qui pontent dans le conteneur via `docker exec` (le code exécuté par l'agent tourne dans le conteneur restreint) ; conteneur nettoyé systématiquement (context manager + `finally`)
- [✅] Implémenter `read_file`, `edit_file`, `list_files` (format `cat -n` pour `read_file`) — testés contre le vrai dépôt Django
- [✅] Implémenter `search_code`, `search_function_or_class_definition_in_code`, `find_references` (format type grep) — testés (216 références réelles trouvées pour `find_references`)
- [✅] Implémenter `run_command` (stdout/stderr/exit code) — testé
- [✅] Implémenter `get_patch` (`git -c core.fileMode=false diff`) — flag conforme §V.4 vérifié, diff testé avant/après édition
- [✅] Mettre en place le nettoyage systématique des conteneurs après exécution
- [✅] `mcp_tools_swebench.py` à la racine du dépôt — 9 outils sur 9, formats de sortie conformes au sujet mot pour mot (`AUDIT_MCP_SERVERS/AUDIT_MCP_TOOLS_SWEBENCH.md`)

**Definition of Done** : chaque outil testé indépendamment (hors boucle agent), conforme aux formats de sortie imposés. ✅ **Atteinte** — 9/9 testés de bout en bout contre `django__django-15851` (dont `run_tests()` qui rejoue les 10 tests réels).

---

## Phase 6 — Agent SWE-bench

**Objectif** : agent complet capable de résoudre des tâches SWE-bench réelles.

Réf. §V.4, §VI.1.2, §VI.2.

- [✅] CLI `agent_swebench` conforme (`--task-file`, `--output`, `--model-name`, `--provider-url`) — `student/agent_swebench/__main__.py`
- [🟡] Tester d'abord sur les tâches suggérées par le sujet comme point de départ simple : `sympy__sympy-14711`, `sympy__sympy-13480`, `pydata__xarray-4629` — **non encore fait** ; la validation réelle porte pour l'instant sur `django__django-15851`
- [🟡] Résoudre la tâche cible manuellement (à la main, avec les mêmes outils que l'agent) avant d'affiner le prompt — méthodologie appliquée (itérations du prompt guidées par l'observation des runs réels), mais l'exercice « manuel » systématique n'est pas documenté comme livrable
- [✅] Découper le script d'éval en sous-objectifs, suivre les tests individuels plutôt que d'attendre le script complet — `run_tests()` rapporte les verdicts test par test (10 tests réels, échec attendu par la tâche identifié)
- [✅] Remplir `SolutionOutput` avec `system_prompt` et tous les champs de traçabilité (`llm_output`, `sandbox_input`, `sandbox_output`, `retries`) — remplis par `loop.py`/les points d'entrée avec de vraies données de run
- [🟡] Appliquer les limites réelles (30 itérations / 300k in / 10k out / 900s) — **validé par la moulinette** sur `django__django-15851` (15/30 it., 65 435/300 000 tokens in → `Metrics: VALID`, `Correctness: PASSED` avec `RESOLVED_FULL`) ; même réserve que MBPP : pas de garde-fou proactif côté agent sur les budgets cumulés
- [✅] Vérifier l'absence de triche : aucune solution récupérée depuis PR/issues/sources externes (§VI.4.1 — violation = note 0) — le flot de données ne fait qu'explorer `/testbed` via les outils ; pas d'accès réseau depuis le conteneur

**Definition of Done** : `moulinette_eval validate swebench ...` passe sur au moins 2/3 tâches tirées aléatoirement. 🟡 **En cours** — 1/1 tâche validée en conditions réelles ; reste la campagne 2/3 et les tâches de départ suggérées.

---

## Phase 7 — Multi-provider et gestion des clés

**Objectif** : abstraction propre permettant de changer de provider sans réécrire l'agent.

Réf. §V.6.

- [✅] Interface commune pour appeler plusieurs providers (uniquement gratuits — aucun compte facturable) — `provider/base.py` : abstraction `AbstractLLM`, implémentation `LLM` sur **LiteLLM Router** (format `provider/model` requis)
- [✅] Support multi-clé par provider + rotation automatique en cas de rate limit/quota épuisé — lecture de `{PROVIDER}_API_KEY` **et** `{PROVIDER}_API_KEYS` (liste séparée par virgules), Router avec `usage-based-routing`, `allowed_fails=2`, `cooldown_time=5`
- [🟡] Implémenter les `stop_sequences` pour éviter que le modèle n'hallucine une sortie d'outil — **non implémenté** (aucun `stop` passé dans `get_response`) ; recommandation explicite du sujet (§V.6, « Think about it ») à traiter avant la généralisation multi-modèles
- [🟡] Vérifier que changer de provider ne nécessite pas de refactoring majeur (test concret : brancher un 2e provider et mesurer l'effort réel) — l'abstraction LiteLLM le suggère, mais **un seul provider réellement exercé** à ce jour (`deepseek/deepseek-v4-flash`) ; aucun test cross-provider documenté

**Definition of Done** : au moins deux providers gratuits différents fonctionnent avec la même base de code agent, sans clé en dur. 🟡 **En cours** — abstraction et rotation en place ; reste le test sur un 2e provider et les `stop_sequences`.

---

## Phase 8 — Benchmark de modèles

**Objectif** : produire `BENCHMARK_REPORT.md` conforme.

Réf. §V.7.

- [❌] Sélectionner ≥5 modèles et ≥3 tâches SWE-bench communes, justifier le choix des tâches
- [❌] Construire le tableau de résultats (Pass/Fail, itérations, tokens in/out, temps) pour chaque couple modèle × tâche
- [❌] Mesurer la fiabilité provider (temps de réponse moyen, retries, disponibilité)
- [❌] Choisir et mesurer au moins 2 métriques intermédiaires (mesure manuelle acceptée, l'important est l'analyse pas l'outillage)
- [❌] Réaliser au moins une étude d'ablation (avant/après un changement de prompt, d'outils, ou de paramètres, à modèle et tâches fixés)
- [❌] Rédiger la conclusion : modèle(s) retenu(s) et pourquoi, modèle(s) écarté(s) et pourquoi, en s'appuyant sur les données produites
- [❌] Conserver tous les `solution.json` correspondants dans le dépôt

**Definition of Done** : `BENCHMARK_REPORT.md` présent à la racine avec les 6 sous-sections exigées, données réelles et traçables. ❌ **Non démarrée** — aucun `BENCHMARK_REPORT.md` dans le dépôt ; les `solution.json` isolés existent (`cache/`) mais pas de campagne comparative.

---

## Phase 9 — Durcissement, README, et répétition de soutenance

**Objectif** : passer les tests de sécurité, finaliser la documentation, se préparer aux modifications live.

Réf. §VI, §VII.

- [🟡] Faire tourner un jeu de tests de sécurité sandbox : import bloqué, builtin bloqué, réseau bloqué, path hors allowlist, timeout, limite mémoire, protocole MCP — les 6 contraintes §V.2.3 ont été **vérifiées en conditions réelles Docker** (voir `AUDIT_SANDBOX.md`), mais **pas encore** via le script officiel `exam_sandbox.sh` de bout en bout
- [❌] Rédiger `README.md` en anglais avec toutes les sections imposées (Description, Instructions, Resources incluant l'usage de l'IA, + Architecture système, boucle agent, design du sandbox, détails des outils, résultats de benchmark), 1ère ligne en italique avec les logins — **README actuel = squelette** (exemples JSON-RPC d'appels d'outils uniquement, cf. §VII)
- [✅] Vérifier qu'aucune clé API n'est présente dans le code source — `.env` gitignoré, seul `.env.example` est versionné ; scan source sans clé en dur. **À re-vérifier par grep systématique juste avant le rendu** (réflexe à garder)
- [❌] S'entraîner en équipe à faire une petite modification live sur l'agent et la relancer sur une tâche MBPP en 2-5 minutes (simulation de la soutenance, §VI.4)
- [🟡] Vérifier que le dépôt ne contient ni images Docker, ni poids de modèles, ni sorties générées volumineuses (§VIII) — pas d'images ni de poids ; **à nettoyer** : `test.json` (résidu d'un test de build échoué, non suivi) et `cache/swebench_solution.json` vide (0 octet, placeholder) avant le rendu ; les `solution.json` de benchmark, eux, doivent être **conservés** (requis par §V.7)
- [❌] Relire `CAHIER_DES_CHARGES.md` section par section comme checklist finale de conformité

**Definition of Done** : `exam_sandbox.sh` passe à 100 %, README conforme, dépôt propre, équipe capable d'expliquer chaque décision d'architecture. 🟡 **En cours** — la sécurité sandbox est vérifiée, mais README, examen blanc et répétition de soutenance restent à faire.

---

## Vue d'ensemble (ordre recommandé)

```
Phase 0 (socle) ✅
   → Phase 1 (sandbox seul) ✅
      → Phase 2 (MCP + 1er outil) ✅
         → Phase 3 (boucle agent minimale, sans limites) 🟡
            → Phase 4 (agent MBPP complet + limites réelles) 🟡
               → Phase 5 (sandbox Docker + outils SWE-bench) ✅
                  → Phase 6 (agent SWE-bench complet) 🟡
                     → Phase 7 (multi-provider) ─┐ 🟡
                     → Phase 8 (benchmark report) ┘ ❌ (peuvent être menées en parallèle par deux sous-groupes)
                        → Phase 9 (durcissement + README + répétition) 🟡
```

Les phases 7 et 8 peuvent être menées en parallèle par deux membres différents une fois la Phase 6 stabilisée, puisqu'elles sollicitent des compétences différentes (abstraction provider vs. analyse de données).

**Prochaines étapes naturelles** (par ordre de priorité) :
1. **Phase 8** : lancer la campagne benchmark ≥5 modèles × ≥3 tâches (bloque le `BENCHMARK_REPORT.md`, exigence dure du §V.7) — s'appuie sur les agents déjà validés.
2. **Phase 4/6** : généraliser aux campagnes aléatoires (4/5 MBPP, 2/3 SWE-bench) pour valider la non-surabondance sur 1 tâche.
3. **Phase 7** : implémenter `stop_sequences` et valider un 2e provider gratuit.
4. **Phase 9** : réécrire le `README.md`, nettoyer les résidus (`test.json`, cache vide), répéter la modification live.

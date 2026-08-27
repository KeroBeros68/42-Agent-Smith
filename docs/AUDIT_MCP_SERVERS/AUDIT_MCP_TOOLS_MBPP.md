# Audit — `mcp_tools_mbpp.py`

> Audit de conformité du serveur MCP MBPP par rapport au sujet officiel (`subject-1-1.txt`, v1.1, §V.3.2) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-27
> **Périmètre** : `mcp_tools_mbpp.py` (racine du dépôt)
> **Méthode** : points positifs/négatifs justifiés par référence exacte au texte du sujet, par mypy/flake8, ou par comportement réel du code — même méthodologie que `AUDIT_SWEBENCH_TOOLS.md` et `AUDIT_SANDBOX.md`. `flake8` et `mypy` re-vérifiés à 0 erreur le jour de l'audit.

---

## Récapitulatif de conformité §V.3.2 — 1 outil obligatoire sur 1, codé **et** fonctionnel

> Contrairement à `mcp_tools_swebench.py` (bloqué par le trou `/testbed`, voir `AUDIT_SWEBENCH_TOOLS.md`), ce serveur n'a **aucune dépendance à un filesystem partagé** : `run_tests` n'exécute que du code Python en sous-processus via `sys.executable`. L'architecture « serveur MCP spawné sur l'hôte » est donc **correcte ici** — c'est exactement le cas où le modèle hôte fonctionne de bout en bout, là où il casse structurellement pour SWE-bench.

| Outil | Section | Description (du sujet) | État |
|---|---|---|---|
| `run_tests(code)` | §V.3.2 | « The `run_tests` tool » — exécute les tests unitaires publics contre la solution de l'agent | ✅ Conforme et fonctionnel |

---

## ✅ Bon

1. **Pré-vérification de syntaxe `compile()` avec retour explicite** — §V.1.3. `compile(f"{imports}\n\n{code}", "<mbpp_solution>", "exec")` avant toute exécution ; en cas de `SyntaxError`, message clair avec la **position** (`line {e.lineno}`) et la consigne de corriger et ré-essayer. L'agent n'est jamais laissé sans explication : pas d'échec silencieux, exactement l'esprit de §V.1.3 (« An edit introduced a syntax error » → feedback explicite).
2. **Patch `os._exit` (OS_EXIT_PATCH) contre le faux-positif classique** — `os._exit = PATCH_EXIT` où `PATCH_EXIT(status)` fait `sys.exit(1)`. C'est la défense directe contre le hack MBPP le plus connu : un modèle qui appelle `os._exit(0)` pour « réussir » sans exécuter les tests. L'historique git montre la progression de ce point (`f411bfa` → `6288229` → `160734e`), preuve qu'il a été traité comme une vraie vulnérabilité et non supposé. Vérifié dans le code : le patch est injecté **avant** le `try:` qui contient la solution, donc `import os` dans la solution récupère le module déjà patché.
3. **`except SystemExit` dans le sous-processus convertit tout `exit()`/`quit()`/`sys.exit()` en échec** — `try: … except SystemExit: sys.exit(1)`. Une solution qui appelle `exit(0)` (ou `sys.exit(0)`) lève `SystemExit(0)`, interceptée → code de retour 1 → test marqué en échec. Aucun chemin `exit(0)` ne produit un faux-passage.
4. **Isolation par test dans un sous-processus dédié, avec timeout** — chaque `TASK.test_list[i]` tourne dans son propre `subprocess.run([sys.executable, "-c", …], timeout=TIMEOUT_DELAY_SEC)` (10 s). Une solution qui boucle à l'infini ou plante **ne tue pas le serveur MCP** : `TimeoutExpired` est intercepté et le test est simplement marqué `# TIMEDOUT AFTER 10 SECONDS`. « All errors must be handled gracefully » (§IV.1.1) respecté ; le serveur survit à n'importe quel comportement de la solution.
5. **`input=""` force `stdin=PIPE` avec EOF immédiat** — l'enfant ne bloque jamais sur un stdin hérité. Critique sur transport **stdio**, où le serveur MCP écoute déjà sur son propre stdin : sans cela, le sous-processus de test hériterait du stdin du serveur et se disputerait les frames JSON Lines. Même garde que `run_tests` de SWE-bench, cohérence entre les deux serveurs.
6. **Extraction du motif d'échec depuis la dernière ligne de stderr, tronquée à 300 caractères** — `tb_lines[-1].strip()` récupère le message d'erreur réel (`NameError: name 'sub_list' is not defined`, par exemple), et `reason[:300]` borne la sortie. C'est exactement le feedback que l'agent MBPP doit recevoir pour corriger (§V.1.3 : l'agent ne doit jamais deviner). Format `"{test}  # {reason}"` : l'agent voit quel test a échoué **et** pourquoi.
7. **Résultats agrégés et lisibles** — `failed_tests` collecte toutes les erreurs, puis `"Error during the following tests :\n" + "\n".join(...)` renvoie l'ensemble en une seule réponse ; si tout passe, `"All test passed successfully !"`. Décision explicite et lisible par le LLM, ni crash ni retour ambigu.
8. **Cas limites du chargement de tâche traités proprement** — `TASK` chargé une fois au démarrage depuis `MBPP_TASK_JSON`, avec `ValidationError`/`JSONDecodeError` interceptées et fallback `None`. Si `None` : message clair sur `stderr` + `exit(1)` — le serveur **refuse de démarrer** plutôt que de servir des tests vides (`f5a64000` a corrigé le cas « pas de message d'erreur au lancement sans tâche »). Le `TASK is None` est re-vérifié en entrée du tool avec un `MBPPException` descriptif (défense en profondeur).
9. **Gestion du cas « aucun test disponible »** — `if len(TASK.test_list) == 0: return "There are no available tests… You may skip testing."`. Le serveur dit explicitement à l'agent de passer, au lieu de boucler sur zéro test.
10. **Sélection de transport `Literal["http","stdio"]` correctement typée** — `mode: Literal["http", "stdio"]` affectée par condition explicite, validation de `MCP_TRANSPORT` avec un `TypeError` clair si valeur inconnue, défaut `stdio` conforme au docstring. Résout proprement le même `str`-brut-incompatible-avec-`Literal` que le serveur SWE avait eu à corriger (mypy à 0 erreur).
11. **L'architecture hôte est correcte pour MBPP** — contrairement à SWE-bench, aucun outil ici n'a besoin de `/testbed` ni de Docker. `run_tests` n'exige qu'un interpréteur Python en sous-processus, disponible sur l'hôte. C'est le cas où le modèle « MCP tools operate outside the sandbox » (l. 276-278) fonctionne tel quel, sans le trou architectural de `mcp_tools_swebench.py`.
12. **`flake8` et `mypy` propres** — `flake8` → exit 0, `mypy` → *Success: no issues found in 1 source file*, re-vérifiés le jour de l'audit. Code lisible, docstring de module claire sur les prérequis (`MBPP_TASK_JSON`, `MCP_TRANSPORT`).

---

## ❌ Mauvais

1. **`TIMEOUT_DELAY_SEC = 10` codé en dur, non configurable** — alors que `SandboxConfig.max_execution_time_seconds` est configurable (§V.2.3), le timeout par-test du serveur MCP est figé. La limite MBPP globale (§VI.1.1) est de **120 s** pour toute la tâche ; un test isolé qui mettrait >10 s (rare en MBPP, mais possible) serait coupé à tort. À extraire vers la config ou à documenter comme choix assumé.
   > **Piste de solution** : lire le timeout depuis la variable d'environnement au chargement, avec un défaut sain — `TIMEOUT_DELAY_SEC = int(os.environ.get("MBPP_TEST_TIMEOUT_SEC", "10"))` (valeurs invalides → retomber sur 10 s). Comme le sandbox l'expose déjà via `SandboxConfig.max_execution_time_seconds`, le plus propre serait de laisser l'hôte (le sandbox qui spawn le serveur) injecter la valeur au démarrage, pour une source de config unique. Documenter ensuite que le per-test ne doit jamais dépasser le budget global de 120 s.
2. **Le patch `os._exit` est contournable par `from os import _exit`** — si la solution fait `from os import _exit`, elle capture la **vraie** fonction `os._exit` (avant patch) et peut appeler `_exit(0)` pour sortir avec code 0 sans passer les tests. Le patch remplace l'attribut sur le module `os`, pas la référence déjà liée dans le namespace de la solution. Défense en profondeur, pas une fermeture. (Un modèle qui fait `try: os._exit(0) except SystemExit: pass` avale aussi le `sys.exit(1)` du patch — de toute façon un comportement délibérément hostile.)
   > **Piste de solution** : au lieu de ne patch que `os._exit`, neutraliser la sortie par un garde au niveau de l'échec plutôt que de l'entrée. Option A — wrapper de test : envelopper l'exécution dans un process enfant **et** vérifier, dans le code injecté, que le contrôle atteint bien le test en plaçant un marqueur : si le code quitte avant d'arriver au test (quel que soit le moyen, `os._exit`, `sys.exit`, `quit`, `kill`), le marqueur manque → test marqué en échec. Concrètement : injecter `_REACHED = True` juste après le code de la solution et avant chaque test ; si `_REACHED` est absent au moment du test, la solution a court-circuité → échec. Option B (plus radicale, prévue par le sujet §V.2.3) : forcer l'absence des chemins de sortie en exécutant la solution sous les mêmes restrictions que le sandbox (builtins retirés, `os`/`sys` hors allowlist), ce qui retire `os._exit`/`sys.exit` avant même qu'ils puissent être appelés.
3. **Pas de limite de taille de sortie (`MAX_OUTPUT_CHARS`)**, contrairement à `mcp_tools_swebench.py` qui en a une (commit `ac56992`, `truncate_output()`). Le `reason[:300]` borne chaque motif, mais pas la chaîne du test elle-même ni le total : une solution qui `print` un volume énorme, ou une `test_list` exceptionnellement bavarde, peut inonder la réponse de l'outil. Incohérence entre les deux serveurs MCP du dépôt.
   > **Piste de solution** : réutiliser la même approche que le serveur SWE — définir `MAX_OUTPUT_CHARS = 50_000` (ou moins, MBPP produit moins de sortie) et une fonction `truncate_output()` qui, si la réponse assemblée dépasse la limite, la tronque avec le suffixe explicite *"Output was truncated because it was too long"* (§V.1.3). L'idéal serait d'extraire ce helper dans un module partagé (ex. `mcp_common.py` ou dans `student/`) importé par les deux serveurs, plutôt que de le dupliquer — ça garantit que les deux serveurs MCP restent cohérents et évite une dérive de configuration.
4. **Extraction du motif par « dernière ligne de stderr » peut être trompeuse** — `tb_lines[-1].strip()` suppose que la dernière ligne de stderr est le message d'exception. Si la solution écrit elle-même sur stderr (un `print(..., file=sys.stderr)`), la dernière ligne sera ce print, pas l'erreur réelle — feedback possiblement trompeur pour l'agent. Un parsing du traceback (chercher la dernière ligne `NomErreur: message` après le dernier `Traceback (most recent call last)`) serait plus robuste.
   > **Piste de solution** : parser le traceback plutôt que prendre la dernière ligne brute. Rechercher le dernier marqueur `"Traceback (most recent call last):"` dans stderr et, à partir de là, prendre la dernière ligne non vide qui suit — elle contiendra `TypeError: ...`/`NameError: ...`. On peut aussi laisser `traceback` formater l'erreur différemment en injectant dans le script un handler qui imprime uniquement la classe + message (`except Exception as e: print(f"{type(e).__name__}: {e}", file=sys.stderr)` avant `raise`) — mais le parsing simple (dernier `Traceback` → dernière ligne non vide) est suffisant et ne change pas le contrat du script.
5. **Le code de la solution s'exécute sur l'hôte, non sandboxé, avec accès réseau et filesystem** — `subprocess.run([sys.executable, "-c", …])` lance la solution **hors** des restrictions du sandbox (§V.2.3 : imports, réseau, mémoire, builtins). C'est assumé par l'architecture (MCP tools opèrent hors sandbox), et acceptable pour des solutions MBPP algorithmiques, mais c'est un vrai vecteur : un modèle « voyou » exécuterait sur l'hôte avec les privilèges du serveur MCP. À documenter explicitement comme frontière assumée (cf. le conteneur sandbox qui, lui, est isolé).
   > **Piste de solution** : restreindre le sous-processus de test à moindre coût : (a) `start_new_session=True` (+ `preexec_fn` si besoin) pour créer une session isolée, (b) `env` réduit — vider les variables sensibles et ne garder que le strict nécessaire pour `python -c`, (c) réappliquer les mêmes restrictions d'imports/builtins que le sandbox en réutilisant le `MetaPathFinder` de `restrictions.py` (réutilisable dans un script). La solution la plus robuste, alignée sur le sujet (§V.2.3) : exécuter `run_tests` **dans le conteneur** du sandbox (déjà `network_mode="none"`, `cap_drop`, filesystem restreint) plutôt que sur l'hôte — mais ça impose que le serveur MCP connaisse l'ID du conteneur (même débat que la piste B du trou SWE-bench). À défaut, documenter la frontière pour la soutenance.
6. **En timeout, le sous-processus est tué mais pas un éventuel descendant** — `subprocess.run` avec `timeout` envoie SIGKILL à l'enfant direct, pas à son groupe de process (pas de `start_new_session=True`). Une solution qui `fork`/spawne un enfant persistant pourrait le laisser vivre sur l'hôte après le timeout. Risque faible en MBPP, mais à connaître.
   > **Piste de solution** : lancer le sous-processus dans sa propre session et tuer le groupe entier au timeout. `subprocess.Popen(…, start_new_session=True)` place l'enfant dans un nouveau groupe de process ; au timeout, `proc.kill()` puis `os.killpg(proc.pid, signal.SIGKILL)` (en gardant `timeout` sur `proc.wait()` pour ne pas bloquer le serveur). Alternativement, capturer `proc.pid` et envoyer SIGKILL à `-proc.pid` (le groupe). Si le conteneur sandbox est utilisé (piste du point ❌ #5), le descendant meurt avec le conteneur, ce qui règle le problème structurellement.

**Détails mineurs non bloquants** : `flake8` et `mypy` sont propres. La re-vérification `TASK is None` dans `run_tests` est défensive (le serveur `exit(1)` au démarrage sinon), donc jamais atteignable en pratique — inoffensif. Le `compile()` pré-vérifie `imports + code` mais pas la chaîne de test complète injectée ensuite ; acceptable car les tests viennent de la moulinette (source de confiance), pas du modèle.

---

## Corrigés (historique)

Points déjà réglés dans l'historique git de ce fichier — retirés des sections ❌, listés pour la trace.

| Point | Correctif | Commit |
|---|---|---|
| Faux-passage via `exit(0)` : une solution pouvait sortir avec code 0 sans exécuter les tests | Patch `os._exit` + `except SystemExit: sys.exit(1)` injecté dans le sous-processus de test, en trois itérations | `f411bfa`, `6288229`, `160734e` |
| Timeout d'exécution du sous-processus | `subprocess.run(…, timeout=TIMEOUT_DELAY_SEC)` + interception de `TimeoutExpired` | `f7f9c3a` |
| Aucun message d'erreur au lancement du serveur sans tâche (`MBPP_TASK_JSON` absent/invalide) | Message clair sur `stderr` + `exit(1)` ; fallback `None` sur `ValidationError`/`JSONDecodeError` | `5a64000` |
| Docstring de module obsolète (info de dev périmée) | Docstring nettoyée sur les prérequis réels | `c82dfed` |

---

## Dépendance externe

Importe `from student.agent_mbpp.task import MBPPTaskInput` — module qui **miroite `moulinette.models_public.MBPPTaskInput`** (hérité de `agent_core.schemas.TaskInput`) pour que l'agent et le contrat d'évaluation partagent le même schéma (§V.3.3). **Vérifié au moment de l'audit** : les champs (`task_id`, `task_definition`, `function_definition`, `test_imports`, `test_list`) correspondent exactement à ceux du sujet (l. 414-421). L'import fonctionne depuis la racine du dépôt, contexte réel d'invocation de ce fichier. Le module `task.py` ne dépend pas de MCP ni du sandbox — le serveur reste indépendant de la boucle agent, comme exigé (§IV.2 : « Your tools must work independently of the agent loop »).

---

## Priorités recommandées

1. **🟡 Documenter explicitement la frontière de sécurité du point ❌ #5** — le code de la solution MBPP tourne sur l'hôte avec réseau/filesystem, hors sandbox. Choix architectural légitime (MCP tools hors sandbox), mais à assumer et documenter pour la soutenance (§VI.4 « Sandbox security and isolation guarantees ») — un examinateur peut demander pourquoi la solution n'est pas isolée.
2. **Rendre `TIMEOUT_DELAY_SEC` configurable** (ou le lier à la config) au lieu d'une constante en dur (❌ #1).
3. **Aligner sur le serveur SWE : ajouter une limite de taille de sortie** (`MAX_OUTPUT_CHARS` + troncature explicite) pour rester cohérent et borné (❌ #3).
4. **Robustifier l'extraction du motif d'échec** : parser le dernier traceback plutôt que prendre la dernière ligne de stderr (❌ #4).
5. **Optionnel — tuer le groupe de process en timeout** (`start_new_session=True` + `killpg`) pour ne pas laisser de descendant survivre (❌ #6).

L'outil obligatoire `run_tests` (§V.3.2) est implémenté, committé et **fonctionnel** — c'est la partie MCP du dépôt qui tourne de bout en bout sans le blocage architectural du serveur SWE.

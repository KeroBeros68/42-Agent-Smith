# Audit — `mcp_tools_swebench.py`

> Audit de conformité du serveur MCP SWE-bench par rapport au sujet officiel (`subject-1-1.txt`, v1.1, §V.4, §V.5) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-28
> **Périmètre** : `mcp_tools_swebench.py` (racine du dépôt), dans son architecture avec `student/sandbox/container.py` (le conteneur dans lequel les outils s'exécutent) et `student/sandbox/mcp_bridge.py` (le lanceur).
> **Méthode** : points positifs/négatifs justifiés par référence exacte au texte du sujet, par mypy/flake8, ou par comportement réel du code — même méthodologie que `AUDIT_MCP_TOOLS_MBPP.md` et `AUDIT_SANDBOX.md`. `flake8` → exit 0, `mypy` → *Success: no issues found in 1 source file*. Comportements vérifiés par exécution réelle le jour de l'audit (import, gardes de chemin, commande `get_patch`).

---

## Récapitulatif de conformité §V.5 — 9 outils obligatoires sur 9, codés

Le sujet (§V.4) autorise explicitement l'approche « (b) run the sandbox on the host with MCP tools bridging into Docker » (l. 462-465) — c'est exactement ce que fait ce serveur : le pont MCP s'exécute sur l'hôte, mais **chaque action d'outil est un `docker exec` dans le conteneur sandbox** (voir ✅ #3). Tous les outils de §V.5 sont présents et leurs formats de sortie correspondent au sujet.

| Outil | Section | Description (du sujet) | État |
|---|---|---|---|
| `read_file(filepath, start_line, end_line)` | §V.5.1 (l. 640-645) | Lecture avec numéros de ligne, format `cat -n` | ✅ Conforme |
| `edit_file(filepath, old_str, new_str)` | §V.5.1 (l. 646-647) | Remplace une chaîne exacte dans un fichier | ✅ Conforme |
| `list_files(directory, pattern)` | §V.5.1 (l. 648-649) | Liste les fichiers d'un dossier selon un pattern | ✅ Conforme |
| `search_code(pattern, file_pattern)` | §V.5.2 (l. 651-656) | Recherche grep-like, format `/abs/path.py:<line> <content>` | ✅ Conforme |
| `search_function_or_class_definition_in_code(name)` | §V.5.2 (l. 657-659) | Trouve la définition d'une fonction/classe | ✅ Conforme |
| `find_references(name, filepath, line)` | §V.5.2 (l. 660-662) | Trouve les usages d'un symbole | ✅ Conforme |
| `run_tests()` | §V.5.3 (l. 666-667) | Exécute le script d'évaluation | ✅ Conforme *(voir ❌ #2, #3)* |
| `get_patch()` | §V.5.3 (l. 668-670) | Diff git unifié de tous les changements | ✅ Conforme |
| `run_command(command, workdir)` | §V.5.3 (l. 671-673) | Commande shell, retourne stdout/stderr/exit code | ✅ Conforme |

Vérifié : les 9 outils sont importables (`import mcp_tools_swebench` avec `SWE_TASK_JSON` + `MCP_TIMEOUT_DELAY` valides → import OK, 9 symboles d'outils résolus). Le démarrage est **garanti** : l'agent pose `SWE_TASK_JSON` avant de spawner ([agent_swebench/__main__.py:153](student/agent_swebench/__main__.py#L153)) et le lanceur injecte `MCP_TIMEOUT_DELAY` ([mcp_bridge.py:51-53](student/sandbox/mcp_bridge.py#L51-L53)) — même schéma que MBPP.

---

## ✅ Bon

1. **9/9 outils obligatoires §V.5 implémentés, formats conformes** — `read_file` au format `cat -n` (`<n>: <ligne>`), `edit_file` par remplacement de chaîne exacte, `list_files` par glob, les trois outils de recherche au format `/abs/path.py:<line> <content>`, `run_tests` qui exécute `TASK.eval_script`, `get_patch` qui produit un diff git, `run_command` qui retourne stdout/stderr/exit code. Rien ne manque : §VI.3 « All mandatory tools pass independent tests » est satisfait sur le périmètre (§V.5).
2. **Architecture conforme à §V.4 option (b)** — « run the sandbox on the host with MCP tools bridging into Docker » (l. 462-465). Le serveur MCP tourne sur l'hôte et pont via `docker exec` dans le conteneur sandbox. C'est l'une des deux approches explicitement valides du sujet.
3. **Les outils s'exécutent dans le conteneur restreint, jamais sur l'hôte** — bien meilleure posture que `mcp_tools_mbpp.py` (qui lance la solution en sous-processus sur l'hôte). Ici le code de la solution tourne dans le conteneur `sandbox-executor:` créé par [container.py](student/sandbox/container.py) : `network_mode="none"`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`, rootfs `read_only=True`, tmpfs `/workspace`+`/tmp`, `pids_limit`, mem_limit, exécution en `user="1000"` (§V.2.3 : réseau coupé, pas d'élévation, filesystem borné). Le code LLM ne touche jamais la machine hôte.
4. **`exec` en style argv, sans interpolation shell pour les outils de lecture/recherche** — les arguments (fichiers, regex, noms) sont passés en `sys.argv` de scripts `python3 -c`, jamais concaténés dans une commande shell. Un nom de fichier ou une regex contenant des guillemets ne peut pas sortir du script. `run_command` est `bash -c` **par design** (le sujet demande une commande shell, l. 671).
5. **Garde de périmètre `is_relative_to(ROOT_DIR)` sur tous les outils de fichier** — `read_file`, `edit_file`, `list_files`, `find_references`, `run_command` refusent toute interaction hors de `/workspace/testbed`, **avant** tout contact avec le conteneur. L'agent ne peut pas lire/écrire l'arborescence système via ces outils. *(Le détail de ce périmètre et son mismatch avec `/testbed` sont traités en ❌ #1.)*
6. **`run_tests` réécrit intelligemment le script d'évaluation pour le réseau coupé** — (a) `/testbed` → `/workspace/testbed` (le diff se fait sur la copie éditable, pas sur l'original read-only) ; (b) `pip install -e .` → `pip install -e . --no-build-isolation --no-deps` (sinon le build isolation part chercher setuptools sur PyPI → échec réseau, diagnostiqué sur un vrai faux-négatif) ; (c) `PYTHONPATH=ROOT_DIR` injecté dans l'env du `exec` — astuce **générique** (documenté : ne dépend pas de pip pour re-pointer l'install editable, qui reste gelée sur l'/testbed original). Le commentaire (l. 514-538) documente un vrai débogage, pas une hypothèse.
7. **Pas d'échec silencieux (§V.1.3)** — `run_tests` renvoie stdout+stderr bornés avec un message distinct si `timeout` coupe (exit 124 → `Evaluation timed out (Ns)!`) ; `get_patch` et `run_command` gèrent le timeout (124) et retournent explicitement stdout/stderr/exit code ; chaque outil a un message d'erreur lisible (fichier introuvable, permission, regex invalide, workspace absent). L'agent n'est jamais laissé sans explication.
8. **Sortie bornée sur tous les retours volumineux** — `truncate_output` appliqué aux 9 outils (fichiers, recherches, diffs, commandes). Pas d'inondation du contexte LLM (§V.1.3 « Tool output was truncated due to size limits » → explicite). Importé depuis le module partagé `student/mcp_server_shared/share.py` sans effet de bord (cf. `AUDIT_MCP_TOOLS_MBPP.md`, ✅ #15).
9. **Le faux-problème classique `/testbed` est traité par une copie éditable, pas par une modification de l'original** — `_ensure_workspace_repo` copie `/testbed` → `/workspace/testbed` (tmpfs éditable, uid 1000) une seule fois par conteneur (`[ -d ... ] || cp -a ...`). L'original read-only du conteneur reste intact ; `run_tests`/`get_patch` travaillent sur la copie. C'est le correctif de `ee8f8a9` (« verifying that functions perform on '/testbed' directory »).
10. **Chargement de tâche robuste et démarrage vérifié** — `SWEBenchTaskInput.model_validate` avec interception `ValidationError`/`JSONDecodeError`, message clair + `exit(1)` si tâche absente (refus de servir sans contrat), re-vérification `TASK is None` en entrée de `run_tests` (défense en profondeur, `5e73074`). Le timeout est chargé depuis `MCP_TIMEOUT_DELAY` avec validation `>= 1` (le bridge l'injecte à `"60"`). Vérifié : import OK avec env valide.
11. **`flake8` et `mypy` propres** — exit 0 / *Success: no issues found in 1 source file*, re-vérifiés le jour de l'audit. Code commenté et documenté (chaque script auxiliaire, chaque choix de `user="1000"`, `demux`, `timeout` a un commentaire expliquant le *pourquoi*, souvent tiré d'un test réel).
12. **Discovery du conteneur alignée sur l'architecture « un conteneur par session »** — `_find_sandbox_container` matche l'image dérivée `sandbox-executor:<hash>` que [container.py:148](student/sandbox/container.py#L148) génère pour **toute** session (MBPP et SWE-bench confondus, via `FROM base_image`). Cohérent avec « one sandbox container runs at a time ». *(Fragilité si plusieurs sessions : ❌ #4.)*

---

## ❌ Mauvais

1. **Mismatch de chemin : le format canonique `/testbed` du sujet est rejeté ; l'original non édité reste accessible.** `ROOT_DIR = '/workspace/testbed'` (l. 69) et le garde `is_relative_to` rejettent toute entrée sous `/testbed`. Or le sujet utilise `/testbed/...` partout (exemples l. 197 `read_file(filepath="/testbed/file.py")`, l. 620-621 `read_file(filepath="/testbed/src/module.py")`, `allowed_directories` par défaut `["/testbed", "/tmp/agent"]` l. 357). **Vérifié** : `read_file('/testbed/src/module.py', 1, 5)` → `'Error: you are trying to interract with a file outside your allowed directory (/workspace/testbed)'` (le guard s'exécute avant le conteneur). Le mismatch est **atténué** côté prompt agent ([agent_swebench/__main__.py:58](student/agent_swebench/__main__.py#L58) : « The repository is checked out at /workspace/testbed ») et le message d'erreur révèle le bon racine — mais deux frictions réelles subsistent : (a) tout raisonnement/outil copié depuis les exemples du sujet échoue au premier appel ; (b) **l'original `/testbed` (non édité, read-only) reste joignable dans le conteneur** via `run_command` avec un chemin absolu (`pytest /testbed/tests/...`) — le `workdir` est restreint, pas la commande → risque de faux négatifs si l'agent teste le mauvais arbre.
   > **Piste de solution** : (a) canoniser l'entrée dans les outils de fichier — accepter `/testbed/...` et le mapper vers `ROOT_DIR` (les deux racines doivent résoudre sur la même copie) ; (b) pour `run_command`, filtrer la commande elle-même (rejeter/remapper `/testbed` hors `ROOT_DIR`) ou au minimum documenter dans la description de l'outil que la copie éditable est `/workspace/testbed` et que `/testbed` est l'original gelé. L'option propre : rendre `ROOT_DIR` configurable via env, aligné sur la valeur que le prompt agent enseigne.
2. **Réécriture fragile de la chaîne exacte `pip install -e .`** — `run_tests` remplace le littéral `"pip install -e ."` (l. 524-526). Toute variante réelle de l'`eval_script` (`pip install -e ".[dev]"`, `pip install -e .[test]`, `pip install -e ./`, `python -m pip install -e .` avec options) n'est **pas** couverte → le build isolation part sur PyPI → échec « Temporary failure in name resolution » sous `network_mode="none"` (le bug exact que le correctif visait, mais seulement pour l'orthographe exacte). Vérifié : le `eval_script` réel du `.env` fait `python -m pip install -e .` — qui contient bien la sous-chaîne et passe ; mais la robustesse dépend de l'orthographe fournie par la moulinette.
   > **Piste de solution** : au lieu de réécrire le texte du script, injecter les comportements via l'environnement du `exec` : `PIP_NO_BUILD_ISOLATION=1` et `PIP_NO_DEPS=1` (ou `PIP_CONFIG_FILE` pointant vers une config avec ces réglages). Ça couvre toutes les formes de `pip install` sans dépendre d'un match textuel. En complément, réécrire plus largement (`re.sub(r"pip install -e\S*", ...)`) si l'env n'est pas transmissible.
3. **L'`eval_script` peut échouer car `git config --global` écrit dans un `$HOME` sur rootfs read-only — à vérifier en conditions réelles.** Le `eval_script` SWE-bench fait `git config --global --add safe.directory /workspace/testbed` (présent dans le `.env` réel). Or le conteneur est `read_only=True` : seuls `/workspace` et `/tmp` sont éditables. `run_tests` n'injecte pas `HOME` dans l'env du `exec` (l. 538 : seulement `PYTHONPATH`). Si `$HOME` du user 1000 résout sur le rootfs read-only (ou n'existe pas), `git config --global` **échoue**, et sous `set -uxo pipefail` de l'`eval_script`, `run_tests` échoue avant d'avoir lancé les tests. Non constaté (aucun conteneur démarré au moment de l'audit — l'image SWE-bench n'a pas été tirée), mais mécanisme vérifiable : le correctif `safe.directory` est exactement conçu pour des repos dont l'ownership diffère du user d'exécution.
   > **Piste de solution** : injecter `HOME=/workspace` (tmpfs uid 1000 éditable) dans l'env du `exec` de `run_tests` — avec le commentaire approprié, ça règle `git config --global` et toute écriture de config utilisateur. À défaut, exécuter l'`eval_script` avec `user="0"` ne résout pas le problème (rootfs toujours read-only) — c'est bien `HOME` sur un chemin writable qu'il faut garantir.
4. **Discovery du conteneur par préfixe d'image : fragile et en dépendance dure de la session.** `_find_sandbox_container` (l. 74-93) retourne le **premier** conteneur dont une image porte un tag `sandbox-executor:*` ; si aucun, tous les outils lèvent `SWEException` (« No running sandbox container found — is the sandbox started? »). Ça présuppose : (a) la session sandbox a déjà créé le conteneur avant que le pont MCP ne connecte le serveur (ordre opérationnel non garanti par ce module) ; (b) un seul conteneur sandbox actif — sinon un autre conteneur de test pourrait être ciblé (ambigüité silencieuse). Vérifié : sans conteneur actif, tout outil échoue (le garde de chemin passe, puis `_get_container` lève).
   > **Piste de solution** : passer l'identifiant du conteneur (ou son nom/tag exact) au serveur via une variable d'env au spawn (ex. `SWE_CONTAINER_ID`), posée par la session au moment de créer le conteneur — élimine la découverte par préfixe et l'ordre implicite. Garder un message d'échec distinct « sandbox non démarrée » plutôt qu'un `SWEException` générique.

**Détails mineurs non bloquants** : typo « interract » au lieu de « interact » dans 5 messages d'erreur (10 occurrences, l. 278, 332, 378, 478, 579) — cosmétique mais lisible par le LLM. `search_code` avec `file_pattern="*"` (défaut) traverse `.git` via `rglob` — bruit/perf possible sur gros dépôts ; les deux autres recherches ne matchent que `*.py`. `search_code` retourne « No matches found. » vs les autres « No definition/references found for 'X'. » — léger manque d'homogénéité, sans impact. `_ensure_workspace_repo` copie aussi `.git` (nécessaire pour `get_patch`) mais pas les éventuels gros caches — correct. La docstring de `get_patch` documente déjà la nécessité de `git add`/`git add -N` pour les nouveaux fichiers — bon.

---

## Corrigés (historique)

Points déjà réglés dans l'historique git de ce fichier ou le working tree — retirés des sections ❌, listés pour la trace.

| Point | Correctif | Commit |
|---|---|---|
| Outil `run_tests` manquant | Ajout de `run_tests()` exécutant `TASK.eval_script` | `f57ab82` |
| Outil `get_patch` manquant | Ajout de `get_patch()` (diff git unifié) | `d0744fd` |
| Outil `run_command` manquant | Ajout de `run_command(command, workdir)` (stdout/stderr/exit code) | `ff69ad0` |
| Sortie sans limite de taille | `truncate_output` appliqué à toutes les sorties volumineuses | `ac56992` |
| Fonctions opérant sur l'`/testbed` original read-only | Copie éditable `/workspace/testbed` + réécriture `/testbed` → `ROOT_DIR` dans `run_tests` | `ee8f8a9` |
| Timeout d'exécution codé en dur | Timeout chargé depuis `MCP_TIMEOUT_DELAY` avec validation (entier ≥ 1) ; injection du bridge (`MCP_TIMEOUT_DELAY="60"`) (cf. `AUDIT_MCP_TOOLS_MBPP.md`) | `a0f5a64` (serveur) + `e08300e` (bridge) |
| Couplage `truncate_output` depuis le serveur frère | Import depuis le module partagé sans effet de bord `student/mcp_server_shared/share.py` (même résolution que MBPP) | `e08300e` |
| Aucun message d'erreur au lancement sans tâche | Message clair + `exit(1)` si `SWE_TASK_JSON` absent/invalide | `5e73074` |
| Patch `get_patch` sans `-c core.fileMode=false` (non-conformité §V.4 l. 472) | Ajout du drapeau — commande `git -c core.fileMode=false diff HEAD` | working tree (non committé) |

---

## Dépendance externe

1. **`from student.agent_swebench.task import SWEBenchTaskInput`** — module qui **miroite `moulinette.models_public.SWEBenchTaskInput`** (hérité de `agent_core.schemas.TaskInput`) : `instance_id`, `problem_statement`, `docker_image`, `eval_script`, `hints_text`, `repo` — correspondance exacte avec le sujet (l. 506-521). Le serveur reste indépendant de la boucle agent (§IV.2) ; le schéma est partagé via le module neutre `task.py`.
2. **`from student.mcp_server_shared.share import truncate_output`** (l. 23) — module partagé **sans effet de bord**, utilisé aussi par MBPP : source de vérité unique, aucun couplage au serveur frère (cf. `AUDIT_MCP_TOOLS_MBPP.md`, ✅ #15).
3. **`import docker` + daemon Docker + un conteneur sandbox vivant** — dépendance **d'exécution** structurelle : chaque outil fait un `docker exec` dans le conteneur `sandbox-executor:*`. Sans conteneur actif, **aucun** outil ne répond (❌ #4). Cette dépendance est assumée par l'architecture §V.4(b), mais elle lie la disponibilité du serveur à la vie d'une session sandbox — à connaître pour la démo/soutenance.
4. **Couplage de nommage avec `container.py`** — la découverte repose sur le tag dérivé `sandbox-executor:<hash>` (l. 71, 89) produit par [container.py:148-150](student/sandbox/container.py#L148-L150). Si le schéma de tag change, la découverte casse silencieusement (❌ #4). Couplage horizontal entre deux composants à documenter.

---

## Priorités recommandées

1. **Canoniser `/testbed` → `/workspace/testbed` dans les outils de fichier et borner `run_command`** (❌ #1) — supprime la friction avec les exemples du sujet et le risque de tester l'arbre original non édité.
2. **`run_tests` : injecter `HOME=/workspace` dans l'env du `exec`** (❌ #3) — élimine le risque d'échec de `git config --global` sur rootfs read-only. À confirmer en conditions réelles (image SWE-bench tirée, conteneur démarré).
3. **Injecter les réglages pip par environnement (`PIP_NO_BUILD_ISOLATION`/`PIP_NO_DEPS`) au lieu de réécrire la chaîne** (❌ #2) — robustifie `run_tests` contre les variantes d'`eval_script`.
4. **Passer l'ID du conteneur par env au lieu de la découverte par préfixe** (❌ #4) — fiabilise la session et lève l'ambiguïté multi-conteneurs.

Le seul point de **non-conformité directe au sujet** — le drapeau `-c core.fileMode=false` de `get_patch`, §V.4 l. 472 — est **corrigé** (voir Corrigés). Les 9 outils obligatoires (§V.5) restent **implémentés, conformes et vérifiés** (import, gardes, formats). Le serveur est **fonctionnel** dans l'architecture §V.4(b) : tout le code exécuté tourne dans le conteneur restreint (`network_mode="none"`, `cap_drop=["ALL"]`, rootfs read-only), une posture de sécurité bien meilleure que celle de MBPP. Les ❌ restants sont des correctifs ciblés (canonisation des chemins, robustesse de `run_tests`, fiabilité de la discovery) — aucun ne bloque le fonctionnement actuel, mais ❌ #1 et #3 méritent d'être traités avant une évaluation réelle.

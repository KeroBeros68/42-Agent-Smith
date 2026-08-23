# Audit — `mcp_tools_swebench.py`

> Audit de conformité du serveur MCP SWE-bench par rapport au sujet officiel (`subject-1-1.txt`, v1.1, §V.5) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-23 (mise à jour)
> **Périmètre** : `mcp_tools_swebench.py` (racine du dépôt)
> **Méthode** : points positifs/négatifs justifiés par référence exacte au texte du sujet, par mypy/flake8, ou par test réel — même méthodologie que `AUDIT_SANDBOX.md`.

---

## Récapitulatif de conformité §V.5 — 6 outils sur 9

| Outil | Section | Description (du sujet) | État |
|---|---|---|---|
| `read_file(filepath, start_line, end_line)` | §V.5.1 | Read the content of a file with line numbers. Output format: `<line_number>: <line_content>` (cat -n) | ✅ Implémenté |
| `edit_file(filepath, old_str, new_str)` | §V.5.1 | Replace an exact string in a file with a new string. | ✅ Implémenté |
| `list_files(directory, pattern)` | §V.5.1 | List files in a directory matching a given pattern. | ✅ Implémenté |
| `search_code(pattern, file_pattern)` | §V.5.2 | Perform a grep-like search in the codebase. Output format: `/absolute/path_to_file.py:<line_number> <line_content>` | ✅ Implémenté |
| `search_function_or_class_definition_in_code(name)` | §V.5.2 | Find the definition of a function or a class. Output format similar to `search_code`. | ✅ Implémenté |
| `find_references(name, filepath, line)` | §V.5.2 | Find all usages of a symbol (function or class). Output format similar to `search_code`. | ✅ Implémenté |
| `run_tests()` | §V.5.3 | Execute the evaluation script. | ❌ Manquant |
| `get_patch()` | §V.5.3 | Retrieve the unified git diff of all changes made to the repository. | ❌ Manquant |
| `run_command(command, workdir)` | §V.5.3 | Execute a shell command in the specified working directory. Returns the command's stdout, stderr, and exit code. | ❌ Manquant |

---

## ✅ Bon

1. **Formats de sortie vérifiés conformes au sujet, mot pour mot** — pas une approximation. §V.5.1 exige pour `read_file` : *"`<line_number>: <line_content>`"* → implémenté exactement (`f'{current_line}: {line}'`). §V.5.2 exige pour `search_code` : *"`/absolute/path_to_file.py:<line_number> <line_content>`"* → implémenté exactement (`f"{abs_path}:{line_number} {line.rstrip()}"`).
2. **`search_code` gère une regex invalide proprement** (`re.error` intercepté, message clair renvoyé) plutôt qu'un crash — cohérent avec l'esprit "pas d'échec silencieux" du sujet (§V.1.3), même si ce n'est pas un des 3 outils de filesystem concernés par cette exigence.
3. **`TASK` chargé une fois au démarrage depuis `SWE_TASK_JSON`**, avec fallback `None` proprement géré (`ValidationError`/`JSONDecodeError` interceptées) — même pattern que `mcp_tools_mbpp.py`, cohérence entre les deux serveurs.
4. **`search_code` scope son parcours à `/testbed`** (`root_dir = '/testbed'`) et vérifie son existence avant de parcourir — évite de chercher sur tout le système de fichiers du conteneur par défaut.
5. **`search_function_or_class_definition_in_code` conforme — même format que `search_code`, matcher plus précis.** Implémentée à la racine `/testbed`, ne parcourt que `*.py`, et utilise un regex ancré `^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b` : `re.escape(name)` neutralise les métacaractères de l'entrée, `\b` empêche les faux positifs de sous-chaîne (`name="parse"` ne matche pas `parse_all`), et l'ancre `def|class` exclut les appels (`x = name(...)`). Format de sortie strictement identique à `search_code` (`/abs/path.py:<n> <content>`) — le *"similar to search_code format"* du §V.5.2 est respecté au mot près.
6. **`find_references` conforme — matcher sémantique "usage", garde de définition.** Implémentée à la racine `/testbed` sur `*.py`, elle utilise un regex à frontière de mot `\b{name}\b` (avec `re.escape`) : matche `parse(...)`, `mod.parse`, `from x import parse`, mais pas `parse_all` ni `Parser` (faux positifs de sous-chaîne écartés). `filepath`/`line` identifient le site de définition, dont la **ligne est exclue** des résultats (une déclaration n'est pas un usage). Un garde `Path(filepath).exists()` renvoie une erreur claire si le chemin fourni n'existe pas — cohérent avec l'esprit "pas d'échec silencieux" (§V.1.3). Format de sortie strictement identique à `search_code`. Vérifié par test réel sur un dépôt synthétique (`parse` vs `parse_all`/`Parser` + exclusion de la ligne de définition). Limite assumée : approche grep, pas AST — `filepath`/`line` excluent la ligne de définition mais ne désambiguïsent pas sémantiquement deux symboles homonymes.

## ❌ Mauvais

1. **`except IndexError` mort dans `read_file` et `edit_file` — vérifié empiriquement, pas supposé.** Le slicing Python (`lines[start_line - 1:end_line]`) ne lève **jamais** `IndexError`, même hors limites — testé directement : `['a','b','c'][100:200]` retourne `[]`, pas d'exception. Conséquence concrète : `start_line=0` donne `lines[-1:end_line]`, qui prend la **dernière** ligne du fichier au lieu de signaler une entrée invalide — un résultat silencieusement faux plutôt que le feedback explicite exigé par §V.1.3.
2. **Aucune limite de taille de sortie.** `search_code` et `list_files` peuvent retourner un nombre illimité de résultats sur un `/testbed` volumineux, sans troncature ni signal — alors que le sujet exige explicitement un feedback pour *"Tool output was truncated due to size limits"* (§V.1.3). Actuellement, rien ne tronque, donc rien ne signale non plus.
3. **Incohérence de portée entre outils.** `search_code` est scopé à `/testbed`, mais `read_file`/`edit_file`/`list_files` acceptent n'importe quel chemin absolu, sans restriction. Ces outils tournent hors sandbox avec leurs propres permissions (pas une violation du sujet en soi), mais l'absence de cohérence avec `search_code` sur ce point n'a probablement pas été un choix délibéré.
4. **`list_files` ne recurse pas sans `**` explicite dans le pattern — vérifié empiriquement.** `glob.glob(path, recursive=True)` ne recurse que si le *pattern* contient `**` ; testé directement : `list_files("/dir", "*.py")` ne renvoie que les fichiers du niveau racine, pas des sous-dossiers, malgré `recursive=True`. Pour explorer un vrai dépôt comme `/testbed` (fichiers presque toujours dans des sous-dossiers), un agent qui appelle `list_files(dir, "*.py")` — l'usage le plus naturel — n'obtiendra presque rien.
5. ~~`mcp.run(transport=transport_mode)` — mypy signale un type non garanti statiquement~~ **→ RÉSOLU.** Le `transport_mode` était un `str` brut, incompatible avec le `Literal['stdio', 'http', ...]` attendu par `FastMCP.run()`. Corrigé depuis l'audit du 2026-08-23 : une variable typée `mode: Literal["http", "stdio"]` est affectée via une condition explicite avant `mcp.run(transport=mode)`. Vérifié : `mypy mcp_tools_swebench.py` → `Success: no issues found`.

**Détails mineurs non bloquants** : typo dans le docstring de `read_file` ("opening pens the given file"). flake8 et mypy sont **propres** (`flake8` → exit 0, `mypy` → *Success: no issues found*) — les 10 signalements flake8 signalés lors de l'audit du 2026-08-23 (lignes trop longues `E501`, espacements `E302`/`E303`) ont été corrigés depuis.

---

## Dépendance externe

Importe `from student.agent_swebench.task import SWEBenchTaskInput` — un module qui **miroire `moulinette.models_public.SWEBenchTaskInput`** (hérité de `agent_core.schemas.TaskInput`) pour que l'agent et le contrat d'évaluation partagent le même schéma (§V.4). **Vérifié au moment de l'audit** : l'import fonctionne depuis la racine du dépôt, contexte réel d'invocation de ce fichier.

> **Évolution depuis l'audit du 2026-08-20** : le fichier importait auparavant `from student.data_models import SWEBenchTaskInput` ; le module `student.data_models` n'existe **plus** (renommé/supprimé — `ModuleNotFoundError` confirmé empiriquement). L'ancienne section sur le bug de `data_models/__init__.py` (voir `AUDIT_AGENT_CORE.md`) ne s'applique donc plus : l'import actuel pointe vers `student/agent_swebench/task.py`, une nouvelle localisation stable et vérifiée.

---

## Priorités recommandées

1. **Ajouter une limite de taille + message de troncature** sur `search_code`/`list_files` — c'est une exigence explicite du sujet (§V.1.3), pas une amélioration optionnelle
2. **Remplacer les `except IndexError` morts** par une vraie validation de `start_line`/`end_line` (ex: `start_line >= 1`, `start_line <= end_line`) dans `read_file`/`edit_file`
3. **Corriger le pattern de `list_files`** — soit forcer `**/` en préfixe du pattern, soit documenter clairement que l'appelant doit le faire lui-même
4. **Implémenter les 3 outils manquants** : `run_tests`, `get_patch`, `run_command` — sans eux, l'agent SWE-bench ne peut ni exécuter de tests, ni produire de patch final (les deux outils de code search §V.5.2 sont désormais implémentés — voir ✅ Bon #5 et #6).
5. **Décider et appliquer une politique de portée cohérente** (`/testbed` partout, ou nulle part, mais pas un mélange des deux)

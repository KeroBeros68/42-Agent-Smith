# Audit — `mcp_tools_swebench.py`

> Audit de conformité du serveur MCP SWE-bench par rapport au sujet officiel (`subject-1-1.txt`, v1.1, §V.5) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-20
> **Périmètre** : `mcp_tools_swebench.py` (racine du dépôt)
> **Méthode** : points positifs/négatifs justifiés par référence exacte au texte du sujet, par mypy/flake8, ou par test réel — même méthodologie que `AUDIT_SANDBOX.md`.

---

## Récapitulatif de conformité §V.5 — 4 outils sur 9

| Outil | Section | État |
|---|---|---|
| `read_file(filepath, start_line, end_line)` | §V.5.1 | ✅ Implémenté |
| `edit_file(filepath, old_str, new_str)` | §V.5.1 | ✅ Implémenté |
| `list_files(directory, pattern)` | §V.5.1 | ✅ Implémenté |
| `search_code(pattern, file_pattern)` | §V.5.2 | ✅ Implémenté |
| `search_function_or_class_definition_in_code(name)` | §V.5.2 | ❌ Manquant |
| `find_references(name, filepath, line)` | §V.5.2 | ❌ Manquant |
| `run_tests()` | §V.5.3 | ❌ Manquant |
| `get_patch()` | §V.5.3 | ❌ Manquant |
| `run_command(command, workdir)` | §V.5.3 | ❌ Manquant |

---

## ✅ Bon

1. **Formats de sortie vérifiés conformes au sujet, mot pour mot** — pas une approximation. §V.5.1 exige pour `read_file` : *"`<line_number>: <line_content>`"* → implémenté exactement (`f'{current_line}: {line}'`). §V.5.2 exige pour `search_code` : *"`/absolute/path_to_file.py:<line_number> <line_content>`"* → implémenté exactement (`f"{abs_path}:{line_number} {line.rstrip()}"`).
2. **`search_code` gère une regex invalide proprement** (`re.error` intercepté, message clair renvoyé) plutôt qu'un crash — cohérent avec l'esprit "pas d'échec silencieux" du sujet (§V.1.3), même si ce n'est pas un des 3 outils de filesystem concernés par cette exigence.
3. **`TASK` chargé une fois au démarrage depuis `SWE_TASK_JSON`**, avec fallback `None` proprement géré (`ValidationError`/`JSONDecodeError` interceptées) — même pattern que `mcp_tools_mbpp.py`, cohérence entre les deux serveurs.
4. **`search_code` scope son parcours à `/testbed`** (`root_dir = '/testbed'`) et vérifie son existence avant de parcourir — évite de chercher sur tout le système de fichiers du conteneur par défaut.

## ❌ Mauvais

1. **`except IndexError` mort dans `read_file` et `edit_file` — vérifié empiriquement, pas supposé.** Le slicing Python (`lines[start_line - 1:end_line]`) ne lève **jamais** `IndexError`, même hors limites — testé directement : `['a','b','c'][100:200]` retourne `[]`, pas d'exception. Conséquence concrète : `start_line=0` donne `lines[-1:end_line]`, qui prend la **dernière** ligne du fichier au lieu de signaler une entrée invalide — un résultat silencieusement faux plutôt que le feedback explicite exigé par §V.1.3.
2. **Aucune limite de taille de sortie.** `search_code` et `list_files` peuvent retourner un nombre illimité de résultats sur un `/testbed` volumineux, sans troncature ni signal — alors que le sujet exige explicitement un feedback pour *"Tool output was truncated due to size limits"* (§V.1.3). Actuellement, rien ne tronque, donc rien ne signale non plus.
3. **Incohérence de portée entre outils.** `search_code` est scopé à `/testbed`, mais `read_file`/`edit_file`/`list_files` acceptent n'importe quel chemin absolu, sans restriction. Ces outils tournent hors sandbox avec leurs propres permissions (pas une violation du sujet en soi), mais l'absence de cohérence avec `search_code` sur ce point n'a probablement pas été un choix délibéré.
4. **`list_files` ne recurse pas sans `**` explicite dans le pattern — vérifié empiriquement.** `glob.glob(path, recursive=True)` ne recurse que si le *pattern* contient `**` ; testé directement : `list_files("/dir", "*.py")` ne renvoie que les fichiers du niveau racine, pas des sous-dossiers, malgré `recursive=True`. Pour explorer un vrai dépôt comme `/testbed` (fichiers presque toujours dans des sous-dossiers), un agent qui appelle `list_files(dir, "*.py")` — l'usage le plus naturel — n'obtiendra presque rien.
5. **`mcp.run(transport=transport_mode)` — mypy signale un type non garanti statiquement.** `transport_mode` est un `str` brut ; `FastMCP.run()` attend un `Literal['stdio', 'http', ...]`. La validation faite juste au-dessus (`if transport_mode != 'http' and transport_mode != 'stdio': raise`) est correcte à l'exécution, mais mypy ne peut pas la relier au type attendu sans un `Literal`/`cast` explicite. Mineur (pas un bug réel), mais empêche `mypy mcp_tools_swebench.py` d'être propre.

**Détails mineurs non bloquants** : typo dans le docstring de `read_file` ("opening pens the given file") ; 11 signalements flake8, presque tous des lignes trop longues (>79 caractères) ou un espacement de 2 lignes manquant entre fonctions — aucun n'affecte le comportement.

---

## Dépendance externe

Utilise `from student.data_models import SWEBenchTaskInput` — cette forme d'import (avec le préfixe `student.`) dépendait d'un bug dans `data_models/__init__.py` qui aurait pu la casser selon le contexte d'exécution ; corrigé pendant la session dans le cadre de l'audit `agent_core` (voir `AUDIT_AGENT_CORE.md`). Vérifié après correction : cette forme d'import fonctionne toujours depuis la racine du dépôt, contexte réel d'invocation de ce fichier.

---

## Priorités recommandées

1. **Ajouter une limite de taille + message de troncature** sur `search_code`/`list_files` — c'est une exigence explicite du sujet (§V.1.3), pas une amélioration optionnelle
2. **Remplacer les `except IndexError` morts** par une vraie validation de `start_line`/`end_line` (ex: `start_line >= 1`, `start_line <= end_line`) dans `read_file`/`edit_file`
3. **Corriger le pattern de `list_files`** — soit forcer `**/` en préfixe du pattern, soit documenter clairement que l'appelant doit le faire lui-même
4. **Implémenter les 5 outils manquants** : `search_function_or_class_definition_in_code`, `find_references`, `run_tests`, `get_patch`, `run_command` — sans eux, l'agent SWE-bench ne peut ni comprendre le code (au-delà d'un grep brut), ni exécuter de tests, ni produire de patch final
5. **Décider et appliquer une politique de portée cohérente** (`/testbed` partout, ou nulle part, mais pas un mélange des deux)

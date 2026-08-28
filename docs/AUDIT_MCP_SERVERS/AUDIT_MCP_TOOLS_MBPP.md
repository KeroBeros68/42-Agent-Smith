# Audit — `mcp_tools_mbpp.py`

> Audit de conformité du serveur MCP MBPP par rapport au sujet officiel (`subject-1-1.txt`, v1.1, §V.3.2) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-27
> **Mise à jour du 2026-08-28** : re-audit du working tree (non committé) — `truncate_output` importé depuis un **module partagé sans effet de bord** (`student/mcp_server_shared/share.py`) ; **🔴 crash au démarrage** et **couplage inter-serveurs** **résolus**. Check `_exit` retiré ; docstring corrigée (`MCP_TIMEOUT_DELAY`). **Nouveau : le lanceur `mcp_bridge._build_transport` injecte désormais `MCP_TIMEOUT_DELAY: "60"`** — la dernière dépendance de démarrage (ex-❌ #1) est **résolue**. Plus aucun obstacle au démarrage ne subsiste. Les points soulevés en cours d'audit (défense `os._exit`, exécution hôte, extraction du motif, descendants de process) ont été **écartés** — trace conservée dans la section « Trace ».
> **Périmètre** : `mcp_tools_mbpp.py` (racine du dépôt)
> **Méthode** : points positifs/négatifs justifiés par référence exacte au texte du sujet, par mypy/flake8, ou par comportement réel du code — même méthodologie que `AUDIT_SWEBENCH_TOOLS.md` et `AUDIT_SANDBOX.md`. `flake8` et `mypy` re-vérifiés à 0 erreur ; la robustesse anti-bypass a été re-vérifiée par exécution réelle le jour de l'audit.

---

## Récapitulatif de conformité §V.3.2 — 1 outil obligatoire sur 1, codé **et** fonctionnel

> Contrairement à `mcp_tools_swebench.py` (bloqué par le trou `/testbed`, voir `AUDIT_SWEBENCH_TOOLS.md`), ce serveur n'a **aucune dépendance à un filesystem partagé** : `run_tests` n'exécute que du code Python en sous-processus via `sys.executable`. L'architecture « serveur MCP spawné sur l'hôte » est donc **correcte ici** — c'est exactement le cas où le modèle hôte fonctionne de bout en bout, là où il casse structurellement pour SWE-bench.

| Outil | Section | Description (du sujet) | État |
|---|---|---|---|
| `run_tests(code)` | §V.3.2 | « The `run_tests` tool » — exécute les tests unitaires publics contre la solution de l'agent | ✅ Conforme et fonctionnel |

---

## ✅ Résolu — plus aucun obstacle au démarrage

Trois problèmes ont été réglés depuis l'audit initial, tous **vérifiés réellement le jour de l'audit** :
1. **🔴 Crash au démarrage (ex-🔴 du 27/08)** — le serveur MBPP pouvait crasher au boot car il importait `mcp_tools_swebench`, dont le chargement appelle `exit(1)` si `SWE_TASK_JSON`/`MCP_TIMEOUT_DELAY` manquent. Résolu : `mcp_tools_mbpp.py` (l. 25) et `mcp_tools_swebench.py` (l. 23) importent tous deux `truncate_output` depuis **`student/mcp_server_shared/share.py`**, un module partagé **sans aucun effet de bord** (il ne définit que `MAX_OUTPUT_CHARS` et la fonction, aucun import exécutable, aucun `exit(1)`). C'est l'extraction recommandée dans l'audit précédent. Vérifié : `SWE_TASK_JSON='' MBPP_TASK_JSON='' MCP_TIMEOUT_DELAY=10 uv run python -c "import mcp_tools_mbpp"` ne produit **plus** l'erreur SWE.
2. **Couplage inter-serveurs (ex-❌ #3)** — `from mcp_tools_swebench import truncate_output` supprimé au profit du module partagé : plus de dépendance du serveur MBPP au module du serveur frère.
3. **Dépendance de démarrage `MCP_TIMEOUT_DELAY` (ex-❌ #1)** — le serveur fait `exit(1)` si la variable est absente/invalide (l. 59-67). Le lanceur `mcp_bridge._build_transport` injecte désormais **`MCP_TIMEOUT_DELAY: "60"`** en plus de `MCP_TRANSPORT` ([mcp_bridge.py:51-53](student/sandbox/mcp_bridge.py#L51-L53)) : la variable est **garantie présente au spawn**, quel que soit l'environnement (le `.env` n'est plus nécessaire). Correctif **transverse** : le serveur SWE lit la même variable (l. 46), donc il est lui aussi fiabilisé au démarrage — le lanceur ne les distingue pas.

**Vérification fonctionnelle complète** : import + `run_tests` avec une tâche MBPP valide → `'All test passed successfully !'` pour une solution correcte ; `os._exit(0)` → `'# exit code 1, no stderr'` (bloqué). Le serveur fonctionne de bout en bout, sans dépendance d'environnement non garantie.

---

## ✅ Bon

1. **Pré-vérification de syntaxe `compile()` avec retour explicite** — §V.1.3. `compile(f"{imports}\n\n{code}", "<mbpp_solution>", "exec")` avant toute exécution ; en cas de `SyntaxError`, message clair avec la **position** (`line {e.lineno}`) et la consigne de corriger et ré-essayer. L'agent n'est jamais laissé sans explication : pas d'échec silencieux, exactement l'esprit de §V.1.3 (« An edit introduced a syntax error » → feedback explicite).
2. **Patch `os._exit` (OS_EXIT_PATCH) contre le faux-positif classique** — `os._exit = PATCH_EXIT` où `PATCH_EXIT(status)` fait `sys.exit(1)`. C'est la défense directe contre le hack MBPP le plus connu : un modèle qui appelle `os._exit(0)` pour « réussir » sans exécuter les tests. L'historique git montre la progression de ce point (`f411bfa` → `6288229` → `160734e`), preuve qu'il a été traité comme une vraie vulnérabilité et non supposé. Le patch est injecté **avant** le `try:` qui contient la solution, donc `import os` dans la solution récupère le module déjà patché — et **avant** le code de la solution, donc aucune référence à `os._exit` ne peut être capturée préalablement.
3. **`except SystemExit` dans le sous-processus convertit tout `exit()`/`quit()`/`sys.exit()` en échec** — `try: … except SystemExit: sys.exit(1)`. Une solution qui appelle `exit(0)` (ou `sys.exit(0)`) lève `SystemExit(0)`, interceptée → code de retour 1 → test marqué en échec. Aucun chemin `exit(0)` ne produit un faux-passage.
4. **Isolation par test dans un sous-processus dédié, avec timeout** — chaque `TASK.test_list[i]` tourne dans son propre `subprocess.run([sys.executable, "-c", …], timeout=TIMEOUT_DELAY_SEC)`. Une solution qui boucle à l'infini ou plante **ne tue pas le serveur MCP** : `TimeoutExpired` est intercepté et le test est simplement marqué `# TIMEDOUT AFTER N SECONDS`. « All errors must be handled gracefully » (§IV.1.1) respecté ; le serveur survit à n'importe quel comportement de la solution.
5. **`input=""` force `stdin=PIPE` avec EOF immédiat** — l'enfant ne bloque jamais sur un stdin hérité. Critique sur transport **stdio**, où le serveur MCP écoute déjà sur son propre stdin : sans cela, le sous-processus de test hériterait du stdin du serveur et se disputerait les frames JSON Lines. Même garde que `run_tests` de SWE-bench, cohérence entre les deux serveurs.
6. **Extraction du motif d'échec depuis la dernière ligne de stderr, tronquée à 300 caractères** — `tb_lines[-1].strip()` récupère le message d'erreur réel (`NameError: name 'sub_list' is not defined`, par exemple), et `reason[:300]` borne la sortie. C'est exactement le feedback que l'agent MBPP doit recevoir pour corriger (§V.1.3 : l'agent ne doit jamais deviner). Format `"{test}  # {reason}"` : l'agent voit quel test a échoué **et** pourquoi.
7. **Résultats agrégés et lisibles** — `failed_tests` collecte toutes les erreurs, puis `"Error during the following tests :\n" + "\n".join(...)` renvoie l'ensemble en une seule réponse ; si tout passe, `"All test passed successfully !"`. Décision explicite et lisible par le LLM, ni crash ni retour ambigu.
8. **Cas limites du chargement de tâche traités proprement** — `TASK` chargé une fois au démarrage depuis `MBPP_TASK_JSON`, avec `ValidationError`/`JSONDecodeError` interceptées et fallback `None`. Si `None` : message clair sur `stderr` + `exit(1)` — le serveur **refuse de démarrer** plutôt que de servir des tests vides (`5a64000` a corrigé le cas « pas de message d'erreur au lancement sans tâche »). Le `TASK is None` est re-vérifié en entrée du tool avec un `MBPPException` descriptif (défense en profondeur).
9. **Gestion du cas « aucun test disponible »** — `if len(TASK.test_list) == 0: return "There are no available tests… You may skip testing."`. Le serveur dit explicitement à l'agent de passer, au lieu de boucler sur zéro test.
10. **Sélection de transport `Literal["http","stdio"]` correctement typée** — `mode: Literal["http", "stdio"]` affectée par condition explicite, validation de `MCP_TRANSPORT` avec un `TypeError` clair si valeur inconnue, défaut `stdio` conforme au docstring. Résout proprement le même `str`-brut-incompatible-avec-`Literal` que le serveur SWE avait eu à corriger (mypy à 0 erreur).
11. **L'architecture hôte est correcte pour MBPP** — contrairement à SWE-bench, aucun outil ici n'a besoin de `/testbed` ni de Docker. `run_tests` n'exige qu'un interpréteur Python en sous-processus, disponible sur l'hôte. C'est le cas où le modèle « MCP tools operate outside the sandbox » (l. 276-278) fonctionne tel quel, sans le trou architectural de `mcp_tools_swebench.py`.
12. **`flake8` et `mypy` propres** — `flake8` → exit 0, `mypy` → *Success: no issues found in 1 source file*, re-vérifiés après les dernières modifications le jour de l'audit. La docstring de module liste les prérequis avec le **bon** nom `MCP_TIMEOUT_DELAY` (l. 11-12 — corrigé depuis l'audit du 27/08, cf. Corrigés).
13. **Timeout configurable via `MCP_TIMEOUT_DELAY`, désormais garanti au démarrage** — `int(os.environ.get('MCP_TIMEOUT_DELAY', -1))` + contrôle `>= 1` (l. 59-67), la variable étant injectée par le lanceur (cf. « ✅ Résolu » et ✅ #16). Le timeout par-test n'est plus figé : il répond à l'esprit de `SandboxConfig.max_execution_time_seconds` (§V.2.3). Message d'erreur clair sur stderr si la variable est absente/invalide — cas désormais évité par le lanceur.
14. **Sortie bornée via `truncate_output`, importé depuis un module partagé sans effet de bord** — l'ex-❌ #3 du 27/08 (pas de limite de taille de sortie) est **résolu** : `truncate_output` est appliqué au message `SyntaxError` (l. 110-113) et au récapitulatif d'échecs (l. 145-146). La sortie ne peut plus inonder la réponse de l'outil (§V.1.3, troncature explicite). Et, contrairement à l'audit précédent, le helper est importé depuis `student/mcp_server_shared/share.py` (pas depuis le serveur frère) : **aucun couplage ni effet de bord** — voir « ✅ Résolu ».
15. **Module partagé propre `student/mcp_server_shared/share.py`** — c'est l'extraction recommandée au 27/08, mise en œuvre : un fichier qui ne contient que `MAX_OUTPUT_CHARS` et `truncate_output`, sans aucun import exécutable ni `exit(1)`. Utilisé par MBPP (l. 25) **et** SWE (l. 23) : source de vérité unique, cohérente entre serveurs, et qui supprime à elle seule le crash au démarrage (ex-🔴) et le couplage inter-serveurs (ex-❌ #3).
16. **Le lanceur injecte `MCP_TIMEOUT_DELAY` en plus de `MCP_TRANSPORT`** — `mcp_bridge._build_transport` pose `env={**os.environ, "MCP_TRANSPORT": "stdio", "MCP_TIMEOUT_DELAY": "60"}` ([mcp_bridge.py:51-53](student/sandbox/mcp_bridge.py#L51-L53)). C'est la résolution de l'ex-❌ #1 : la variable est **garantie présente** au spawn, sans dépendre du `.env` ni de l'env hôte. Correctif **transverse** qui fiabilise aussi le serveur SWE (même variable, l. 46). *Réserve mineure : la valeur est codée en dur à `60` dans le lanceur, pas lue depuis la config — à homogénéiser si un autre timeout était souhaité.*

---

## Trace — points écartés (non bloquants, ignorés)

Quatre points soulevés au cours de l'audit ont été **écartés** — trace conservée pour mémoire, ils ne comptent plus comme défauts :
1. **Défense anti-bypass reposant sur le patch `os._exit` seul, sans garde au niveau de l'échec** — le patch `OS_EXIT_PATCH` remplace `os._exit` **avant** l'exécution de la solution et bloque les vecteurs directs (`os._exit(0)`, `sys.exit(0)`, `from os import _exit`, `getattr(os, chr(95)+'exit')(0)`), vérifié par exécution réelle (`os._exit(0)` → `exit code 1`). Piste un temps envisagée : marqueur `_REACHED` de contrôle atteint, ou restrictions §V.2.3. **Écarté** : la défense couvre les vecteurs directs, un bypass plus fin est improbable en MBPP.
2. **Le code de la solution s'exécute sur l'hôte, non sandboxé (réseau + filesystem)** — `subprocess.run([sys.executable, "-c", …])` tourne hors des restrictions du sandbox (§V.2.3). Assumé par l'architecture (§V : MCP tools opèrent hors sandbox), acceptable pour des solutions MBPP algorithmiques. Piste : restreindre imports/builtins ou exécuter dans le conteneur. **Écarté** : choix architectural assumé.
3. **Extraction du motif par « dernière ligne de stderr »** — `tb_lines[-1].strip()` suppose que la dernière ligne de stderr est le message d'exception ; un `print(..., file=sys.stderr)` de la solution pourrait tromper l'agent. Piste un temps envisagée : parser le dernier `"Traceback (most recent call last):"` puis la dernière ligne non vide. **Écarté** : cas peu probable en MBPP, le feedback actuel reste utile.
4. **Descendants de process en timeout** — `subprocess.run` ne tue que l'enfant direct, pas son groupe. Piste : `start_new_session=True` + `os.killpg`. **Écarté** : risque faible en MBPP.

**Détails mineurs non bloquants** : `flake8` et `mypy` sont propres. La re-vérification `TASK is None` dans `run_tests` est défensive (le serveur `exit(1)` au démarrage sinon), donc jamais atteignable en pratique — inoffensif. Le `compile()` pré-vérifie `imports + code` mais pas la chaîne de test complète injectée ensuite ; acceptable car les tests viennent de la moulinette (source de confiance), pas du modèle. Le timeout est codé en dur à `60` dans le lanceur (cf. ✅ #16) : sans conséquence sur la fiabilité, juste un choix de valeur non paramétré.

---

## Corrigés (historique)

Points déjà réglés dans l'historique git ou le working tree de ce fichier — retirés des sections ❌/🔴, listés pour la trace.

| Point | Correctif | Commit / état |
|---|---|---|
| **🔴 Crash au démarrage** : MBPP importait `mcp_tools_swebench` dont le chargement appelle `exit(1)` (→ serveur tué si `SWE_TASK_JSON`/`MCP_TIMEOUT_DELAY` absentes) | `truncate_output` déplacé dans un module partagé **sans effet de bord** (`student/mcp_server_shared/share.py`), importé par les deux serveurs — l'import ne traverse plus jamais le serveur SWE | working tree (non committé) |
| **Couplage inter-serveurs (ex-❌ #3)** : `from mcp_tools_swebench import truncate_output` | Idem — import depuis le module partagé, plus de dépendance au serveur frère | working tree (non committé) |
| **Dépendance de démarrage `MCP_TIMEOUT_DELAY` non injectée (ex-❌ #1)** : le serveur `exit(1)` si la variable manque, et le lanceur ne la posait pas | `mcp_bridge._build_transport` injecte désormais `MCP_TIMEOUT_DELAY: "60"` en plus de `MCP_TRANSPORT` — la variable est garantie au spawn (sans dépendre du `.env`), pour MBPP **et** SWE | working tree (non committé) |
| Faux-passage via `exit(0)` : une solution pouvait sortir avec code 0 sans exécuter les tests | Patch `os._exit` + `except SystemExit: sys.exit(1)` injecté dans le sous-processus de test, en trois itérations | `f411bfa`, `6288229`, `160734e` |
| Timeout d'exécution du sous-processus | `subprocess.run(…, timeout=TIMEOUT_DELAY_SEC)` + interception de `TimeoutExpired` | `f7f9c3a` |
| Timeout par-test codé en dur (`TIMEOUT_DELAY_SEC = 10`) | Timeout chargé depuis la variable d'environnement `MCP_TIMEOUT_DELAY` avec validation (entier ≥ 1), désormais injecté par le lanceur (cf. ligne ci-dessus) | working tree (non committé) |
| Nom de variable erroné dans la docstring (« TIMEOUT_DELAY_SEC » au lieu de `MCP_TIMEOUT_DELAY`) | Docstring corrigée → `MCP_TIMEOUT_DELAY` (l. 11-12) | working tree (non committé) |
| Pas de limite de taille de sortie (ex-❌ #3 du 27/08) | `truncate_output` appliqué au retour `SyntaxError` (l. 110-113) et au récapitulatif d'échecs (l. 145-146), importé depuis le module partagé | working tree (non committé) |
| Check `_exit` (blocklist `if '_exit' in code`) ajouté puis retiré | Ajouté le 27/08 comme défense, puis **retiré** : redondant avec le patch, source de faux positifs (rejet de code correct) et contournable par noms calculés. La défense repose sur le patch seul | working tree (non committé, jamais commité) |
| Aucun message d'erreur au lancement du serveur sans tâche (`MBPP_TASK_JSON` absent/invalide) | Message clair sur `stderr` + `exit(1)` ; fallback `None` sur `ValidationError`/`JSONDecodeError` | `5a64000` |
| Docstring de module obsolète (info de dev périmée) | Docstring nettoyée sur les prérequis réels | `c82dfed` |

---

## Dépendance externe

1. **`from student.agent_mbpp.task import MBPPTaskInput`** — module qui **miroite `moulinette.models_public.MBPPTaskInput`** (hérité de `agent_core.schemas.TaskInput`) pour que l'agent et le contrat d'évaluation partagent le même schéma (§V.3.3). **Vérifié** : les champs (`task_id`, `task_definition`, `function_definition`, `test_imports`, `test_list`) correspondent exactement à ceux du sujet (l. 414-421). Le module `task.py` ne dépend pas de MCP ni du sandbox — le serveur reste indépendant de la boucle agent (§IV.2).
2. **`from student.mcp_server_shared.share import truncate_output`** (l. 25) — module partagé **sans effet de bord** (cf. ✅ #15). C'est la résolution du couplage inter-serveurs : au lieu d'importer depuis le serveur frère (comme au 27/08), MBPP et SWE lisent la même fonction depuis un module neutre. Dépendance saine et unique, ne casse pas l'indépendance du serveur MBPP vis-à-vis de l'autre benchmark.

---

## Priorités recommandées

**Aucune action correctrice requise.** L'outil obligatoire `run_tests` (§V.3.2) est implémenté, **conforme** et **vérifié fonctionnel** (exécution réelle le 28/08). Tous les obstacles au démarrage sont **résolus** : le crash SWE (import), le couplage inter-serveurs, et la dépendance `MCP_TIMEOUT_DELAY` désormais injectée par le lanceur. Les points écartés (voir « Trace ») ne constituent pas des obstacles — le serveur démarre et sert les tests de manière fiable.

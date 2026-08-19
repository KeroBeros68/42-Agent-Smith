# Audit — Partie Sandbox

> Audit de conformité de la partie sandbox réalisée à ce jour, par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-13
> **Dernière mise à jour** : 2026-08-18 — points corrigés retirés (voir « Corrigés depuis l'audit initial » en fin de document)
> **Périmètre** : `student/sandbox/` (fichiers implémentés uniquement) + `sandbox_template.json`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier, chacun justifié par référence au sujet ou par le comportement réel du code.

---

## ✅ Mise à jour : le round-trip de bout en bout fonctionne

`runner.py` a été écrit (version minimale : `exec`/`result`/`error`, sans restrictions ni watchdog). Testé en conditions réelles à plusieurs reprises — REPL → conteneur → `compile()`/`exec()` → réponse structurée → remontée par le socket (y compris un vrai cas d'erreur de syntaxe intercepté correctement). La connexion MCP (`MCPBridge`) a aussi été testée de bout en bout contre le vrai `mcp_tools_mbpp.py`.

Ce qui reste non branché : les restrictions (`restrictions.py` est écrit et testé **en isolation**, mais `runner.py` ne l'appelle pas encore — voir la section dédiée plus bas), le `watchdog.py` (timeout par exécution), et le relais `tool_call` conteneur↔`MCPBridge`.

---

## `cli.py`

### ✅ Bon

1. **Les 4 formes CLI du §V.2.1 sont couvertes syntaxiquement** — positionnel optionnel + deux flags. `uv run sandbox`, `uv run sandbox config.json`, `--mcp-stdio "..."`, `--mcp-server URL` parsent tous correctement.
2. **`mutually_exclusive_group`** — argparse refuse automatiquement les deux transports MCP simultanés, avec un message d'erreur généré. Deux serveurs MCP connectés n'ont pas de sens dans le modèle du sujet (un sandbox = un serveur connecté).
3. **`load_config` isolée de `main()`** — testable sans lancer Docker, et le fallback `SandboxConfig()` quand aucun fichier n'est donné correspond au cas `uv run sandbox` nu.
4. **`SandboxConfig(**data)` plutôt qu'un parsing manuel** — délègue la validation à Pydantic, donc un champ manquant prend son défaut et un champ de mauvais type est rejeté sans code de vérification maison.
5. **`with container as c`** — garantit `stop()` sur tous les chemins de sortie, y compris exception. C'est ce qui rend la contrainte §VII (nettoyage des conteneurs à votre charge) structurellement respectée plutôt que dépendante d'un `try/finally` oublié quelque part.

### ❌ Mauvais

1. **Le docstring ment sur le comportement** : « either the REPL (no task) or a single task run » — il n'y a aucun argument de tâche dans le parser, et `main()` lance inconditionnellement le REPL. En soutenance, un docstring qui décrit une capacité absente est plus coûteux qu'un docstring vide.

---

## `config.py`

### ✅ Bon

1. **Modèle Pydantic avec les 4 noms de champs exacts du sujet** — `authorized_imports`, `allowed_directories`, `max_execution_time_seconds`, `max_memory_mb`. Si la moulinette instancie votre `SandboxConfig` depuis un JSON qu'elle fournit, les clés correspondront.
2. **`description=` sur chaque `Field`** — ces métadonnées alimentent `model_json_schema()`. Utile au-delà de la doc : c'est exactement le mécanisme qui servira à générer le manuel du sandbox (§V.2.6) si vous décidez d'y exposer la config.
3. **`os` et `sys` retirés de l'allowlist** — décision correcte et non triviale. `os.system`, `os.remove`, `sys.modules` sont des vecteurs d'évasion directs ; les laisser aurait vidé la restriction de son sens.
4. **Constantes extraites au niveau module** — `AUTHORIZED_IMPORTS` etc. sont réutilisables par `restrictions.py` et par les tests sans instancier le modèle.
5. **Approche allowlist et non blocklist** — conforme au docstring du sujet (« only imports in authorized_imports are allowed. Everything else is blocked by default »). Une blocklist serait contournable par un module oublié.

### ❌ Mauvais

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

---

## `container.py`

### ✅ Bon

1. **`network_mode="none"`** — satisfait « No network access: Prevent any outbound or inbound network connections » (§V.2.3) au niveau du noyau, pas au niveau Python. C'est la seule des six contraintes de sécurité qui est actuellement **réellement** appliquée, et elle est incontournable depuis l'intérieur du conteneur.
2. **`cap_drop=["ALL"]` + `security_opt=["no-new-privileges"]` + `pids_limit` configurable** — non exigés par le sujet. Retirent toutes les capabilities Linux, empêchent tout gain de privilège via setuid, et bornent le nombre de process/threads (donc une fork bomb depuis le code exécuté). Le genre de choix que §VI.4 (« Sandbox security and isolation guarantees ») récompense en soutenance, à condition de savoir le justifier.
3. **Séquence `_ensure_image()` (build/pull) → image dérivée `FROM` + `COPY executor/` → `create()` → `start()`** — correcte et, surtout, **unifiée** : le même chemin de code embarque l'exécuteur dans une image construite par l'équipe et dans une image SWE-bench arbitraire, via un second `docker build` plutôt qu'une injection post-création. Aucun `if benchmark == ...` dans le gestionnaire de conteneur.
4. **`__enter__`/`__exit__` sans capture d'exception** — `__exit__` retourne `None` (falsy), donc toute exception, y compris `KeyboardInterrupt` et `SystemExit`, se propage après nettoyage. C'est précisément la contrainte §V.2.2. Beaucoup d'implémentations ratent ça en retournant `True`.
5. **Le démultiplexage du flux Docker est correct** — `tty=False` évite l'écho TTY, `_recv_exactly()` gère un en-tête ou une charge utile coupés entre deux paquets TCP, et `receive()` sépare stdout (protocole) de stderr (tracebacks du conteneur, conservées dans `_stderr_buffer` au lieu d'être perdues). La boucle `while b"\n" not in self._recv_buffer` avec conservation du reste après `split(..., 1)` traite les deux cas durs du framing applicatif : message coupé en deux frames, et deux messages dans une seule frame.

### ❌ Mauvais

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

---

## `executor/runner.py`

### ✅ Bon

1. **Round-trip complet vérifié en conditions réelles**, pas juste supposé — REPL/appels directs → conteneur Docker → `compile`/`exec` → réponse structurée → socket → host, testé plusieurs fois avec de vrais conteneurs (erreur de syntaxe, imports autorisés/refusés, persistance du namespace).
2. **`compile(code, "<sandbox>", "exec")`** — accepte plusieurs statements top-level en un seul message, après correction d'un bug trouvé par test (`"single"` rejetait tout bloc de plus d'un statement, ce qui aurait cassé n'importe quel code multi-lignes envoyé par la future boucle agent).
3. **`NAMESPACE` persistant confirmé fonctionnellement**, pas juste par lecture de code — testé `x = 10` puis `print(x * 2)` dans deux messages séparés, résultat `20`.
4. **`redirect_stdout` isole la sortie du code exécuté du canal protocole** — un `print()` dans le code utilisateur ne pollue jamais le flux JSON Lines que `container.py` essaie de parser.
5. **`except Exception`, pas `except BaseException`** — `SystemExit`/`KeyboardInterrupt` ne sont pas capturées, elles se propagent et terminent le conteneur plutôt que d'être avalées comme une erreur d'exécution ordinaire. Conforme à §V.2.2 : un `exit()` ou une interruption dans le code sandboxé doit se voir, pas être traité comme "juste une erreur de plus".

### ❌ Mauvais

1. **Pas de watchdog** — un `exec` qui boucle à l'infini bloque `runner.py` indéfiniment, aucune limite de temps par exécution.
2. **`final_answer` et les stubs d'outils MCP ne sont pas injectés dans `NAMESPACE`** — la connexion MCP fonctionne côté host (`MCPBridge`), mais rien ne relaie encore un `tool_call` depuis le conteneur, et rien ne signale la fin de tâche autrement qu'en quittant le REPL.

---

## `executor/restrictions.py`

### ✅ Bon

1. **Hook `sys.meta_path` plutôt que du pattern-matching sur le texte du code.** Un `MetaPathFinder` intercepte *tout* mécanisme d'import (`import X`, `from X import Y`, `__import__("X")`, `importlib.import_module("X")`) au niveau de l'interpréteur — contourne les techniques de bypass triviales qu'une simple recherche de sous-chaîne (`"os" in code`) laisserait passer (alias, imports dynamiques, espaces superflus).
2. **Purge de `sys.modules["os"]` ciblée et vérifiée empiriquement**, pas un balayage aveugle de tout `sys.modules`. Testé avant d'écrire le code : `os` est le seul module dangereux réellement pré-chargé au démarrage de l'interpréteur (avant même l'exécution de `runner.py`) — un `meta_path` seul ne l'aurait jamais intercepté puisque Python consulte `sys.modules` avant `sys.meta_path`.
3. **Pré-import de tous les modules autorisés avant d'activer la restriction.** Corrige un problème réel découvert par test : `random` (a besoin de `os.urandom` en interne), `json` (sous-modules `.decoder`/`.encoder`), `string` (`_string`), `copy` (`weakref`) échouaient tous à l'import sans ce mécanisme — résolu une fois pour toutes plutôt qu'au cas par cas avec des wildcards manuels.
4. **`find_spec` lève `ImportError` explicitement pour un import refusé**, au lieu de `return None` — un refus net immédiatement, pas une recherche qui continue silencieusement ailleurs dans les autres finders.
5. **Testé contre de vraies tentatives de contournement** (`__import__`, `importlib.import_module`, `from X import Y`) et vérifié fonctionnellement, pas juste syntaxiquement (`random.randint()` appelé en vrai après import, pas seulement "l'import ne lève pas"). Depuis, aussi vérifié **en conditions réelles dans un vrai conteneur Docker** (pas seulement en process isolé) : `os`/`subprocess` bloqués, `math`/`random` utilisables normalement.

### ❌ Mauvais

1. **Pas de restriction des builtins.** Le docstring du fichier couvre les deux volets (« Import allowlist **and** restricted builtins enforcement »), mais seul le premier est fait. `open`, `eval`, `exec` (le vrai, pas celui de `runner.py`) restent accessibles tels quels dans le namespace d'exécution.
2. **`PRELOADED_DANGEROUS_MODULES = ("os",)` est une liste figée**, basée sur une vérification empirique faite sur cette machine/cette image de base précise. Si l'image Docker change (autre variante `python:3.10-slim`, autre OS de base), un autre module dangereux pourrait se retrouver pré-chargé sans qu'on l'ait revérifié.

---

## `repl.py`

### ✅ Bon

1. **Les deux conditions de sortie du sujet sont là** — `exit` et EOF (Ctrl+D), littéralement « It exits cleanly on the exit command or on EOF (Ctrl+D) ».
2. **`EOFError` capturée plutôt que laissée remonter** — sans ce `try`, Ctrl+D produirait une traceback. C'est la différence entre « exits cleanly » et « crashe à la fermeture ».
3. **`.strip()` sur le test de sortie** — `"exit "` avec un espace parasite fonctionne. Détail, mais c'est le genre de chose qu'un correcteur teste au clavier en 2 secondes.
4. **`container` reçu en paramètre, pas construit ici** — le REPL ne possède pas le cycle de vie, donc il ne peut pas fuiter un conteneur ni empêcher `cli.py` de le nettoyer. Séparation correcte.
5. **Ignore totalement Docker, les sockets et le format de trame** — ne connaît que `send`/`receive`. Si le mécanisme d'isolation change (process au lieu de conteneur), ce fichier ne bouge pas.

### ❌ Mauvais

1. **`print(response)` affiche le dict brut** — l'utilisateur verra `{'type': 'result', 'stdout': '4\n'}` au lieu de `4`. Le sujet demande « it prints the result or any raised error » : résultat et erreur doivent être **distingués** visuellement, ce que l'affichage d'un dict ne fait pas.
2. **Le cas `final_answer` n'est pas traité.** Le sujet exige que le REPL ait « the connected MCP tool wrappers and final_answer available ». Si l'utilisateur tape `final_answer("x")`, le message de retour aura un type différent de `result` — et rien ici ne le reconnaît. L'implémentation est côté exécuteur, mais l'affichage est côté REPL.

---

## `Dockerfile`

### ✅ Bon

1. **`python:3.10-slim`** — respecte « You must use Python 3.10 » (§IV.1) au niveau de l'environnement d'exécution du code non fiable, pas seulement du projet.
2. **`USER sandbox` (uid 1000, non-root)** — si `restrictions.py` était contourné, le code s'exécuterait quand même sans droits root **dans** le conteneur. Défense en profondeur, cumulée avec `cap_drop=ALL`.
3. **Aucun `apt-get`, aucun `pip install`** — l'allowlist ne contenant que de la stdlib, il n'y a rien à installer. Surface d'attaque minimale, image légère, build rapide.
4. **Aucun `CMD`/`ENTRYPOINT`** — cohérent avec `container.py` qui passe toujours `command=` explicitement. Un défaut ici serait du code mort, ou pire, une divergence silencieuse entre l'image MBPP et les images SWE-bench.

### ❌ Mauvais

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

---

## Récapitulatif de conformité §V.2

| Exigence | État |
|---|---|
| CLI `uv run sandbox` (4 formes) | ✅ Les 4 formes fonctionnent, testé de bout en bout (`--mcp-stdio` contre le vrai `mcp_tools_mbpp.py`) |
| REPL interactif | 🟡 Boucle, sorties, multi-ligne et Ctrl+C OK ; affichage brut, `final_answer` non traité |
| `final_answer` injecté | ❌ Absent |
| `KeyboardInterrupt`/`SystemExit` propagées | ✅ Structurellement garanti par `__exit__` |
| Restriction imports | ✅ Branché et vérifié en conditions réelles (Docker) |
| Restriction filesystem | 🟡 Racine en read-only + tmpfs (Docker) ; l'allowlist `allowed_directories` reste à appliquer dans `restrictions.py` |
| Pas de réseau | ✅ `network_mode="none"` |
| Timeout d'exécution | ❌ Stub |
| Limite mémoire | ✅ `mem_limit` |
| Builtins restreints | ❌ Stub |
| Intégration MCP (stdio + HTTP) | 🟡 Connexion réelle + découverte des tools fonctionnelles (`MCPBridge`, testé contre `mcp_tools_mbpp.py`) ; `protocol.py` définit le message `tool_call` mais `runner.py` ne l'émet pas encore, transport HTTP non testé en réel |
| Manuel dynamique | ❌ Stub |
| Config Pydantic + JSON | ✅ Fait, défauts à réaligner |

---

## Priorités recommandées

Par ordre d'impact sur la note :

1. **Écrire `watchdog.py`** — timeout par exécution, dernière des 6 contraintes de sécurité pas encore couverte (`exam_sandbox.sh` exige **100 %**, §VI.2)
2. **Restreindre les builtins** (`open`, `eval`, `exec`...) — deuxième volet de `restrictions.py`, pas encore fait
3. **Relayer les `tool_call`** conteneur → `MCPBridge` et injecter `final_answer`/les stubs d'outils dans `NAMESPACE` — la connexion MCP fonctionne déjà côté host, mais `runner.py` ne sait pas encore émettre ce type de message ni attendre sa réponse

---

## Corrigés depuis l'audit initial

| Point | Fichier | Correctif appliqué | Date |
|---|---|---|---|
| `tty=True` cassait le protocole (écho TTY renvoyant nos propres messages) | `container.py` | `tty=False` + démultiplexage des frames Docker (`_recv_exactly`, `_read_frame`), stderr capturé séparément | 2026-08-13 |
| Convention d'import de `executor/` non tranchée | `executor/__init__.py` | Imports plats absolus (`import protocol`), lancement en script simple depuis `/sandbox_executor` ; décision et conséquences documentées dans le docstring du package | 2026-08-13 |
| Tout le filesystem du conteneur était inscriptible (`/tmp`, `/home/sandbox`, `/dev/shm`) | `container.py` | `read_only=True` + `tmpfs` sur `/workspace` et `/tmp` avec `noexec,nosuid,nodev`, `size=64m` (un tmpfs est en RAM → DoS sinon) et `uid=1000,gid=1000` (sans quoi le montage root:root rendrait `/workspace` inutilisable pour l'utilisateur non-root) | 2026-08-13 |
| `pids_limit` absent — pas de protection contre une fork bomb | `config.py`, `container.py`, `sandbox_template.json` | Champ `pids_limit` (défaut 64) ajouté au modèle, branché sur `create(pids_limit=self._config.pids_limit)` | 2026-08-13 |
| Base `python:3.10-slim` non épinglée (tag mutable) | `Dockerfile` | `FROM python:3.10-slim@sha256:...` — digest fixe, format vérifié valide (64 hex) | 2026-08-13 |
| `chown sandbox:sandbox /workspace` devenu mort après l'ajout du tmpfs | `Dockerfile` | Ligne retirée | 2026-08-13 |
| `pathlib` dans l'allowlist annulait le retrait de `os` | `config.py` | `pathlib` retiré ; `copy`, `array`, `cmath` ajoutés (alignement sur la config de référence du sujet) ; notation wildcard (`math.*`, `collections.*`, `datetime.*`, `typing.*`) introduite dans la liste | 2026-08-13 |
| Aucune contrainte de validation sur les champs numériques | `config.py` | `Field(gt=0)` sur `max_execution_time_seconds`, `max_memory_mb`, `pids_limit` | 2026-08-13 |
| `pids_limit` sans description, docstring du fichier non mise à jour | `config.py` | Description ajoutée (« Maximum number of processes/threads … to prevent fork bombs »), docstring corrigée pour lister les 5 champs | 2026-08-13 |
| Pas de `if __name__ == "__main__": main()` | `cli.py` | Ajouté | 2026-08-13 |
| `csv` restait dans l'allowlist | `config.py` | Retiré | 2026-08-13 |
| `allowed_directories` ignorait `/testbed` | `config.py` | `/testbed` ajouté à côté de `/workspace` | 2026-08-13 |
| `Field(gt=0)` mal appliqué à `authorized_imports`/`allowed_directories` (contrainte numérique sur des `list[str]`) | `config.py` | Remplacé par `Field(min_length=1)` sur ces deux champs | 2026-08-13 |
| Zéro gestion d'erreur (§IV.1) — config introuvable/malformée, Docker absent → traceback brute | `cli.py` | `try/except` ciblés dans `main()` : `FileNotFoundError`, `json.JSONDecodeError`, `pydantic.ValidationError` autour du chargement de config ; `docker.errors.DockerException` autour du cycle de vie du conteneur. Message clair + `sys.exit(1)` ; `KeyboardInterrupt`/`SystemExit` non interceptés (§V.2.2 toujours respecté) | 2026-08-13 |
| `put_archive()` échoue sur un conteneur `read_only=True` (« container rootfs is marked read-only »), vérifié empiriquement — l'injection tar était donc cassée dans tous les cas, pas seulement en théorie | `container.py` | Remplacé par une image dérivée `FROM {base_image}` + `COPY --chown=1000:1000 executor/ /sandbox_executor`, construite juste avant `create()` ; fonctionne uniformément pour l'image maison MBPP et une image SWE-bench arbitraire, corrige aussi au passage l'uid des fichiers injectés (c'était le point « Mauvais » n°2 du `Dockerfile` dans l'audit initial) et le risque `__pycache__` (filtre `_skip_pycache` sur `tar.add`) | 2026-08-14 |
| Pas de `.dockerignore` — tout `sandbox/` envoyé comme contexte de build (sources, `__pycache__`), alors qu'aucun `COPY` n'utilisait ce contexte | `Dockerfile`, `cli.py` | `student/sandbox/.dockerignore` avec `*` (tout ignoré — le `Dockerfile` de base n'a aucun `COPY`) ; build réel testé (`docker build`) pour confirmer que rien ne casse | 2026-08-14 |
| Digest `python:3.10-slim@sha256:...` non vérifié contre le registre | `Dockerfile` | Confirmé par un `docker build` réel réussi (image récupérée et construite avec succès) | 2026-08-14 |
| `receive()` bloquait indéfiniment, sans timeout | `container.py` | `settimeout()` sur le socket attaché (`max_execution_time_seconds` + marge de 30 s), `TimeoutError` levée avec message clair dans `_recv_exactly()` | 2026-08-14 |
| `stop()` fuyait un conteneur dès la première erreur (`AttributeError` possible si `_socket` restait `None`) | `container.py` | `try/finally` imbriqué par étape (stop → close socket → remove), `remove(force=True)`, l'état est remis à `None` quoi qu'il arrive | 2026-08-14 |
| `KeyboardInterrupt` non gérée dans le REPL → traceback à l'écran au lieu d'annuler la ligne en cours | `repl.py` | Ctrl+C réinitialise le buffer et redonne le prompt `>>>` (comportement REPL standard) ; seul Ctrl+D (EOF) quitte, inchangé | 2026-08-14 |
| REPL limité à une ligne — impossible de saisir `def`/`for`/`try` multi-ligne | `repl.py` | `_read_block()` accumule les lignes et utilise `codeop.compile_command()` (le module stdlib du vrai REPL Python) pour détecter bloc incomplet (prompt `...`) vs complet vs syntaxe invalide ; comportement vérifié manuellement contre plusieurs cas (`def` seul, `def`+corps, `def`+corps+ligne vide, syntaxe invalide) | 2026-08-14 |
| `ConnectionError`/`TimeoutError` de `send`/`receive` non capturées dans le REPL — traceback si le conteneur meurt ou se fige | `repl.py` | `try/except (ConnectionError, TimeoutError)` autour de `send`/`receive`, message + sortie propre de la boucle. Note mineure non bloquante : le message affiché ("Connection to container lost.") est un peu imprécis pour le cas timeout (conteneur figé, pas forcément déconnecté) | 2026-08-14 |
| `_stderr_buffer` rempli mais jamais lu — crash de `runner.py` se manifestait par un `ConnectionError` opaque | `container.py` | Propriété `stderr` ajoutée ; `receive()` enrichit le `ConnectionError` avec le contenu de `_stderr_buffer` s'il y en a. Testé de bout en bout (build + start + échec attendu) : le chemin ne casse rien même quand le buffer est vide (fallback sur le message original) | 2026-08-14 |
| Image dérivée `sandbox-executor:<hash>` jamais nettoyée, accumulation dans le cache Docker local | `container.py` | Supprimée dans `stop()` (`images.remove(force=True)`) après le conteneur, dans le même enchaînement `try/finally` par étape ; vérifié par un test réel — plus aucune image `sandbox-executor:*` après le `with`, l'image de base reste (réutilisation voulue entre sessions) | 2026-08-14 |
| `--mcp-stdio`/`--mcp-server` parsés puis totalement ignorés (§V.2.5, exigence dure) | `cli.py`, `mcp_bridge.py` (nouveau) | `MCPBridge` : facade synchrone sur `fastmcp.Client` (async), pont via thread + event loop dédiée (`_run()` seul point de passage sync→async), connexion stdio (`shlex.split` + `StdioTransport`) ou HTTP (URL passée telle quelle, transport inféré par `fastmcp`). Branché dans `cli.py` via `contextlib.ExitStack` (nettoyage garanti, avec ou sans flag MCP). Testé de bout en bout contre le vrai `mcp_tools_mbpp.py` : connexion stdio réelle, `list_tools()` découvre bien `run_tests`, cleanup confirmé. Le relais `tool_call` conteneur→bridge n'existe pas encore (dépend de `runner.py`/`protocol.py`) | 2026-08-14 |
| `runner.py` vide — rien ne tournait de bout en bout | `executor/protocol.py` (nouveau), `executor/runner.py` (nouveau) | `protocol.py` : `TypedDict` pour chaque type de message (`exec`, `result`, `error`, `tool_call`, `tool_result`, `final_answer`). `runner.py` (version minimale, sans restrictions ni watchdog) : `NAMESPACE` persistant, `compile(..., "single")` + `redirect_stdout` pour capturer la sortie et auto-afficher les expressions comme un vrai REPL, `sys.stdout.flush()` explicite (stdout bufferisé sans tty). Testé en conditions réelles (REPL manuel, y compris un cas d'erreur de syntaxe) | 2026-08-17 |
| Aucune restriction d'imports — code exécuté sans limite | `executor/restrictions.py` (nouveau) | Hook `sys.meta_path` (intercepte `import`/`from`/`__import__`/`importlib.import_module`, pas de pattern-matching texte contournable) + purge ciblée de `os` (seul module dangereux pré-chargé au démarrage, vérifié empiriquement) + pré-import de tous les modules autorisés avant activation (corrige un bug réel trouvé par test : `random`/`json`/`string`/`copy` cassaient sans ça). Testé contre de vraies tentatives de contournement et fonctionnellement (`random.randint()` produit un résultat) | 2026-08-18 |
| `restrictions.install()` écrit mais jamais appelé — `runner.py` n'avait aucun moyen de recevoir `SandboxConfig` | `container.py`, `executor/runner.py` | Toute la `SandboxConfig` sérialisée en JSON dans la variable d'env `SANDBOX_CONFIG_JSON` posée à la création du conteneur (`model_dump_json()`), lue côté `runner.py` **avant** l'appel à `restrictions.install()` (le `import os` nécessaire pour lire `os.environ` a lieu avant la purge de `os`, même principe que le pré-import). Un seul passage réutilisable pour `watchdog.py` plus tard (même variable, autres champs). Vérifié en conditions réelles Docker | 2026-08-18 |
| `compile(code, "<sandbox>", "single")` dans `runner.py` rejetait tout message de plus d'un statement (`SyntaxError: multiple statements found`) — aurait cassé tout code multi-lignes envoyé par la future boucle agent | `executor/runner.py` | Mode changé en `"exec"` (accepte plusieurs statements, perd l'auto-affichage REPL d'une expression isolée — acceptable, un LLM utilise `print()` explicitement). Trouvé et corrigé grâce au test Docker réel avec `import math\nprint(math.sqrt(16))`, pas en théorie | 2026-08-18 |
| Message protocole malformé (JSON invalide, `"type"` absent) faisait planter tout `runner.py` — le `except Exception` référençait `message["type"]`, qui plantait à son tour si `message` n'existait pas encore | `executor/runner.py` | `try/except/else` : `json.JSONDecodeError` capturée spécifiquement (pas `Exception`), `message.get("type")` au lieu de `message["type"]` (plus de `KeyError` possible), messages d'erreur reflétant la vraie cause. Testé en conditions réelles Docker : JSON invalide, type inconnu, champ `type` absent — les trois renvoient une `ErrorMessage` claire et la session survit (un `exec` normal juste après fonctionne toujours) | 2026-08-18 |

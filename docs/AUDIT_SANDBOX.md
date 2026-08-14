# Audit — Partie Sandbox

> Audit de conformité de la partie sandbox réalisée à ce jour, par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-13
> **Dernière mise à jour** : 2026-08-14 — points corrigés retirés (voir « Corrigés depuis l'audit initial » en fin de document)
> **Périmètre** : `student/sandbox/` (fichiers implémentés uniquement) + `sandbox_template.json`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier, chacun justifié par référence au sujet ou par le comportement réel du code.

---

## ⚠️ Préambule : l'état actuel ne peut pas tourner de bout en bout

`container.py:69` lance `python3 /sandbox_executor/runner.py`, mais `runner.py` ne contient qu'un docstring. Le conteneur démarre, exécute un script vide, **se termine immédiatement**. `attach_socket()` s'attache donc à un conteneur mort, et le premier `receive()` lèvera `ConnectionError`.

Ce n'est pas un défaut de conception — c'est l'ordre de construction qui a mis le transport avant l'exécuteur. À garder en tête : **rien de ce qui suit n'a encore été validé par une exécution réelle**.

---

## `cli.py`

### ✅ Bon

1. **Les 4 formes CLI du §V.2.1 sont couvertes syntaxiquement** — positionnel optionnel + deux flags. `uv run sandbox`, `uv run sandbox config.json`, `--mcp-stdio "..."`, `--mcp-server URL` parsent tous correctement.
2. **`mutually_exclusive_group`** — argparse refuse automatiquement les deux transports MCP simultanés, avec un message d'erreur généré. Deux serveurs MCP connectés n'ont pas de sens dans le modèle du sujet (un sandbox = un serveur connecté).
3. **`load_config` isolée de `main()`** — testable sans lancer Docker, et le fallback `SandboxConfig()` quand aucun fichier n'est donné correspond au cas `uv run sandbox` nu.
4. **`SandboxConfig(**data)` plutôt qu'un parsing manuel** — délègue la validation à Pydantic, donc un champ manquant prend son défaut et un champ de mauvais type est rejeté sans code de vérification maison.
5. **`with container as c`** — garantit `stop()` sur tous les chemins de sortie, y compris exception. C'est ce qui rend la contrainte §VII (nettoyage des conteneurs à votre charge) structurellement respectée plutôt que dépendante d'un `try/finally` oublié quelque part.

### ❌ Mauvais

1. **`--mcp-stdio` / `--mcp-server` sont parsés puis totalement ignorés.** `args.mcp_stdio` et `args.mcp_server` ne sont lus nulle part dans `main()`. Concrètement, les 3 commandes du sujet qui incluent un flag MCP se comportent **exactement** comme `uv run sandbox` nu : aucun serveur connecté, aucun outil dans le namespace. C'est l'écart de conformité le plus large du fichier, et il touche une exigence dure (§V.2.5 : « Both stdio or streamable HTTP transports must be supported »).
2. **Le docstring ment sur le comportement** : « either the REPL (no task) or a single task run » — il n'y a aucun argument de tâche dans le parser, et `main()` lance inconditionnellement le REPL. En soutenance, un docstring qui décrit une capacité absente est plus coûteux qu'un docstring vide.

---

## `config.py`

### ✅ Bon

1. **Modèle Pydantic avec les 4 noms de champs exacts du sujet** — `authorized_imports`, `allowed_directories`, `max_execution_time_seconds`, `max_memory_mb`. Si la moulinette instancie votre `SandboxConfig` depuis un JSON qu'elle fournit, les clés correspondront.
2. **`description=` sur chaque `Field`** — ces métadonnées alimentent `model_json_schema()`. Utile au-delà de la doc : c'est exactement le mécanisme qui servira à générer le manuel du sandbox (§V.2.6) si vous décidez d'y exposer la config.
3. **`os` et `sys` retirés de l'allowlist** — décision correcte et non triviale. `os.system`, `os.remove`, `sys.modules` sont des vecteurs d'évasion directs ; les laisser aurait vidé la restriction de son sens.
4. **Constantes extraites au niveau module** — `AUTHORIZED_IMPORTS` etc. sont réutilisables par `restrictions.py` et par les tests sans instancier le modèle.
5. **Approche allowlist et non blocklist** — conforme au docstring du sujet (« only imports in authorized_imports are allowed. Everything else is blocked by default »). Une blocklist serait contournable par un module oublié.

### ❌ Mauvais

1. **Les wildcards sont dans la liste, mais rien ne les interprète encore.** `"math.*"`, `"collections.*"`, `"datetime.*"`, `"typing.*"` sont désormais présents comme chaînes littérales dans `AUTHORIZED_IMPORTS` — mais `restrictions.py` (le fichier qui doit s'en servir) est encore un stub vide. Tant qu'il n'implémente pas le matching par motif, ces entrées ne valent qu'un match exact sur la chaîne `"math.*"`, ce qui n'autorise `import` d'aucun vrai module. Le format est choisi, le comportement ne l'est pas encore.

---

## `container.py`

### ✅ Bon

1. **`network_mode="none"`** — satisfait « No network access: Prevent any outbound or inbound network connections » (§V.2.3) au niveau du noyau, pas au niveau Python. C'est la seule des six contraintes de sécurité qui est actuellement **réellement** appliquée, et elle est incontournable depuis l'intérieur du conteneur.
2. **`cap_drop=["ALL"]` + `security_opt=["no-new-privileges"]` + `pids_limit` configurable** — non exigés par le sujet. Retirent toutes les capabilities Linux, empêchent tout gain de privilège via setuid, et bornent le nombre de process/threads (donc une fork bomb depuis le code exécuté). Le genre de choix que §VI.4 (« Sandbox security and isolation guarantees ») récompense en soutenance, à condition de savoir le justifier.
3. **Séquence `_ensure_image()` (build/pull) → image dérivée `FROM` + `COPY executor/` → `create()` → `start()`** — correcte et, surtout, **unifiée** : le même chemin de code embarque l'exécuteur dans une image construite par l'équipe et dans une image SWE-bench arbitraire, via un second `docker build` plutôt qu'une injection post-création. Aucun `if benchmark == ...` dans le gestionnaire de conteneur.
4. **`__enter__`/`__exit__` sans capture d'exception** — `__exit__` retourne `None` (falsy), donc toute exception, y compris `KeyboardInterrupt` et `SystemExit`, se propage après nettoyage. C'est précisément la contrainte §V.2.2. Beaucoup d'implémentations ratent ça en retournant `True`.
5. **Le démultiplexage du flux Docker est correct** — `tty=False` évite l'écho TTY, `_recv_exactly()` gère un en-tête ou une charge utile coupés entre deux paquets TCP, et `receive()` sépare stdout (protocole) de stderr (tracebacks du conteneur, conservées dans `_stderr_buffer` au lieu d'être perdues). La boucle `while b"\n" not in self._recv_buffer` avec conservation du reste après `split(..., 1)` traite les deux cas durs du framing applicatif : message coupé en deux frames, et deux messages dans une seule frame.

### ❌ Mauvais

1. **`_stderr_buffer` est rempli mais jamais lu.** Les tracebacks du conteneur sont désormais capturées, mais rien ne les remonte à l'utilisateur ni à la boucle agent. En l'état, un crash de `runner.py` se manifeste par un `ConnectionError` opaque alors que la cause exacte est disponible dans le buffer — exactement le « silent failure » que §V.1.3 interdit.
2. **La tag de l'image dérivée (`sandbox-executor:<hash(base_image)>`) n'est jamais nettoyée.** Chaque base image distincte accumule une image dans le cache Docker local, jamais supprimée par `stop()`. Bénin en local, moins en CI si le disque est contraint.

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
| CLI `uv run sandbox` (4 formes) | 🟡 Parse tout, n'utilise que 2 formes sur 4 |
| REPL interactif | 🟡 Boucle, sorties, multi-ligne et Ctrl+C OK ; affichage brut, `final_answer` non traité |
| `final_answer` injecté | ❌ Absent |
| `KeyboardInterrupt`/`SystemExit` propagées | ✅ Structurellement garanti par `__exit__` |
| Restriction imports | ❌ Stub |
| Restriction filesystem | 🟡 Racine en read-only + tmpfs (Docker) ; l'allowlist `allowed_directories` reste à appliquer dans `restrictions.py` |
| Pas de réseau | ✅ `network_mode="none"` |
| Timeout d'exécution | ❌ Stub |
| Limite mémoire | ✅ `mem_limit` |
| Builtins restreints | ❌ Stub |
| Intégration MCP (stdio + HTTP) | ❌ Stub, flags CLI ignorés |
| Manuel dynamique | ❌ Stub |
| Config Pydantic + JSON | ✅ Fait, défauts à réaligner |

---

## Priorités recommandées

Par ordre d'impact sur la note :

1. **Écrire `executor/runner.py`** — sans lui, rien ne tourne (cf. préambule)
2. **Brancher les flags MCP ignorés dans `cli.py`** (§V.2.5, exigence dure)
3. **Implémenter `restrictions.py`** — c'est là que se jouent 3 des 6 contraintes de sécurité, et `exam_sandbox.sh` exige **100 %** de réussite (§VI.2). Doit notamment interpréter le matching wildcard (`"math.*"`) déjà présent dans `AUTHORIZED_IMPORTS`, sinon ces entrées ne servent à rien.
4. **Robustesse** : exploitation de `_stderr_buffer`, nettoyage de l'image dérivée `sandbox-executor:*`

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

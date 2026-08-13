# Audit — Partie Sandbox

> Audit de conformité de la partie sandbox réalisée à ce jour, par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-13
> **Dernière mise à jour** : 2026-08-13 — points corrigés retirés (voir « Corrigés depuis l'audit initial » en fin de document)
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
2. **Zéro gestion d'erreur, alors que §IV.1 en fait un critère d'échec** (« All errors must be handled gracefully — crashes during evaluation will result in failure »). Quatre crashes atteignables trivialement : chemin de config inexistant → `FileNotFoundError` brut ; JSON malformé → `json.JSONDecodeError` ; champ invalide → `pydantic.ValidationError` ; démon Docker absent → `docker.errors.DockerException`. Chacun sort une traceback Python au lieu d'un message + code retour.
3. **`SANDBOX_BUILD_CONTEXT = Path(__file__).parent`** envoie **tout** `sandbox/` au démon Docker comme contexte de build — y compris `__pycache__/`, `container.py`, `mcp_bridge.py`. Aucun de ces fichiers n'est utilisé par le `Dockerfile`. Sans `.dockerignore`, chaque build transfère du bruit et tout changement dans n'importe quel `.py` invalide le cache de contexte.
4. **Le docstring ment sur le comportement** : « either the REPL (no task) or a single task run » — il n'y a aucun argument de tâche dans le parser, et `main()` lance inconditionnellement le REPL. En soutenance, un docstring qui décrit une capacité absente est plus coûteux qu'un docstring vide.
5. **Pas de `if __name__ == "__main__": main()`** — l'entry point `[project.scripts]` fonctionne, mais `python -m sandbox.cli` (réflexe courant en debug) ne fait rien du tout, silencieusement.

---

## `config.py`

### ✅ Bon

1. **Modèle Pydantic avec les 4 noms de champs exacts du sujet** — `authorized_imports`, `allowed_directories`, `max_execution_time_seconds`, `max_memory_mb`. Si la moulinette instancie votre `SandboxConfig` depuis un JSON qu'elle fournit, les clés correspondront.
2. **`description=` sur chaque `Field`** — ces métadonnées alimentent `model_json_schema()`. Utile au-delà de la doc : c'est exactement le mécanisme qui servira à générer le manuel du sandbox (§V.2.6) si vous décidez d'y exposer la config.
3. **`os` et `sys` retirés de l'allowlist** — décision correcte et non triviale. `os.system`, `os.remove`, `sys.modules` sont des vecteurs d'évasion directs ; les laisser aurait vidé la restriction de son sens.
4. **Constantes extraites au niveau module** — `AUTHORIZED_IMPORTS` etc. sont réutilisables par `restrictions.py` et par les tests sans instancier le modèle.
5. **Approche allowlist et non blocklist** — conforme au docstring du sujet (« only imports in authorized_imports are allowed. Everything else is blocked by default »). Une blocklist serait contournable par un module oublié.

### ❌ Mauvais

1. **`pathlib` dans l'allowlist annule l'intérêt d'avoir retiré `os`.** `pathlib.Path("/etc/passwd").read_text()`, `Path("/").iterdir()`, `Path(x).unlink()` — accès fichier complet en lecture, écriture et suppression. La porte `os` est fermée, la fenêtre `pathlib` est ouverte. Idem pour `csv` (qui ouvre des fichiers) dans une moindre mesure. Le sujet ne liste **ni** `pathlib` **ni** `csv` dans son exemple de défaut, probablement pour cette raison.
2. **`allowed_directories: ["/workspace"]` ignore `/testbed`.** Le sujet est explicite : les dépôts SWE-bench vivent dans `/testbed`, et l'exemple de config du sujet est `["/testbed", "/tmp/agent"]`. La justification donnée (« plusieurs entrées pour séparer le workspace de la tâche d'une zone scratch inscriptible ») indique un usage attendu à deux répertoires. Ce défaut-là bloquera les tâches SWE-bench.
3. **Aucune notion de wildcard.** Le sujet écrit `"math.*"`, `"collections.*"`, `"typing.*"`, `"datetime.*"` dans sa config de référence. Avec un matching par égalité de chaîne, `import collections.abc` sera refusé alors que `collections` est autorisé — et `collections.abc` est utilisé par du code Python parfaitement banal. La syntaxe de motif doit être décidée **dans ce fichier** avant d'écrire `restrictions.py`, sinon les deux divergeront.
4. **Modules absents du défaut du sujet** : `copy`, `array`, `cmath`. `copy` en particulier (`deepcopy`) apparaît constamment dans des solutions MBPP. Rien n'oblige à recopier la liste du sujet, mais une divergence en *moins* sur un module courant se paiera en tâches échouées.
5. **Aucune contrainte de validation** — `max_execution_time_seconds: int` accepte `0` et `-5`. Un JSON avec `"max_memory_mb": 0` passerait la validation et produirait un conteneur ingérable. `Field(gt=0)` aurait un coût nul.

---

## `container.py`

### ✅ Bon

1. **`network_mode="none"`** — satisfait « No network access: Prevent any outbound or inbound network connections » (§V.2.3) au niveau du noyau, pas au niveau Python. C'est la seule des six contraintes de sécurité qui est actuellement **réellement** appliquée, et elle est incontournable depuis l'intérieur du conteneur.
2. **`cap_drop=["ALL"]` + `security_opt=["no-new-privileges"]`** — non exigés par le sujet. Retirent toutes les capabilities Linux et empêchent tout gain de privilège via setuid. Le genre de choix que §VI.4 (« Sandbox security and isolation guarantees ») récompense en soutenance, à condition de savoir le justifier.
3. **Séquence `create()` → `put_archive()` → `start()`** — correcte et, surtout, **unifiée** : le même chemin de code injecte l'exécuteur dans une image construite par l'équipe et dans une image SWE-bench arbitraire. Aucun `if benchmark == ...` dans le gestionnaire de conteneur.
4. **`__enter__`/`__exit__` sans capture d'exception** — `__exit__` retourne `None` (falsy), donc toute exception, y compris `KeyboardInterrupt` et `SystemExit`, se propage après nettoyage. C'est précisément la contrainte §V.2.2. Beaucoup d'implémentations ratent ça en retournant `True`.
5. **Le démultiplexage du flux Docker est correct** — `tty=False` évite l'écho TTY, `_recv_exactly()` gère un en-tête ou une charge utile coupés entre deux paquets TCP, et `receive()` sépare stdout (protocole) de stderr (tracebacks du conteneur, conservées dans `_stderr_buffer` au lieu d'être perdues). La boucle `while b"\n" not in self._recv_buffer` avec conservation du reste après `split(..., 1)` traite les deux cas durs du framing applicatif : message coupé en deux frames, et deux messages dans une seule frame.

### ❌ Mauvais

1. **`receive()` bloque indéfiniment, sans timeout.** Le socket est en mode bloquant. Si le conteneur se fige (boucle infinie et watchdog défaillant) ou meurt sans fermer proprement, `recv()` ne rend jamais la main — et la boucle agent avec lui. Les limites d'examen sont des murs de temps réel (120 s MBPP, 900 s SWE-bench) : un blocage ici fait échouer la tâche sans aucun diagnostic. `settimeout()` + gestion de `socket.timeout` est nécessaire.
2. **`stop()` fuit un conteneur dès la première erreur.** Les trois appels sont séquentiels et non protégés : si `self._container.stop()` lève (`NotFound` si le conteneur est déjà mort, `APIError` si le démon hoquette), ni `_socket.close()` ni `remove()` ne s'exécutent → **conteneur orphelin**. Or §VII met le nettoyage explicitement à la charge de l'équipe. Second bug dans la même méthode : si `start()` échoue après `create()` mais avant l'affectation de `_socket`, celui-ci vaut `None` et `.close()` lève `AttributeError`. Il faut un `try/finally` par étape et `remove(force=True)`.
3. **`_build_executor_archive()` embarque `__pycache__`.** `tar.add()` sur un répertoire récurse sans filtre. Il y a déjà des `__pycache__` dans `student/sandbox/` ; dès que `executor/` en aura, des `.pyc` potentiellement périmés seront injectés dans le conteneur, où ils primeront sur les `.py` si les timestamps s'alignent mal. Le paramètre `filter=` de `tar.add()` existe pour ça.
4. **`_stderr_buffer` est rempli mais jamais lu.** Les tracebacks du conteneur sont désormais capturées, mais rien ne les remonte à l'utilisateur ni à la boucle agent. En l'état, un crash de `runner.py` se manifeste par un `ConnectionError` opaque alors que la cause exacte est disponible dans le buffer — exactement le « silent failure » que §V.1.3 interdit.

---

## `repl.py`

### ✅ Bon

1. **Les deux conditions de sortie du sujet sont là** — `exit` et EOF (Ctrl+D), littéralement « It exits cleanly on the exit command or on EOF (Ctrl+D) ».
2. **`EOFError` capturée plutôt que laissée remonter** — sans ce `try`, Ctrl+D produirait une traceback. C'est la différence entre « exits cleanly » et « crashe à la fermeture ».
3. **`.strip()` sur le test de sortie** — `"exit "` avec un espace parasite fonctionne. Détail, mais c'est le genre de chose qu'un correcteur teste au clavier en 2 secondes.
4. **`container` reçu en paramètre, pas construit ici** — le REPL ne possède pas le cycle de vie, donc il ne peut pas fuiter un conteneur ni empêcher `cli.py` de le nettoyer. Séparation correcte.
5. **Ignore totalement Docker, les sockets et le format de trame** — ne connaît que `send`/`receive`. Si le mécanisme d'isolation change (process au lieu de conteneur), ce fichier ne bouge pas.

### ❌ Mauvais

1. **`KeyboardInterrupt` non gérée → traceback à l'écran.** Ctrl+C pendant `input()` lève, traverse `run()`, traverse le `with` (qui nettoie correctement, ça c'est bon), puis s'affiche en traceback brute. Le sujet exige que `KeyboardInterrupt` **atteigne la boucle agent** (§V.2.2) — ce n'est pas la même chose que de la laisser produire un crash visible dans un REPL interactif, où §IV.1 demande une terminaison gracieuse. Comportement REPL attendu : Ctrl+C annule la ligne en cours et redonne le prompt, Ctrl+D quitte. Actuellement les deux quittent, l'un salement.
2. **Une seule ligne à la fois.** `input()` lit une ligne. Impossible de saisir `def f():` suivi d'un corps indenté, ou un `for`, ou un `try`. Le sujet dit « read user-typed code in a loop » — du code Python multi-ligne est le cas normal, pas le cas limite. Il faut une logique de continuation (prompt secondaire tant que le bloc est incomplet).
3. **`print(response)` affiche le dict brut** — l'utilisateur verra `{'type': 'result', 'stdout': '4\n'}` au lieu de `4`. Le sujet demande « it prints the result or any raised error » : résultat et erreur doivent être **distingués** visuellement, ce que l'affichage d'un dict ne fait pas.
4. **`ConnectionError` de `receive()` non capturée** — c'est l'exception introduite dans `container.py` pour le cas « le conteneur a fermé la connexion ». Elle remonte ici en traceback. Vu le préambule (le conteneur meurt immédiatement aujourd'hui), c'est le chemin qui sera rencontré au tout premier test.
5. **Le cas `final_answer` n'est pas traité.** Le sujet exige que le REPL ait « the connected MCP tool wrappers and final_answer available ». Si l'utilisateur tape `final_answer("x")`, le message de retour aura un type différent de `result` — et rien ici ne le reconnaît. L'implémentation est côté exécuteur, mais l'affichage est côté REPL.

---

## `Dockerfile`

### ✅ Bon

1. **`python:3.10-slim`** — respecte « You must use Python 3.10 » (§IV.1) au niveau de l'environnement d'exécution du code non fiable, pas seulement du projet.
2. **`USER sandbox` (uid 1000, non-root)** — si `restrictions.py` était contourné, le code s'exécuterait quand même sans droits root **dans** le conteneur. Défense en profondeur, cumulée avec `cap_drop=ALL`.
3. **`/workspace` créé puis `chown` à l'utilisateur sandbox** — le `WORKDIR` crée le répertoire en root ; sans le `chown` explicite, l'utilisateur non-root ne pourrait rien y écrire, et `allowed_directories: ["/workspace"]` serait un répertoire en lecture seule.
4. **Aucun `apt-get`, aucun `pip install`** — l'allowlist ne contenant que de la stdlib, il n'y a rien à installer. Surface d'attaque minimale, image légère, build rapide.
5. **Aucun `CMD`/`ENTRYPOINT`** — cohérent avec `container.py` qui passe toujours `command=` explicitement. Un défaut ici serait du code mort, ou pire, une divergence silencieuse entre l'image MBPP et les images SWE-bench.

### ❌ Mauvais

1. **`/workspace` n'est pas le seul répertoire inscriptible.** L'utilisateur `sandbox` peut écrire dans `/tmp`, `/home/sandbox`, `/dev/shm`. Aucun n'est dans `allowed_directories`. La restriction filesystem n'est donc **pas** appliquée par Docker et repose entièrement sur `restrictions.py` — qui n'existe pas encore. Aujourd'hui, le champ `allowed_directories` est purement décoratif. `read_only=True` + `tmpfs` sur `/workspace` côté `create()` rendrait la contrainte réelle.
2. **Base non épinglée** — `python:3.10-slim` est un tag mutable. Un rebuild dans trois mois donnera une image différente. §III insiste sur la reproductibilité ; épingler par digest (`python:3.10-slim@sha256:...`) coûte une ligne.
3. **Pas de `.dockerignore`** — combiné au contexte de build = tout `sandbox/` (point 3 de `cli.py`), chaque `docker build` transfère les sources Python et les `__pycache__`.
4. **Les fichiers injectés par tar portent l'uid de l'hôte, pas 1000.** `tar.add()` préserve le propriétaire de la machine hôte. `/sandbox_executor/*` appartiendra donc à un uid arbitraire. Fonctionne tant que les permissions sont en lecture pour tous (cas usuel, 644), mais c'est une dépendance implicite au `umask` de la machine de développement.
5. **`pids_limit` absent côté `create()`** — rien n'empêche une fork bomb depuis le code exécuté.

---

## Récapitulatif de conformité §V.2

| Exigence | État |
|---|---|
| CLI `uv run sandbox` (4 formes) | 🟡 Parse tout, n'utilise que 2 formes sur 4 |
| REPL interactif | 🟡 Boucle + sorties OK, mono-ligne, affichage brut |
| `final_answer` injecté | ❌ Absent |
| `KeyboardInterrupt`/`SystemExit` propagées | ✅ Structurellement garanti par `__exit__` |
| Restriction imports | ❌ Stub |
| Restriction filesystem | ❌ Stub — champ config non appliqué |
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
3. **Implémenter `restrictions.py`** — c'est là que se jouent 3 des 6 contraintes de sécurité, et `exam_sandbox.sh` exige **100 %** de réussite (§VI.2)
4. **Réaligner les défauts de `config.py`** (`/testbed`, retrait de `pathlib`, wildcards)
5. **Robustesse** : timeout sur `receive()`, `try/finally` dans `stop()`, exploitation de `_stderr_buffer`, gestion d'erreurs dans `cli.py` (§IV.1)

---

## Corrigés depuis l'audit initial

| Point | Fichier | Correctif appliqué | Date |
|---|---|---|---|
| `tty=True` cassait le protocole (écho TTY renvoyant nos propres messages) | `container.py` | `tty=False` + démultiplexage des frames Docker (`_recv_exactly`, `_read_frame`), stderr capturé séparément | 2026-08-13 |
| Convention d'import de `executor/` non tranchée | `executor/__init__.py` | Imports plats absolus (`import protocol`), lancement en script simple depuis `/sandbox_executor` ; décision et conséquences documentées dans le docstring du package | 2026-08-13 |

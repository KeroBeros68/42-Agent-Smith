# Audit — Partie Sandbox

> Audit de conformité de la partie sandbox réalisée à ce jour, par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-13
> **Dernière mise à jour** : 2026-08-20 — points corrigés retirés (voir « Corrigés depuis l'audit initial » en fin de document)
> **Périmètre** : `student/sandbox/` (fichiers implémentés uniquement) + `sandbox_template.json`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier, chacun justifié par référence au sujet ou par le comportement réel du code.

---

## ✅ Mise à jour : le round-trip complet fonctionne, relais `tool_call` inclus

Le sandbox est maintenant fonctionnel de bout en bout, sécurité comprise : `exec`/`result`/`error`/`final_answer`, restrictions d'imports, builtins restreints, timeout par exécution, **et** le relais `tool_call` conteneur ↔ `MCPBridge` ↔ vrai serveur MCP. Tout a été vérifié en conditions Docker réelles, pas seulement en théorie — y compris 3 bugs non triviaux trouvés uniquement grâce à ces tests (mapping des arguments positionnels d'un tool, timeout local qui comptait à tort le temps d'attente réseau, et un `redirect_stdout` qui avalait silencieusement le message protocole du stub — voir « Corrigés » en fin de document pour le détail de chacun).

**Mise à jour du 2026-08-26** : le transport MCP HTTP est désormais testé en réel lui aussi (`MCPBridge` et la CLI `--mcp-server`, voir la section `mcp_bridge.py` plus bas) — les deux transports sont couverts. Ce qui reste : quelques points mineurs listés par fichier ci-dessous.

---

## `cli.py`

### ✅ Bon

1. **Les 4 formes CLI du §V.2.1 sont couvertes syntaxiquement** — positionnel optionnel + deux flags. `uv run sandbox`, `uv run sandbox config.json`, `--mcp-stdio "..."`, `--mcp-server URL` parsent tous correctement.
2. **`mutually_exclusive_group`** — argparse refuse automatiquement les deux transports MCP simultanés, avec un message d'erreur généré. Deux serveurs MCP connectés n'ont pas de sens dans le modèle du sujet (un sandbox = un serveur connecté).
3. **`load_config` isolée de `main()`** — testable sans lancer Docker, et le fallback `SandboxConfig()` quand aucun fichier n'est donné correspond au cas `uv run sandbox` nu.
4. **`SandboxConfig(**data)` plutôt qu'un parsing manuel** — délègue la validation à Pydantic, donc un champ manquant prend son défaut et un champ de mauvais type est rejeté sans code de vérification maison.
5. **`with container as c`** — garantit `stop()` sur tous les chemins de sortie, y compris exception. C'est ce qui rend la contrainte §VII (nettoyage des conteneurs à votre charge) structurellement respectée plutôt que dépendante d'un `try/finally` oublié quelque part.

### ❌ Mauvais

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

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

**Depuis le 2026-08-26** : `TMPFS_OPTIONS` a changé deux fois en implémentant l'accès `docker exec` de `mcp_tools_swebench.py` au conteneur sandbox (voir `AUDIT_SWEBENCH_TOOLS.md`) — taille `64m → 4096m` (64 Mo était dimensionné pour MBPP, un vrai dépôt SWE-bench comme Django fait déjà 161 Mo, `No space left on device` vérifié avant le fix) et ajout de `exec` explicite. Ce second point est un bug Docker non documenté trouvé par test, pas supposé : un tmpfs monté sans `noexec` dans la chaîne d'options est **quand même** monté `noexec` par défaut — `mount | grep workspace` le confirmait encore après simple retrait de `noexec`. Seul `exec` explicite dans les options lève réellement la restriction. Les deux changements n'affaiblissent pas la sécurité de MBPP : `noexec` était une couche de défense en profondeur par-dessus les restrictions Python déjà comprehensives (`restrictions.py` bloque déjà `subprocess`/`os.system`/imports dangereux), pas la seule barrière.

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

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

---

## `executor/restrictions.py`

### ✅ Bon

1. **Hook `sys.meta_path` plutôt que du pattern-matching sur le texte du code.** Un `MetaPathFinder` intercepte *tout* mécanisme d'import (`import X`, `from X import Y`, `__import__("X")`, `importlib.import_module("X")`) au niveau de l'interpréteur — contourne les techniques de bypass triviales qu'une simple recherche de sous-chaîne (`"os" in code`) laisserait passer (alias, imports dynamiques, espaces superflus).
2. **Purge de `sys.modules["os"]` ciblée et vérifiée empiriquement**, pas un balayage aveugle de tout `sys.modules`. Testé avant d'écrire le code : `os` est le seul module dangereux réellement pré-chargé au démarrage de l'interpréteur (avant même l'exécution de `runner.py`) — un `meta_path` seul ne l'aurait jamais intercepté puisque Python consulte `sys.modules` avant `sys.meta_path`.
3. **Pré-import de tous les modules autorisés avant d'activer la restriction.** Corrige un problème réel découvert par test : `random` (a besoin de `os.urandom` en interne), `json` (sous-modules `.decoder`/`.encoder`), `string` (`_string`), `copy` (`weakref`) échouaient tous à l'import sans ce mécanisme — résolu une fois pour toutes plutôt qu'au cas par cas avec des wildcards manuels.
4. **`find_spec` lève `ImportError` explicitement pour un import refusé**, au lieu de `return None` — un refus net immédiatement, pas une recherche qui continue silencieusement ailleurs dans les autres finders.
5. **Testé contre de vraies tentatives de contournement** (`__import__`, `importlib.import_module`, `from X import Y`, traversée de chemin `../`, collision de préfixe `/workspace-evil`) et vérifié fonctionnellement, pas juste syntaxiquement (`random.randint()` appelé en vrai, écriture/lecture réelles dans `/workspace`). Vérifié **en conditions réelles dans un vrai conteneur Docker** : `os`/`subprocess` bloqués, `math`/`random` utilisables normalement, `eval`/`exec`/`input` bloqués, `open` **restreint** à `allowed_directories` (pas banni — sinon ce champ de `SandboxConfig` n'aurait plus de sens) via `os.path.realpath()` pour résister aux `..` et aux symlinks, classe+méthode/`try-except`/comprehension toujours fonctionnels.

### ❌ Mauvais

1. **Limite documentée, pas fermée : l'introspection objet contourne l'allowlist des builtins.** `().__class__.__bases__[0].__subclasses__()` et variantes permettent d'atteindre des classes déjà chargées en mémoire (potentiellement une référence à `os`/`subprocess` détenue par un autre module) sans jamais appeler `import` ni aucun nom retiré de `SAFE_BUILTINS`. Fermer ça demanderait une vraie sandbox AST — explicitement interdite par le sujet (pas de `RestrictedPython`). Docker (réseau none, filesystem read-only, capabilities droppées) reste la vraie frontière de sécurité ; ce fichier est une couche de défense en profondeur par-dessus, pas la seule ligne de défense.
2. **`PRELOADED_DANGEROUS_MODULES = ("os",)` est une liste figée**, basée sur une vérification empirique faite sur cette machine/cette image de base précise. Si l'image Docker change (autre variante `python:3.10-slim`, autre OS de base), un autre module dangereux pourrait se retrouver pré-chargé sans qu'on l'ait revérifié.

---

## `executor/watchdog.py`

### ✅ Bon

1. **`signal.alarm()` plutôt qu'un thread ou un décorateur** — les deux approches naïvement envisagées ne marchent pas en Python : un thread ne peut pas être tué de force depuis l'extérieur (pas de `thread.kill()`), et un décorateur qui ne mesure le temps qu'après coup ne peut pas interrompre une boucle infinie en cours. `signal.alarm()` fonctionne parce que Python vérifie les signaux en attente entre chaque instruction bytecode — une vraie boucle `while True: pass` est interrompue.
2. **`ExecutionTimeout(TimeoutError)`** — hérite de `TimeoutError`, donc de `Exception`, pas de `BaseException`. Capturée automatiquement par le `except Exception` déjà présent dans `_handle_exec`, sans rien changer côté `runner.py` au-delà du branchement du context manager.
3. **`signal.alarm(0)` + restauration du handler précédent dans un `finally`** — le minuteur est désarmé et le handler restauré même si `exec()` lève une autre exception que le timeout, pas seulement dans le cas nominal.
4. **Testé en conditions réelles contre un vrai `while True: pass`** — coupé après le délai configuré (~3.4s pour une limite à 3s), pas juste testé en théorie contre du code qui se termine tout seul.
5. **`pause()`/`resume()` autour d'un `tool_call`** — le sujet est explicite : le timeout du sandbox ne s'applique qu'au code exécuté localement, pas aux actions du serveur MCP. Bug réel trouvé par test (pas en le lisant) : sans ça, un aller-retour `tool_call` comptait contre le budget d'exécution local et déclenchait un faux timeout. Testé avec une limite de **1 seconde** : l'aller-retour (qui prend certainement plus d'1s en horloge murale) passe sans se faire couper, confirmant que la pause fonctionne réellement.

### ❌ Mauvais

1. **`MAX_EXECUTION_TIME_SECONDS` lu une seule fois au chargement du module `runner.py`**, pas par message — si `SandboxConfig` changeait en cours de session (cas non prévu aujourd'hui, une session = un conteneur = une config fixe), la nouvelle valeur ne serait jamais prise en compte. Cohérent avec l'architecture actuelle, mais implicite.
2. **Pas de garde contre un appel imbriqué** — si `enforce()` était appelé une seconde fois avant que le premier `signal.alarm(0)` n'ait eu lieu (ne devrait pas arriver dans le flux actuel, mono-thread et séquentiel), le second appel écraserait le minuteur du premier sans avertissement.

---

## `mcp_bridge.py`

### ✅ Bon

1. **Facade synchrone sur `fastmcp.Client` (async)** — thread dédié + event loop persistante, `_run()` comme seul point de passage sync→async. Évite de réécrire tout le reste du sandbox (synchrone, sockets bloquants) en async pour brancher un seul client.
2. **La connexion MCP reste ouverte pour toute la session**, pas rouverte à chaque appel — le sous-processus du serveur MCP (`stdio`) n'est lancé qu'une fois.
3. **`call_tool()` testé en conditions réelles**, pas juste `list_tools()` — appel positionnel réel à `run_tests()` relayé jusqu'au vrai serveur MCP et retour, y compris le cas d'erreur légitime du serveur (tâche non chargée), correctement propagé plutôt que masqué. `is_connected()` utilisé pour distinguer cette erreur légitime d'une vraie déconnexion — testé les deux cas dans le même run pour confirmer qu'aucun n'est mal étiqueté.
4. **`__enter__`/`__exit__` sans capture d'exception**, même pattern que `SandboxContainer` — cohérence de style, et garantit la fermeture même en cas d'exception pendant la session.
5. **`shlex.split()` plutôt qu'un `.split()` naïf** pour découper `--mcp-stdio` — gère correctement une commande avec des arguments contenant des espaces entre guillemets.

**Depuis le 2026-08-20** : `StdioTransport` reçoit maintenant `env={**os.environ, "MCP_TRANSPORT": "stdio"}`. Bug trouvé en lisant le SDK MCP, pas en le supposant : `env=None` (le défaut précédent) ne fait **pas** hériter tout l'environnement parent — le SDK filtre sur une allowlist stricte (`mcp.client.stdio.DEFAULT_INHERITED_ENV_VARS = ['HOME', 'LOGNAME', 'PATH', 'SHELL', 'TERM', 'USER']`), donc `MCP_TRANSPORT` (exigé par `mcp_tools_mbpp.py`/`mcp_tools_swebench.py` depuis leur mise à jour, sinon `TypeError` immédiate) n'atteignait jamais le sous-processus. Vérifié réellement : `MCPBridge(stdio_command="python3 mcp_tools_mbpp.py").connect()` échouait avant le fix, réussit après (`list_tools()` retourne bien `['run_tests']`).

**Depuis le 2026-08-26** : `call_tool()` retourne maintenant `result.data` plutôt que l'objet `CallToolResult` complet (repli sur l'objet brut si `.data is None`). Bug trouvé en conditions réelles, pas en relisant le code : lors du 3e test d'intégration `agent_core` (vrai LLM + vrai conteneur), `relay_tool_calls` faisait `str(result)` sur l'objet complet avant de l'envoyer au conteneur — le LLM recevait `"CallToolResult(content=[...], structured_content={...}, data='All test passed successfully !', ...)"` comme observation au lieu du texte propre. Le LLM s'en est sorti quand même cette fois, mais c'était du bruit et un risque de confusion pour un modèle moins capable. Revérifié après fix : `sandbox_output` de l'appel `run_tests` est maintenant exactement `"All test passed successfully !"`.

**Transport HTTP testé réellement le 2026-08-26** — jusqu'ici seul `stdio` avait été vérifié en conditions réelles (❌ Mauvais #1, ci-dessous, maintenant clos). `mcp_tools_mbpp.py` lancé en vrai serveur HTTP (`MCP_TRANSPORT=http`, écoute réelle sur `http://127.0.0.1:8000/mcp`, confirmé par le log de démarrage FastMCP) : `MCPBridge(server_url=...).connect()` + `list_tools()` + `call_tool("run_tests", ...)` fonctionnent de bout en bout (résultat propre grâce au fix `.data` ci-dessus). Testé aussi via la vraie CLI, pas seulement `MCPBridge` isolé : `uv run sandbox --mcp-server http://127.0.0.1:8000/mcp` avec du code réel (`run_tests(...)`) envoyé au conteneur Docker — relais `tool_call`→HTTP→conteneur→LLM fonctionnel, `"All test passed successfully !"` retourné correctement. Les 4 formes de la CLI (§V.2.1) sont donc maintenant **toutes** vérifiées en conditions réelles, pas seulement `--mcp-stdio`.

### ❌ Mauvais

Aucun point ouvert — le seul point restant (transport HTTP jamais testé en conditions réelles) est clos depuis le 2026-08-26, voir ci-dessus.

---

## `sandbox/session.py`

### ✅ Bon

1. **Extrait pour éviter une duplication anticipée** — la séquence "découvrir les tools → construire le conteneur avec les bons noms" n'est pas spécifique au REPL ; `agent_core` devra faire exactement la même chose. Factoriser maintenant évite de la dupliquer plus tard.
2. **Frontière nette avec `cli.py`** : `session.py` sait *comment* câbler correctement un conteneur à partir d'un bridge déjà connecté ; `cli.py` décide *quand* se connecter/déconnecter (spécifique à chaque appelant — REPL vs future boucle agent).
3. **Extrait `inputSchema.properties`** (un dict, donc l'ordre des clés = ordre de déclaration) pour transmettre au conteneur non seulement les noms des tools mais aussi l'ordre de leurs paramètres — nécessaire pour que `runner.py` mappe correctement un appel positionnel (`run_tests("...")`) au bon nom de paramètre.
4. **`mcp_bridge is None` géré explicitement** — `tools = {}` si aucun serveur n'est connecté, pas de branche spéciale nécessaire en aval dans `container.py`/`runner.py`.
5. **Testé de bout en bout en conditions Docker réelles**, pas seulement à la lecture — le mapping nom→paramètres produit ici est exactement ce qui a permis à `run_tests("...")` de fonctionner en positionnel côté sandbox.

**Depuis le 2026-08-20** : `relay_tool_calls(container, mcp_bridge)` a été déplacée ici depuis `repl.py` (où elle s'appelait `_relay_tool_calls`, privée) — mêmes raisons que `build_container` : le nouveau `agent_core/sandbox_client.py` a besoin exactement de la même boucle de relais que le REPL, donc factoriser évite la duplication plutôt que de la découvrir après coup. Comportement inchangé, seule la portée (`_`-prefixed → publique) et l'emplacement changent.

### ❌ Mauvais

1. **Suppose que tous les tools ont un `inputSchema` de type `object` avec `properties`** — un tool MCP avec un schéma différent (type non-objet, `$ref`, schéma composé) ferait échouer silencieusement l'extraction (`properties` vide), pas testé contre un tel cas puisque `mcp_tools_mbpp.py` n'expose qu'un tool simple.

---

## `repl.py`

### ✅ Bon

1. **Les deux conditions de sortie du sujet sont là** — `exit` et EOF (Ctrl+D), littéralement « It exits cleanly on the exit command or on EOF (Ctrl+D) ».
2. **`EOFError` capturée plutôt que laissée remonter** — sans ce `try`, Ctrl+D produirait une traceback. C'est la différence entre « exits cleanly » et « crashe à la fermeture ».
3. **`.strip()` sur le test de sortie** — `"exit "` avec un espace parasite fonctionne. Détail, mais c'est le genre de chose qu'un correcteur teste au clavier en 2 secondes.
4. **`container` et `mcp_bridge` reçus en paramètres, pas construits ici** — le REPL ne possède aucun cycle de vie, donc il ne peut fuiter ni l'un ni l'autre, et ne peut empêcher `cli.py` de les nettoyer. Séparation correcte, y compris pour la nouvelle boucle de relais.
5. **`relay_tool_calls` (désormais dans `session.py`, importée ici) gère le cas `mcp_bridge is None`** (aucun serveur MCP connecté) sans planter — renvoie un `tool_result` d'erreur explicite au conteneur plutôt que de lever une exception côté host. Testé de bout en bout en conditions Docker réelles contre le vrai `mcp_tools_mbpp.py` : `run_tests()` appelé en positionnel depuis le code sandboxé, résultat relayé correctement jusqu'au bout.

### ❌ Mauvais

Aucun point ouvert pour l'instant — voir « Corrigés depuis l'audit initial » pour l'historique.

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
| CLI `uv run sandbox` (4 formes) | ✅ Les 4 formes fonctionnent, testé de bout en bout — `--mcp-stdio` **et** `--mcp-server` contre le vrai `mcp_tools_mbpp.py` (mise à jour 2026-08-26) |
| REPL interactif | ✅ Boucle, sorties, multi-ligne, Ctrl+C, relais `tool_call` et affichage distinct résultat/erreur/`final_answer` |
| `final_answer` injecté | ✅ Testé imbriqué dans une fonction/boucle, propagation par exception vérifiée à plusieurs niveaux d'appel |
| `KeyboardInterrupt`/`SystemExit` propagées | ✅ Structurellement garanti par `__exit__` |
| Restriction imports | ✅ Branché et vérifié en conditions réelles (Docker) |
| Restriction filesystem | ✅ Docker (read-only + tmpfs) + `open` restreint par `allowed_directories` au niveau Python, testé contre `../` et collision de préfixe |
| Pas de réseau | ✅ `network_mode="none"` |
| Timeout d'exécution | ✅ `signal.alarm()`, testé en conditions réelles contre une vraie boucle infinie |
| Limite mémoire | ✅ `mem_limit` |
| Builtins restreints | ✅ Allowlist testée en conditions réelles ; limite connue documentée (introspection `__subclasses__`, non fermable en stdlib pur) |
| Intégration MCP (stdio + HTTP) | ✅ Relais `tool_call` complet, vérifié en conditions Docker réelles pour **les deux transports** (mise à jour 2026-08-26) |
| Manuel dynamique | ✅ `agent_core/manual.py` (`build_manual`), généré depuis `tool.inputSchema` réel, testé contre `mcp_tools_mbpp.py` et utilisé dans un run `agent_mbpp` complet (mise à jour 2026-08-26, voir `AUDIT_AGENT_CORE.md`) |
| Config Pydantic + JSON | ✅ Fait, défauts à réaligner |

---

## Priorités recommandées

Par ordre d'impact sur la note :

Les 6 contraintes de sécurité §V.2.3, le relais `tool_call`/`final_answer`, et les deux transports MCP (stdio + HTTP) sont maintenant couverts et vérifiés en conditions réelles Docker. **Aucune priorité ouverte propre à `student/sandbox/` au 2026-08-26** — le module est fonctionnellement complet et testé de bout en bout sur toute sa surface documentée ici. Les priorités restantes du projet sont ailleurs : voir `AUDIT_AGENT_CORE.md` (limites cumulées, formats de parsing b/c/d) et `AUDIT_SWEBENCH_TOOLS.md` (accès `/testbed` — bloquant pour SWE-bench, sans rapport avec `sandbox/` lui-même).

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
| Aucun timeout par exécution — un `exec` qui boucle à l'infini bloquait `runner.py` indéfiniment | `executor/watchdog.py` (nouveau) | `signal.alarm()` + handler `SIGALRM` levant `ExecutionTimeout(TimeoutError)`, capturée automatiquement par le `except Exception` déjà existant. Deux approches naïves écartées et expliquées (thread — impossible à tuer de force en Python ; décorateur post-hoc — ne peut pas interrompre une boucle en cours). Testé en conditions réelles contre un vrai `while True: pass` : coupé après le délai configuré, session vérifiée survivante ensuite | 2026-08-18 |
| Aucune restriction des builtins — `open`/`eval`/`exec`/`input` accessibles tels quels dans le namespace d'exécution | `executor/restrictions.py` | `SAFE_BUILTINS` (allowlist) + `restricted_builtins()`, posé dans `NAMESPACE["__builtins__"]` avant la boucle. `__import__`/`__build_class__` gardés (nécessaires aux instructions `import`/`class`), `eval`/`exec`/`compile`/`input`/`breakpoint`/`help` exclus (`open` traité séparément, voir ligne suivante). Limite connue documentée dans le fichier plutôt que cachée : l'introspection objet (`__subclasses__`) contourne toujours l'allowlist, fermable seulement par une sandbox AST interdite par le sujet — Docker reste la vraie frontière. Testé en conditions réelles Docker : 4 builtins dangereux bloqués, classe+méthode/try-except/comprehension/import autorisé toujours fonctionnels | 2026-08-18 |
| `allowed_directories` n'était appliqué nulle part côté Python — soit `open` totalement banni (rend le champ inutile), soit non restreint du tout | `executor/restrictions.py` | `open` **remplacé**, pas supprimé : `_make_restricted_open()` vérifie `os.path.realpath(file)` contre les racines autorisées (`target == root or target.startswith(root + os.sep)`, pour éviter qu'une collision de préfixe comme `/workspace-evil` passe). Bug réel trouvé par mypy avant même le test Docker : `os.path.realpath()` d'un chemin `bytes` retourne du `bytes`, comparé à tort à des racines `str` (`TypeError` à l'exécution) — corrigé avec `os.fsdecode()`. Testé en conditions réelles Docker : lecture/écriture OK dans `/workspace`, refusées hors de ce répertoire, y compris via `../` et le chemin en `bytes` (plus de crash) | 2026-08-18 |
| `final_answer` absent — aucun moyen pour le code sandboxé de signaler la fin de tâche | `executor/runner.py` | `_FinalAnswerSignal(Exception)` levée par `final_answer(answer)`, capturée séparément de `except Exception` dans `_handle_exec` pour produire un `FinalAnswerMessage` plutôt qu'une erreur. Injecté comme global (pas un builtin — spécifique au sandbox, pas du Python standard). Testé en conditions réelles Docker, y compris **imbriqué dans une fonction appelée depuis une boucle** — confirme que l'exception remonte correctement à travers plusieurs niveaux d'appel | 2026-08-18 |
| Aucun relais `tool_call` conteneur↔`MCPBridge` — les tools MCP découverts côté host n'étaient jamais utilisables depuis le code sandboxé | `sandbox/session.py` (nouveau), `container.py`, `executor/runner.py`, `executor/watchdog.py`, `repl.py`, `cli.py` | `session.build_container()` (nouveau, réutilisable par la future boucle agent) extrait `{nom: [params]}` de `inputSchema` et le transmet au conteneur via `MCP_TOOLS_JSON`. `runner.py` crée un stub par tool, qui écrit/lit directement sur stdout/stdin (pas via `main()`, déjà bloqué plus haut dans la pile). `repl.py` boucle sur `container.receive()` : relaie tout `tool_call` à `mcp_bridge.call_tool()`, renvoie le `tool_result`, jusqu'à obtenir la vraie réponse finale. **3 bugs réels trouvés uniquement par les tests Docker, pas en les relisant** : (1) le stub n'acceptait que `**kwargs` alors que `run_tests("...")` s'appelle en positionnel — corrigé en mappant les positions aux noms de paramètres via `inputSchema` ; (2) le timeout d'exécution local comptait à tort le temps d'attente du `tool_call` — corrigé avec `watchdog.pause()`/`resume()` (§V.2 : les actions du serveur MCP ne sont pas soumises au timeout du sandbox) ; (3) le plus sournois — `redirect_stdout(buffer)` (qui capture le `print()` de l'utilisateur) capturait aussi le message protocole du stub, provoquant un double blocage silencieux (host et conteneur attendant chacun une donnée qui n'arriverait jamais) — corrigé avec `REAL_STDOUT`, une référence capturée avant toute redirection. Testé de bout en bout avec une limite d'exécution de 1 seconde pour confirmer que la pause du watchdog fonctionne vraiment, pas juste "assez rapide pour ne pas se voir" | 2026-08-20 |
| `print(response)` affichait le dict brut — pas de distinction visuelle résultat/erreur/`final_answer` | `repl.py` | `_format_response()` : `result` → juste le `stdout` capturé ; `error` → la traceback complète (répond littéralement au « it prints ... any raised error » du sujet) ; `final_answer` → préfixé explicitement ; fallback `repr()` pour un type inattendu (pas d'échec silencieux). `end=""` sur le `print()` pour ne pas doubler les retours à la ligne déjà présents dans `stdout`/`traceback`. Testé en conditions réelles Docker : sortie normale, statement silencieux, `ZeroDivisionError` avec traceback lisible, `final_answer` bien distingué | 2026-08-20 |
| Docstring décrivait une capacité absente (« a single task run ») | `cli.py` | Corrigé pour décrire le comportement réel : toujours interactif, sans argument de tâche — la distinction avec les futurs agents (`agent_mbpp`/`agent_swebench`, non-interactifs) est explicitée | 2026-08-20 |
| Aucune détection d'un serveur MCP mort en cours de session — `call_tool()` aurait levé une exception `fastmcp` brute | `mcp_bridge.py` | `is_connected()` (méthode synchrone de `fastmcp.Client`) vérifiée après une exception dans `call_tool()` : si déconnecté, relève un `ConnectionError` clair ; sinon, l'exception d'origine (ex: `ToolError` légitime) remonte inchangée. **Bug distinct trouvé en testant ce fix** : appeler `_run()` après `close()` bloquait indéfiniment (boucle asyncio arrêtée + thread joint, `run_coroutine_threadsafe` programme un callback qui ne s'exécute jamais) — corrigé par un check `self._loop.is_running()` avant soumission, échec immédiat avec un message clair. Testé en conditions réelles : erreur légitime préservée, déconnexion après `close()` détectée sans blocage | 2026-08-20 |
| `_relay_tool_calls` dupliquée à l'identique entre le REPL et le futur `agent_core/sandbox_client.py` (qui vient d'être écrit) — deux copies de la même boucle de relais `tool_call` à maintenir en synchro | `sandbox/session.py` (fonction déplacée depuis `repl.py`, rendue publique : `relay_tool_calls`), `repl.py` (import + appel mis à jour) | Comportement inchangé, simple déplacement + renommage. `agent_core/sandbox_client.py` (nouveau) importe la même fonction plutôt que d'en écrire une copie. Vérifié : `mypy sandbox agent_core` (0 erreur, executor vérifié séparément) et `flake8` sur les 3 fichiers touchés (0 warning) | 2026-08-20 |
| `MCP_TRANSPORT` (exigé par `mcp_tools_mbpp.py`/`mcp_tools_swebench.py`) n'atteignait jamais le sous-processus stdio — `StdioTransport` sans `env=` explicite ne fait hériter que 6 variables (`HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER`), confirmé en lisant le SDK MCP. Bloquait *toute* connexion stdio réelle vers ces deux serveurs (`TypeError` au démarrage du sous-processus) | `mcp_bridge.py` | `env={**os.environ, "MCP_TRANSPORT": "stdio"}` passé explicitement à `StdioTransport`. Vérifié en conditions réelles : `MCPBridge(stdio_command="python3 mcp_tools_mbpp.py").connect()` échouait avant, réussit après (`list_tools()` → `['run_tests']`) | 2026-08-20 |
| `call_tool()` retournait l'objet `CallToolResult` complet — une fois `str()`-ifié par `relay_tool_calls` pour l'envoyer au conteneur, le LLM recevait le repr Python entier (`"CallToolResult(content=[...], data='...', ...)"`) comme observation au lieu du texte du tool | `mcp_bridge.py` | `return result.data if result.data is not None else result` — extrait le résultat parsé, repli sur l'objet brut si `.data` est `None` (tool sans donnée structurée). Trouvé via un vrai run `agent_core` (LLM + Docker), pas en relisant le code : l'observation de `run_tests` contenait le repr brut avant le fix. Revérifié après : `sandbox_output` devient exactement `"All test passed successfully !"` | 2026-08-26 |
| Transport HTTP de `MCPBridge` (`server_url`) jamais testé en conditions réelles — seul `stdio` l'avait été | *(aucun changement de code)* | Testé réellement : `mcp_tools_mbpp.py` lancé en vrai serveur HTTP (`MCP_TRANSPORT=http`, `http://127.0.0.1:8000/mcp`), `MCPBridge(server_url=...)` (`connect`/`list_tools`/`call_tool`) et la CLI complète (`uv run sandbox --mcp-server http://127.0.0.1:8000/mcp` avec du vrai code exécuté dans un vrai conteneur Docker) fonctionnent de bout en bout. Les 4 formes de la CLI (§V.2.1) sont désormais toutes vérifiées en conditions réelles | 2026-08-26 |
| Tmpfs `/workspace`/`/tmp` limité à 64 Mo — trop petit pour la copie writable d'un vrai dépôt SWE-bench (`No space left on device`, Django = 161 Mo) | `container.py` (`TMPFS_OPTIONS`) | Taille portée à 4 Go. Contexte : nécessaire pour `mcp_tools_swebench.py` (voir `AUDIT_SWEBENCH_TOOLS.md`), sans coût réel pour MBPP (tmpfs ne consomme que ce qui y est écrit) | 2026-08-26 |
| Docker monte tmpfs `noexec` par défaut même sans le spécifier explicitement — bloquait l'exécution directe de scripts depuis `/workspace` (`./tests/runtests.py` de SWE-bench) | `container.py` (`TMPFS_OPTIONS`) | `exec` ajouté explicitement aux options de montage. Bug Docker non documenté trouvé par test : `mount \| grep workspace` montrait encore `noexec` après simple retrait de `noexec` de la chaîne — il faut le lister explicitement en plus. Ne rouvre pas de trou de sécurité pour MBPP : `noexec` était une couche de défense en profondeur au-dessus des restrictions Python déjà comprehensives (`restrictions.py`), pas la seule barrière | 2026-08-26 |
| `mcp_bridge.py` injectait `MCP_TIMEOUT_DELAY: "60"` en dur au spawn stdio (ajouté par Gaspard le 2026-08-28 pour fiabiliser le démarrage des deux serveurs MCP, voir `mcp_tools_mbpp.py`/`mcp_tools_swebench.py`) — appliqué **indistinctement** à MBPP et SWE-bench, alors que leurs budgets diffèrent fortement (§VI.1.1/1.2 : 60s total pour MBPP, 900s pour SWE-bench). Un `eval_script` SWE-bench réel (pip install, suite de tests complète) peut dépasser 60s et tronquer `run_tests()` prématurément — non détecté sur nos runs réels (tâche légère, `run_tests()` ~20-30s), mais un vrai risque pour des tâches plus lourdes | `mcp_bridge.py` (`MCPBridge.__init__`/`_build_transport` acceptent désormais `mcp_timeout_delay_sec: int`, défaut 60 conservé pour tout appelant qui ne spécifie rien), `agent_mbpp/__main__.py` (passe `10`, valeur d'origine du serveur), `agent_swebench/__main__.py` (passe `600`, sous le plafond de 900s) | Vérifié : `mypy`/`flake8` propres ; test unitaire (`_build_transport` avec 600/10/60 → `MCP_TIMEOUT_DELAY` correctement propagée) ; **run réel `agent_swebench` rejoué** (`django__django-15851`) : `success: true`, 29 itérations, patch correct — confirmé par la moulinette officielle (`Correctness: PASSED`, `RESOLVED_FULL`, `Metrics: VALID`) | 2026-08-28 |
| **Aucun moyen pour un conteneur d'être identifié comme appartenant à une session précise** — `container.py` créait les conteneurs sans label distinctif, ce qui a permis un vrai bug côté SWE-bench (voir `AUDIT_SWEBENCH_TOOLS.md`, Corrigés) : avec deux sessions sandbox lancées en parallèle, `mcp_tools_swebench.py` ciblait le mauvais conteneur | `container.py` (label Docker `agent-smith.owner-pid` posé à `containers.create()`, valeur = `os.getpid()` du process hôte), `mcp_bridge.py` (même PID transmis en variable d'env `SANDBOX_OWNER_PID` à tout spawn stdio — MBPP, SWE-bench, et le REPL en profitent tous les trois via le même `_build_transport`) | Vérifié : `mypy`/`flake8` propres ; test réel avec 2 vrais conteneurs Docker démarrés simultanément par 2 process séparés (PID différents) — chaque process retrouve exactement son propre conteneur, aucun conteneur orphelin après. Détail complet et test unitaire de la logique de désambiguïsation dans `AUDIT_SWEBENCH_TOOLS.md` (seul `mcp_tools_swebench.py` a un outil de découverte de conteneur à corriger — MBPP n'en a pas besoin) | 2026-09-04 |

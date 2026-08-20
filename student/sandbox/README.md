# Sandbox 42-Agent-Smith

Bac à sable sécurisé pour l'exécution de code généré par LLM (§V.2 du sujet). C'est la frontière de sécurité entre un agent autonome et le monde réel : tout code produit par le modèle tourne ici, isolé, sans réseau ni accès arbitraire au système.

Le sandbox est la couche d'exécution centrale. Il connecte un serveur MCP et expose ses outils comme des fonctions Python appelables dans le namespace d'exécution, aux côtés de `final_answer`. Il enveloppe le **client MCP**, pas l'inverse : le sandbox restreint ce que peut faire le code, tandis que les actions des outils MCP se déroulent **en dehors** du sandbox.

---

## Vue d'ensemble

```
            ┌─────────────────────────────────────────────────────────┐
   REPL ou │                    PROCESSUS HÔTE                       │
   boucle  │                                                         │
   agent   │  cli.py ── repl.py / (agent_core.loop)                  │
            │     │                                                  │
            │     ▼                                                  │
            │  session.build_container()                             │
            │     │                                                  │
            │     ▼                                                  │
            │  SandboxContainer ──── mcp_bridge.py ──► serveur MCP   │
            │  (container.py)         (client MCP hôte)   (outils)   │
            └─────┬───────────────────────────────────────────────────┘
                  │  socket / JSON Lines (exec, tool_call, result…)
                  ▼
            ┌─────────────────────────────────────────────────────────┐
            │   CONTENEUR DOCKER  (network:none, read-only, mem_limit)│
            │                                                        │
            │   runner.py                                             │
            │     • namespace persistant                             │
            │     • final_answer injecté                             │
            │     • stubs d'outils MCP → tool_call relayés à l'hôte   │
            │     • restrictions.py (allowlist imports + builtins)    │
            │     • watchdog.py (timeout par snippet)                │
            └─────────────────────────────────────────────────────────┘
```

Deux domaines de sécurité **indépendants** :

- **Sandbox** — restreint le code LLM : imports, chemins, timeout, mémoire, builtins.
- **Outils MCP** — s'exécutent hors du sandbox (par exemple `run_tests` sur l'hôte, lecture de fichiers dans Docker). Le timeout du sandbox ne s'applique **pas** aux actions du serveur MCP.

---

## Prérequis

- **Docker** (démon accessible à l'utilisateur courant).
- Les dépendances Python du projet (`uv sync` à la racine).

L'image de base est `python:3.10-slim` (voir `Dockerfile`), épinglée par digest. Un utilisateur non privilégié (`sandbox`, uid 1000) est créé ; le code s'exécute sous cet utilisateur.

---

## Utilisation

La CLI est exposée via le script `sandbox` (déclaré dans `pyproject.toml`) :

```bash
# 1. Lancement interactif (REPL) — aucun argument
uv run sandbox

# 2. Avec une configuration personnalisée
uv run sandbox sandbox_template.json

# 3. Avec les outils MBPP via le transport stdio
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json

# 4. Avec un serveur MCP en HTTP streamable
uv run sandbox --mcp-server <URL>
```

### Mode interactif (REPL)

Sans argument de tâche, la CLI ouvre un REPL : une invite lit le code tapé par l'utilisateur et l'exécute **dans le namespace sandboxé**, soumis aux mêmes restrictions d'imports, de fichiers, de timeout et de mémoire que n'importe quelle exécution. Après chaque entrée, elle affiche le résultat ou l'erreur levée, puis revient à l'invite. Le REPL s'arrête proprement sur la commande `exit` ou sur EOF (`Ctrl+D`).

Les wrappers d'outils MCP du serveur connecté et `final_answer` sont disponibles dans le namespace.

### Configuration

`SandboxConfig` (`config.py`) est un modèle Pydantic, chargeable depuis un fichier JSON :

| Champ | Défaut | Rôle |
|---|---|---|
| `authorized_imports` | `math`, `random`, `itertools`, `collections`, `functools`, `operator`, `heapq`, `bisect`, `string`, `re`, `datetime`, `time`, `json`, `typing`, `copy`, `array`, `cmath` (et variantes `.*`) | Allowlist d'imports ; tout le reste est bloqué |
| `allowed_directories` | `["/workspace", "/testbed"]` | Chemins que le code sandboxé peut lire/écrire, vus **à l'intérieur** du conteneur |
| `max_execution_time_seconds` | `10` | Timeout par snippet (ne s'applique qu'au code sandboxé) |
| `max_memory_mb` | `256` | Plafond RAM du conteneur |
| `pids_limit` | `64` | Nombre max de processus/threads (anti fork-bomb) |

Un exemple complet se trouve dans `sandbox_template.json` à la racine du dépôt.

---

## Comment ça fonctionne

### Les couches

| Fichier | Rôle |
|---|---|
| `cli.py` | Point d'entrée `uv run sandbox`. Charge la config, monte le cycle de vie, connecte le `MCPBridge`, lance le REPL. |
| `session.py` | `build_container()` : câble un `SandboxContainer` aux outils du serveur MCP connecté. Facteur commun réutilisable par la boucle agent (`agent_core`). |
| `container.py` | Cycle de vie Docker : construit/tire l'image, calque l'image dérivée avec `executor/`, démarre le conteneur (`network:none`, `read_only`, `mem_limit`, `cap_drop=ALL`, `pids_limit`, tmpfs sur `/workspace` et `/tmp`), attache le socket stdio, garantit le nettoyage. |
| `repl.py` | REPL interactif : lit le code, l'envoie au conteneur, relaie les appels d'outils, affiche le résultat. |
| `mcp_bridge.py` | Client MCP hôte (stdio **ou** HTTP streamable) dans un thread dédié. Répond aux `tool_call` relayés depuis le conteneur. |
| `executor/` | Code **stdlib uniquement**, copié tel quel dans l'image (déployé dans `/sandbox_executor`), exécuté comme script dans le conteneur. Doit fonctionner sans pydantic ni docker-py, donc aussi bien dans l'image MBPP maison que dans une image SWE-bench fournie. |

### Le protocole JSON Lines (`executor/protocol.py`)

L'hôte et le conteneur échangent des messages JSON sur une ligne chacun, sur le socket stdio du conteneur :

| Sens | Type | Contenu |
|---|---|---|
| hôte → conteneur | `exec` | `{code}` à exécuter |
| hôte → conteneur | `tool_result` | résultat d'un outil MCP relayé |
| conteneur → hôte | `result` | `{stdout}` du snippet |
| conteneur → hôte | `error` | `{error_type, message, traceback}` |
| conteneur → hôte | `final_answer` | `{answer}` — la tâche est terminée |
| conteneur → hôte | `tool_call` | `{name, arguments}` — à relayer au serveur MCP |

### `runner.py` — la boucle dans le conteneur

Le namespace est **persistant** : tout ce qu'un snippet définit (fonctions, variables) survit aux exécutions suivantes de la session. Pour chaque `exec` :

1. `restrictions.install()` a déjà posé l'allowlist d'imports et les builtins restreints au démarrage.
2. Le code est compilé puis exécuté avec `redirect_stdout` (pour capturer les `print`) et sous la contrainte de `watchdog.enforce()`.
3. Le résultat est renvoyé : `result` (stdout), `error` (traceback), ou `final_answer`.

### `final_answer`

`final_answer` est **toujours** disponible dans le namespace, quel que soit le serveur MCP connecté — contrairement aux outils, qui varient. Appelé par le code de l'agent :

```python
# MBPP : passer le code de la solution en argument
final_answer(your_solution_code)

# SWE-bench : passer le patch git
final_answer(get_patch())
```

En interne, `final_answer` lève un signal (`_FinalAnswerSignal`) intercepté par `_handle_exec`, qui renvoie un message `final_answer` à l'hôte. La boucle agent (ou le REPL) l'utilise pour terminer la tâche et produire un `SolutionOutput`. Les exceptions de contrôle de flux (`KeyboardInterrupt`, `SystemExit`) ne sont **pas** avalées silencieusement — elles doivent atteindre la boucle pour un arrêt propre (§V.2.2).

### Wrappers d'outils MCP dans le conteneur

Le conteneur n'a **aucun réseau**. Les outils du serveur MCP connecté y sont injectés comme des **stubs** : un appel à `run_tests(...)` dans le code sérialise un message `tool_call` vers l'hôte, qui suspend le watchdog (les actions MCP ne sont pas soumises au timeout sandbox), appelle le serveur via `mcp_bridge`, et renvoie le résultat dans un message `tool_result`. Le stub retourne alors ce résultat au code appelant.

---

## Modèle de sécurité

La défense est en couches — **Docker est la frontière réelle**, le reste est de la défense en profondeur :

1. **Isolation OS (Docker)** : `network_mode="none"` (aucun réseau entrant/sortant), `read_only=True` (système de fichiers racine en lecture seule), `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`, `mem_limit`, `pids_limit`. Les zones inscriptibles sont des tmpfs RAM plafonnés sur `/workspace` et `/tmp`.
2. **Allowlist d'imports (`restrictions.py`)** : via un `MetaPathFinder`, seuls les modules autorisés s'importent ; les modules dangereux pré-chargés (`os`, etc.) sont purgés de `sys.modules`.
3. **Builtins restreints (`restrictions.py`)** : seuls les builtins sûrs restent (`SAFE_BUILTINS`) ; `open` est remplacé par une version qui vérifie `allowed_directories`. `eval`/`exec`/`compile`, `input`, `breakpoint`, `help` sont exclus.
4. **Timeout par snippet (`watchdog.py`)** : `signal.alarm()` interrompt même une boucle infinie pure-Python, sans tuer le conteneur ni perdre le namespace.

**Limitation connue** : l'introspection d'objets (`().__class__.__bases__[0].__subclasses__()`) peut atteindre des classes déjà chargées en mémoire sans passer par `import`, contournant l'allowlist Python. La fermer complètement exigerait un sandbox AST, que le sujet interdit explicitement (pas de RestrictedPython). La frontière de sécurité réelle reste Docker.

---

## Intégration avec `agent_core`

`session.build_container()` est conçu pour être réutilisé par la boucle agent : `agent_core/loop.py` peut piloter le même conteneur de façon non interactive — envoyer des `exec`, relayer les `tool_call`, lire les `result`/`error`/`final_answer` — là où le REPL gère l'interaction humaine. La connexion/fermeture du `MCPBridge` reste à la charge de l'appelant.

---

## Arborescence

```
student/sandbox/
├── README.md          ← ce document
├── Dockerfile         ← image de base (python:3.10-slim + utilisateur sandbox)
├── cli.py             ← point d'entrée `uv run sandbox`
├── config.py          ← modèle SandboxConfig (Pydantic)
├── container.py       ← cycle de vie Docker + protocole JSON Lines
├── mcp_bridge.py      ← client MCP hôte (stdio / HTTP)
├── repl.py            ← REPL interactif
├── session.py         ← build_container() partagé
└── executor/          ← paquet stdlib-only copié dans le conteneur
    ├── protocol.py    ← schémas de messages JSON Lines
    ├── runner.py      ← boucle d'exécution dans le conteneur
    ├── restrictions.py← allowlist d'imports + builtins restreints
    └── watchdog.py    ← timeout par snippet (signal.alarm)
```

## Notes de décision

- **Un conteneur par session** (2026-08-12) : le namespace persiste sur toute la session, pas un conteneur par snippet.
- **Pas de bind mount hôte** : pour MBPP, `allowed_directories` pointe vers `/workspace`/`/testbed` *dans* le conteneur (tmpfs), pas vers des chemins hôte (2026-08-12).
- **Executor cuit dans l'image** : `docker cp`/`put_archive` ne peut pas écrire dans un conteneur `read_only`, donc l'executor est copié à la construction d'une image dérivée `FROM` l'image de base (2026-08-12).
- **Imports plats dans `executor/`** : `import protocol` (pas de `from . import`), pour que le même paquet tourne comme script dans le conteneur (2026-08-13).

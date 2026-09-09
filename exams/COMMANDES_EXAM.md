./exams/exam_sandbox.sh --student-path ./student --moulinette-path ./moulinette --env-file .env

cd moulinette && uv run moulinette_eval display <solution.json>

./exams/exam_mbpp.sh --student-path ./student --moulinette-path ./moulinette --env-file .env

./exams/exam_sandbox.sh --student-path ./student --moulinette-path ./moulinette --env-file .env

./exams/exam_swebench.sh --student-path ./student --moulinette-path ./moulinette --env-file .env

uv run -m moulinette validate swebench '/home/napo/Documents/agent-smith-repo/docs/benchmarks/TASKS/django__django-15104.json' '/home/napo/Documents/agent-smith-repo/test.json'
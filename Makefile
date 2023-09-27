.venv:  ## create virtual environment if .venv is not present
	python3 -m venv .venv
	.venv/bin/pip install pip-tools

requirements.txt: requirements.in | .venv	## generate requirements for release
	.venv/bin/pip-compile -o requirements.txt requirements.in

install: requirements.txt	## create a development environment, install deps
	.venv/bin/pip-sync requirements.txt

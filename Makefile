all:
		poetry run pytest -v --workers 10
		poetry run make -C tests

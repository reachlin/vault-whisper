.PHONY: test build simulator brain up up-mc down logs shell

test:
	docker compose run --rm test

build:
	docker compose build

simulator:
	docker compose up simulator

brain:
	docker compose up brain

up:
	docker compose up simulator brain

up-mc:
	docker compose --profile minecraft up simulator brain mcserver mcbridge

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f

shell:
	docker compose run --rm test bash

.PHONY: test build simulator brain up down logs shell

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

down:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose run --rm test bash

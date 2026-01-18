.PHONY: run diagnose plot dashboard sim

run:
	python -m app run --config configs/default.yaml

diagnose:
	python -m app diagnose

plot:
	python -m app plot --latest

dashboard:
	python -m app dashboard

sim:
	python -m app sim
